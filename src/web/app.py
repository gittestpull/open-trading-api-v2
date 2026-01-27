# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from dataclasses import asdict

from .process_manager import ProcessManager
from ..api import (
    get_database, get_stock_master_service, get_scheduler,
    get_human_index_calculator, get_ai_analyst, get_backtest_engine,
    get_global_market_collector, get_trade_journal, get_trading_simulator,
    get_telegram_notifier
)
from ..api.log_buffer import get_log_buffer
from ..api.naver import get_naver_collector

import json
import secrets
import re
from pathlib import Path
from datetime import datetime
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Request, Depends, status

# Security Constants
MAX_LOGIN_ATTEMPTS = 5
HONEYPOT_PASSWORD = "trading123"
DEFAULT_SECURE_PASS = secrets.token_urlsafe(16)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", DEFAULT_SECURE_PASS)

if DASHBOARD_PASSWORD == DEFAULT_SECURE_PASS:
    print(f"⚠️  NO PASSWORD SET! Generated secure password: {DASHBOARD_PASSWORD}")

security = HTTPBasic()
login_attempts: dict = {}
blocked_ips: dict = {}

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
BLOCKED_IPS_FILE = BASE_DIR / "web" / "config" / "prod" / "blocked_ips.json" # Default path, adjusted dynamically usually


class StartScalperRequest(BaseModel):
    ticker: str
    budget: float = 1000000
    target: float = 0.005
    live_mode: bool = False
    llm_mode: bool = False
    orderbook: bool = False
    momentum: bool = False
    buy_price: float = 0


class ScreenerRequest(BaseModel):
    per_max: Optional[float] = None
    pbr_max: Optional[float] = None
    foreign_net_min: Optional[int] = None
    change_rate_min: Optional[float] = None
    change_rate_max: Optional[float] = None
    volume_min: Optional[int] = None
    market: Optional[str] = None
    sort_by: str = "market_cap"
    sort_order: str = "DESC"
    limit: int = 50


class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    strategy: str = "ma"
    initial_capital: float = 10000000
    short_period: int = 5
    long_period: int = 20
    rsi_period: int = 14
    oversold: int = 30
    overbought: int = 70


class JournalEntryRequest(BaseModel):
    ticker: str
    side: str
    price: float
    qty: int
    thesis: Optional[str] = None
    pnl: Optional[float] = None


class JournalUpdateRequest(BaseModel):
    ticker: Optional[str] = None
    side: Optional[str] = None
    price: Optional[float] = None
    qty: Optional[int] = None
    thesis: Optional[str] = None
    pnl: Optional[float] = None


class SimulatorTradeRequest(BaseModel):
    ticker: str
    price: float
    quantity: Optional[int] = None
    amount: Optional[float] = None


class SectorRequest(BaseModel):
    sector: str
    force_refresh: bool = False


class SectorUpdateRequest(BaseModel):
    sector: str
    data: dict



# Security Helper Functions
def load_blocked_ips() -> dict:
    if BLOCKED_IPS_FILE.exists():
        try:
            with open(BLOCKED_IPS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_blocked_ips(blocked: dict):
    try:
        BLOCKED_IPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BLOCKED_IPS_FILE, "w") as f:
            json.dump(blocked, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save blocked IPs: {e}")

# Initial Load
if BLOCKED_IPS_FILE.exists():
    blocked_ips.update(load_blocked_ips())

def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def check_rate_limit(request: Request):
    ip = get_client_ip(request)
    if ip in blocked_ips:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="🚫 IP Permanently Blocked"
        )
    return ip

def record_failed_attempt(ip: str):
    if ip not in login_attempts:
        login_attempts[ip] = 0
    login_attempts[ip] += 1
    
    if login_attempts[ip] >= MAX_LOGIN_ATTEMPTS:
        blocked_ips[ip] = {
            "blocked_at": datetime.now().isoformat(),
            "reason": "Excessive Login Failures"
        }
        save_blocked_ips(blocked_ips)
        print(f"🚫 IP {ip} PERMANENTLY BLOCKED")

def verify_password(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    ip = check_rate_limit(request)
    
    # Honeypot Check
    if secrets.compare_digest(credentials.password, HONEYPOT_PASSWORD):
        blocked_ips[ip] = {
            "blocked_at": datetime.now().isoformat(),
            "reason": "HONEYPOT_TRIGGERED"
        }
        save_blocked_ips(blocked_ips)
        print(f"🚨 HONEYPOT TRIGGERED! IP {ip} blocked.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    if not correct:
        record_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if ip in login_attempts:
        del login_attempts[ip]
    return credentials.username


def create_app(base_dir: str) -> FastAPI:
    # Update BASE_DIR and BLOCKED_IPS_PATH based on runtime arg if needed
    global BLOCKED_IPS_FILE
    # Try multiple env locations for blocked_ips
    env_type = os.getenv("ENV_TYPE", "prod")
    potential_path = Path(base_dir) / "web" / "config" / env_type / "blocked_ips.json"
    BLOCKED_IPS_FILE = potential_path
    if BLOCKED_IPS_FILE.exists():
        blocked_ips.update(load_blocked_ips())

    app = FastAPI(title="Deep Dive Investment Platform", version="2.0.0", docs_url="/docs")
    manager = ProcessManager(base_dir)
    
    db = get_database()
    stock_service = get_stock_master_service()
    scheduler = get_scheduler(is_live=True)
    human_index = get_human_index_calculator()
    ai_analyst = get_ai_analyst()
    backtest_engine = get_backtest_engine()
    global_market = get_global_market_collector()
    journal = get_trade_journal()
    simulator = get_trading_simulator()
    telegram = get_telegram_notifier()
    log_buffer = get_log_buffer()
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = os.path.join(static_dir, "index.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return HTMLResponse("<h1>Deep Dive Platform</h1><p>Static files not found</p>")
    
    @app.post("/api/scalper/start")
    async def start_scalper(req: StartScalperRequest):
        result = manager.start_scalper(
            ticker=req.ticker,
            budget=req.budget,
            target=req.target,
            live_mode=req.live_mode,
            llm_mode=req.llm_mode,
            orderbook=req.orderbook,
            momentum=req.momentum,
            buy_price=req.buy_price,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.post("/api/scalper/stop/{ticker}")
    async def stop_scalper(ticker: str):
        result = manager.stop_scalper(ticker)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.get("/api/scalper/status")
    async def get_status(ticker: Optional[str] = None):
        return {"processes": manager.get_status(ticker)}
    
    @app.get("/api/scalper/logs/{ticker}")
    async def get_logs(ticker: str, lines: int = 100):
        logs = manager.get_logs(ticker, lines)
        return {"ticker": ticker, "logs": logs}
    
    @app.get("/api/scalper/states")
    async def get_states():
        return {"states": manager.get_state_files()}
    
    @app.websocket("/ws/logs/{ticker}")
    async def websocket_logs(websocket: WebSocket, ticker: str):
        await websocket.accept()
        ticker_key = ticker.upper()
        last_count = 0
        
        try:
            while True:
                logs = manager.get_logs(ticker_key, 500)
                current_count = len(logs)
                
                if current_count > last_count:
                    new_logs = logs[last_count:]
                    for log in new_logs:
                        await websocket.send_text(log)
                    last_count = current_count
                
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            pass
    
    @app.websocket("/ws/collection-logs")
    async def websocket_collection_logs(websocket: WebSocket):
        await websocket.accept()
        
        async def send_log(log_entry: dict):
            try:
                import json
                await websocket.send_text(json.dumps(log_entry))
            except Exception:
                log_buffer.unsubscribe(send_log)
        
        log_buffer.subscribe(send_log)
        
        try:
            recent_logs = log_buffer.get_recent(50)
            import json
            for log in recent_logs:
                await websocket.send_text(json.dumps(log))
            
            while True:
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            log_buffer.unsubscribe(send_log)
    
    @app.get("/api/stocks/search")
    async def search_stocks(q: str, limit: int = 20):
        results = await stock_service.search_stocks(q, limit)
        return {"stocks": results}
    
    @app.get("/api/stocks/count")
    async def get_stock_count():
        return await stock_service.get_stock_count()
    
    @app.get("/api/stocks/{ticker}")
    async def get_stock(ticker: str):
        stock = await stock_service.get_stock_info(ticker)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        
        price = await db.fetch_one(
            "SELECT * FROM daily_price WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        stats = await db.fetch_one(
            "SELECT * FROM daily_stats WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        investor = await db.fetch_one(
            "SELECT * FROM daily_investor WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        short_credit = await db.fetch_one(
            "SELECT * FROM daily_short_credit WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker,)
        )
        
        news = await db.fetch_all(
            "SELECT datetime, title, source, provider, url FROM stock_news WHERE ticker = ? ORDER BY datetime DESC LIMIT 20",
            (ticker,)
        )
        
        return {
            **stock,
            "price": price,
            "stats": stats,
            "investor": investor,
            "short_credit": short_credit,
            "news": news
        }
    
    @app.post("/api/screener")
    async def screener(req: ScreenerRequest):
        conditions = []
        params = []
        
        base_query = """
            SELECT 
                si.ticker, si.name, si.market, si.sector,
                dp.close, dp.change_rate, dp.volume, dp.market_cap,
                ds.per, ds.pbr, ds.eps, ds.bps,
                di.foreign_net, di.inst_net, di.foreign_ratio,
                dsc.short_ratio, dsc.credit_ratio,
                CASE WHEN dp.close > 0 AND di.foreign_net IS NOT NULL 
                    THEN CAST(di.foreign_net * dp.close / 100000000.0 AS REAL) ELSE NULL END as foreign_net_amt,
                CASE WHEN dp.close > 0 AND di.inst_net IS NOT NULL 
                    THEN CAST(di.inst_net * dp.close / 100000000.0 AS REAL) ELSE NULL END as inst_net_amt
            FROM stock_info si
            LEFT JOIN daily_price dp ON si.ticker = dp.ticker 
                AND dp.date = (SELECT MAX(date) FROM daily_price WHERE ticker = si.ticker)
            LEFT JOIN daily_stats ds ON si.ticker = ds.ticker 
                AND ds.date = (SELECT MAX(date) FROM daily_stats WHERE ticker = si.ticker)
            LEFT JOIN daily_investor di ON si.ticker = di.ticker 
                AND di.date = (SELECT MAX(date) FROM daily_investor WHERE ticker = si.ticker)
            LEFT JOIN daily_short_credit dsc ON si.ticker = dsc.ticker
                AND dsc.date = (SELECT MAX(date) FROM daily_short_credit WHERE ticker = si.ticker)
            WHERE 1=1
        """
        
        if req.per_max is not None:
            conditions.append("ds.per <= ? AND ds.per > 0")
            params.append(req.per_max)
        
        if req.pbr_max is not None:
            conditions.append("ds.pbr <= ? AND ds.pbr > 0")
            params.append(req.pbr_max)
        
        if req.foreign_net_min is not None:
            conditions.append("di.foreign_net >= ?")
            params.append(req.foreign_net_min)
        
        if req.change_rate_min is not None:
            conditions.append("dp.change_rate >= ?")
            params.append(req.change_rate_min)
        
        if req.change_rate_max is not None:
            conditions.append("dp.change_rate <= ?")
            params.append(req.change_rate_max)
        
        if req.volume_min is not None:
            conditions.append("dp.volume >= ?")
            params.append(req.volume_min)
        
        if req.market:
            conditions.append("si.market = ?")
            params.append(req.market.upper())
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        sort_map = {
            "market_cap": "dp.market_cap",
            "change_rate": "dp.change_rate",
            "volume": "dp.volume",
            "per": "ds.per",
            "pbr": "ds.pbr",
            "foreign_net": "di.foreign_net",
            "short_ratio": "dsc.short_ratio",
            "credit_ratio": "dsc.credit_ratio"
        }
        
        sort_col_key = req.sort_by if req.sort_by in sort_map else "market_cap"
        db_col = sort_map[sort_col_key]
        
        sort_order = "DESC" if req.sort_order.upper() == "DESC" else "ASC"
        
        base_query += f" ORDER BY {db_col} {sort_order} NULLS LAST LIMIT ?"
        params.append(req.limit)
        
        results = await db.fetch_all(base_query, tuple(params))
        return {"stocks": results, "count": len(results)}
    
    @app.get("/api/deepdive/{ticker}")
    async def deep_dive(ticker: str):
        stock = await stock_service.get_stock_info(ticker)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")

        # On-demand fetch for Forward EPS if missing
        if not stock.get('fwd_eps'):
            try:
                naver = get_naver_collector()
                await naver.fetch_fundamental_data(ticker)
                # Reload stock info
                stock = await stock_service.get_stock_info(ticker)
            except Exception as e:
                print(f"Failed to fetch forward EPS: {e}")
        
        # On-demand fetch for Open Talk Users if missing
        if not stock.get('opentalk_users'):
            try:
                naver = get_naver_collector()
                await naver.fetch_opentalk_info(ticker)
                # Reload stock info
                stock = await stock_service.get_stock_info(ticker)
            except Exception as e:
                print(f"Failed to fetch opentalk users: {e}")
        
        price_history = await db.fetch_all(
            "SELECT * FROM daily_price WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker,)
        )
        
        stats_history = await db.fetch_all(
            "SELECT * FROM daily_stats WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker,)
        )
        
        investor_history = await db.fetch_all(
            "SELECT * FROM daily_investor WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker,)
        )
        
        short_credit = await db.fetch_all(
            "SELECT * FROM daily_short_credit WHERE ticker = ? ORDER BY date DESC LIMIT 30",
            (ticker,)
        )
        
        news = await db.fetch_all(
            "SELECT * FROM stock_news WHERE ticker = ? ORDER BY datetime DESC LIMIT 20",
            (ticker,)
        )
        
        opentalk_history = await db.get_naver_talk_history(ticker, days=30)
        
        return {
            "stock": stock,
            "price_history": price_history,
            "stats_history": stats_history,
            "investor_history": investor_history,
            "short_credit": short_credit,
            "news": news,
            "opentalk_history": opentalk_history
        }
    
    @app.get("/api/human-index/fomo-alerts")
    async def get_fomo_alerts(threshold: float = 70):
        stocks = await human_index.get_fomo_alert_stocks(threshold)
        return {"stocks": stocks, "count": len(stocks)}
    
    @app.get("/api/human-index/bottom-signals")
    async def get_bottom_signals(threshold: float = 20):
        stocks = await human_index.get_bottom_signal_stocks(threshold)
        return {"stocks": stocks, "count": len(stocks)}
    
    @app.get("/api/human-index/{ticker}")
    async def get_human_index_api(ticker: str):
        data = await human_index.get_human_index(ticker)
        if not data:
            data = await human_index.calculate_human_index(ticker)
        return data
    
    @app.get("/api/human-index/{ticker}/history")
    async def get_human_index_history(ticker: str, days: int = 30):
        history = await human_index.get_human_index_history(ticker, days)
        return {"ticker": ticker, "history": history, "count": len(history)}
    
    @app.get("/api/human-index/{ticker}/chart")
    async def get_human_index_chart(ticker: str, days: int = 30):
        chart_data = await human_index.get_human_index_chart_data(ticker, days)
        return chart_data
    
    @app.get("/api/human-index/{ticker}/youtube-history")
    async def get_youtube_history(ticker: str, days: int = 30):
        history = await human_index.get_youtube_history(ticker, days)
        return {"ticker": ticker, "history": history, "count": len(history)}
    
    @app.get("/api/human-index/{ticker}/naver-history")
    async def get_naver_history(ticker: str, days: int = 30):
        history = await human_index.get_naver_history(ticker, days)
        return {"ticker": ticker, "history": history, "count": len(history)}
    
    @app.post("/api/human-index/{ticker}/collect")
    async def collect_human_data(ticker: str, days: int = 30):
        stock = await stock_service.get_stock_info(ticker)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        
        # Run synchronously to return status
        result = await human_index.collect_all_human_data(ticker, stock['name'], days=days)
        
        return {
            "status": "collected" if result.get('collected') else "failed",
            "ticker": ticker,
            "details": result
        }
    
    @app.get("/api/ai/deepdive/{ticker}")
    async def ai_deep_dive(ticker: str, mode: str = "simple"):
        if mode not in ["simple", "deep"]:
            mode = "simple"
        report = await ai_analyst.generate_deep_dive_report(ticker, mode=mode)
        if "error" in report:
            raise HTTPException(status_code=404, detail=report["error"])
        return report
    
    @app.post("/api/ai/compare")
    async def ai_compare(tickers: List[str]):
        if len(tickers) < 2:
            raise HTTPException(status_code=400, detail="At least 2 tickers required")
        result = await ai_analyst.compare_stocks(tickers)
        return result
    
    @app.post("/api/global/sector-leaders")
    async def get_global_sector_leaders(req: SectorRequest):
        result = await ai_analyst.get_global_sector_leaders(req.sector, req.force_refresh)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    
    @app.get("/api/global/sectors")
    async def get_saved_sectors():
        results = await ai_analyst.get_saved_sectors()
        return {"sectors": results}

    @app.put("/api/global/sector-leaders")
    async def update_sector_leaders(req: SectorUpdateRequest):
        success = await ai_analyst.update_sector_data(req.sector, req.data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update sector data")
        return {"status": "updated"}

    @app.post("/api/history/collect-sector")
    async def collect_sector_history(req: SectorUpdateRequest, background_tasks: BackgroundTasks):
        async def run_collection():
            await history_collector.init_db()
            await history_collector.collect_sector_history(req.data, days=365)
        
        background_tasks.add_task(run_collection)
        return {"status": "started", "message": f"Collecting 1 year history for sector: {req.sector}"}

    @app.post("/api/backtest/run")
    async def run_backtest(req: BacktestRequest):
        if req.strategy == "ma":
            result = await backtest_engine.run_simple_ma_strategy(
                ticker=req.ticker,
                start_date=req.start_date,
                end_date=req.end_date,
                short_period=req.short_period,
                long_period=req.long_period,
                initial_capital=req.initial_capital
            )
        elif req.strategy == "rsi":
            result = await backtest_engine.run_rsi_strategy(
                ticker=req.ticker,
                start_date=req.start_date,
                end_date=req.end_date,
                period=req.rsi_period,
                oversold=req.oversold,
                overbought=req.overbought,
                initial_capital=req.initial_capital
            )
        else:
            raise HTTPException(status_code=400, detail="Unknown strategy")
        
        await backtest_engine.save_result(result)
        return asdict(result)
    
    @app.get("/api/backtest/results")
    async def get_backtest_results(limit: int = 20):
        results = await backtest_engine.get_results(limit)
        return {"results": results, "count": len(results)}
    
    @app.get("/api/global-market")
    async def get_global_market_data():
        summary = await global_market.get_market_summary()
        return summary
    
    @app.post("/api/global-market/collect")
    async def collect_global_market(background_tasks: BackgroundTasks):
        async def run_collection():
            await global_market.collect_all()
        
        background_tasks.add_task(run_collection)
        return {"status": "collection_started"}
    
    @app.get("/api/global-market/history/{symbol}")
    async def get_global_market_history(symbol: str, days: int = 30):
        history = await global_market.get_history(symbol.upper(), days)
        return {"symbol": symbol, "history": history}
    
    @app.post("/api/journal/entry")
    async def add_journal_entry(req: JournalEntryRequest):
        entry_id = await journal.add_entry(
            ticker=req.ticker,
            side=req.side,
            price=req.price,
            qty=req.qty,
            thesis=req.thesis,
            pnl=req.pnl
        )
        return {"id": entry_id, "status": "created"}
    
    @app.put("/api/journal/entry/{entry_id}")
    async def update_journal_entry(entry_id: int, req: JournalUpdateRequest):
        success = await journal.update_entry(
            entry_id=entry_id,
            ticker=req.ticker,
            side=req.side,
            price=req.price,
            qty=req.qty,
            thesis=req.thesis,
            pnl=req.pnl
        )
        if not success:
            raise HTTPException(status_code=404, detail="Entry not found or no changes")
        return {"status": "updated"}

    @app.delete("/api/journal/entry/{entry_id}")
    async def delete_journal_entry(entry_id: int):
        success = await journal.delete_entry(entry_id)
        return {"status": "deleted"}
    
    @app.get("/api/journal/entries")
    async def get_journal_entries(
        ticker: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50
    ):
        entries = await journal.get_entries(ticker, start_date, end_date, limit)
        return {"entries": entries, "count": len(entries)}
    
    @app.get("/api/journal/entry/{entry_id}")
    async def get_journal_entry(entry_id: int):
        entry = await journal.get_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry
    
    @app.get("/api/journal/statistics")
    async def get_journal_statistics(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        stats = await journal.get_statistics(start_date, end_date)
        return stats
    
    @app.post("/api/journal/analyze/{entry_id}")
    async def analyze_journal_entry(entry_id: int):
        result = await journal.analyze_entry(entry_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    
    @app.get("/api/simulator/portfolio")
    async def get_simulator_portfolio():
        summary = await simulator.get_portfolio_summary()
        return summary
    
    @app.post("/api/simulator/buy")
    async def simulator_buy(req: SimulatorTradeRequest):
        result = simulator.buy(
            ticker=req.ticker,
            price=req.price,
            quantity=req.quantity,
            amount=req.amount
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.post("/api/simulator/sell")
    async def simulator_sell(req: SimulatorTradeRequest):
        result = simulator.sell(
            ticker=req.ticker,
            price=req.price,
            quantity=req.quantity
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    
    @app.get("/api/simulator/trades")
    async def get_simulator_trades(limit: int = 50):
        trades = simulator.get_trades(limit)
        return {"trades": trades, "count": len(trades)}
    
    @app.post("/api/simulator/reset")
    async def reset_simulator(initial_capital: float = 10000000):
        simulator.reset(initial_capital)
        return {"status": "reset", "initial_capital": initial_capital}
    
    @app.get("/api/simulator/export")
    async def export_simulator_state():
        state = simulator.export_state()
        return state
    
    @app.post("/api/simulator/import")
    async def import_simulator_state(data: dict):
        simulator.import_state(data)
        return {"status": "imported"}
    
    @app.get("/api/telegram/status")
    async def get_telegram_status():
        return {
            "configured": telegram.is_configured(),
            "has_token": bool(telegram.bot_token),
            "has_chat_id": bool(telegram.chat_id)
        }
    
    @app.post("/api/telegram/test")
    async def test_telegram():
        if not telegram.is_configured():
            raise HTTPException(status_code=400, detail="Telegram not configured")
        
        success = telegram.send_message("Deep Dive Platform test message")
        return {"success": success}
    
    @app.get("/api/admin/scheduler/status")
    async def scheduler_status():
        return scheduler.get_status()
    
    @app.post("/api/admin/scheduler/start")
    async def start_scheduler(hour: int = 15, minute: int = 50):
        scheduler.start(hour=hour, minute=minute)
        return {"status": "started", "schedule": f"{hour:02d}:{minute:02d}"}
    
    @app.post("/api/admin/scheduler/stop")
    async def stop_scheduler():
        scheduler.stop()
        return {"status": "stopped"}
    
    @app.post("/api/admin/collect")
    async def trigger_collection(background_tasks: BackgroundTasks, force: bool = False, detect_changes: bool = False):
        async def run_collection():
            await scheduler.run_now(force=force, detect_changes=detect_changes)
        
        background_tasks.add_task(run_collection)
        mode = "DETECT " if detect_changes else ("FORCE " if force else "")
        return {"status": "collection_started", "force": force, "detect_changes": detect_changes, "message": f"{mode}Data collection started in background"}
    
    @app.post("/api/admin/load-stocks")
    async def load_stocks():
        count = await scheduler.load_stocks_only()
        return {"status": "success", "count": count}

    class MinuteTickersRequest(BaseModel):
        tickers: list[str]

    @app.post("/api/admin/minute-tickers")
    async def set_minute_tickers(req: MinuteTickersRequest):
        await scheduler.set_minute_tickers(req.tickers)
        scheduler.start_minute_collection()
        return {"status": "success", "tickers": req.tickers}

    @app.get("/api/admin/minute-tickers")
    async def get_minute_tickers():
        status = scheduler.get_status()
        return {"tickers": status.get('minute_tickers', [])}

    @app.post("/api/admin/minute-collect-now")
    async def collect_minute_now(background_tasks: BackgroundTasks):
        async def run():
            return await scheduler.run_minute_now()
        background_tasks.add_task(run)
        return {"status": "started", "message": "Minute collection started in background"}
    
    @app.get("/api/admin/collection-logs")
    async def get_collection_logs(limit: int = 20):
        logs = await db.fetch_all(
            "SELECT * FROM collection_log ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return {"logs": logs}
    
    @app.on_event("startup")
    async def startup_event():
        db.create_tables()
        await scheduler.initialize()
        scheduler.start()
    
    @app.on_event("shutdown")
    def shutdown_event():
        manager.cleanup()
        scheduler.stop()
    
    # History Collection Endpoints
    from ..api import get_history_collector
    history_collector = get_history_collector()

    @app.get("/api/history/overview")
    async def get_history_overview():
        return {"summary": await history_collector.get_history_summary()}
    @app.get("/api/history/coverage/{ticker}")
    async def get_coverage(ticker: str, timeframe: str = "D"):
        return await history_collector.get_coverage_stats(ticker, timeframe)
    class HistoryCollectRequest(BaseModel):
        ticker: str
        start_date: str # YYYYMMDD
        end_date: str # YYYYMMDD
        timeframe: str = "D" # D, W, M
        time: str = "153000" # HHMMSS

    @app.post("/api/history/collect")
    async def collect_history(req: HistoryCollectRequest):
        # Initialize DB schema on first run
        await history_collector.init_db()
        
        result = await history_collector.collect_history(
            ticker=req.ticker,
            start_date=req.start_date,
            end_date=req.end_date,
            timeframe=req.timeframe,
            time=req.time
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @app.get("/api/history/{ticker}")
    async def get_history(ticker: str, timeframe: str = "D", limit: int = 100):
        data = await history_collector.get_history(ticker, timeframe, limit)
        return {"history": data, "count": len(data)}

    class BulkCollectRequest(BaseModel):
        tickers: list[str]
        start_date: str
        end_date: str
        timeframes: list[str] = ["D", "W", "M"]

    @app.post("/api/history/collect-bulk")
    async def collect_bulk_history(req: BulkCollectRequest, background_tasks: BackgroundTasks):
        await history_collector.init_db()

        async def run_bulk():
            results = []
            for ticker in req.tickers:
                result = await history_collector.collect_bulk_history(
                    ticker=ticker,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    timeframes=req.timeframes
                )
                results.append(result)
            return results

        background_tasks.add_task(run_bulk)
        return {
            "status": "started",
            "tickers": req.tickers,
            "timeframes": req.timeframes,
            "message": f"Collecting {len(req.tickers)} tickers in background"
        }

    @app.post("/api/history/collect-bulk-sync")
    async def collect_bulk_history_sync(req: BulkCollectRequest):
        await history_collector.init_db()

        results = []
        for ticker in req.tickers:
            result = await history_collector.collect_bulk_history(
                ticker=ticker,
                start_date=req.start_date,
                end_date=req.end_date,
                timeframes=req.timeframes
            )
            results.append(result)

        total = sum(r.get('total_count', 0) for r in results if 'error' not in r)
        return {
            "status": "success",
            "total_records": total,
            "results": results
        }

    return app
