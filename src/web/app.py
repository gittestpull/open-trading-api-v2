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
    get_telegram_notifier, get_maga_engine, get_trade_stats_service
)
from ..api.indices import fetch_indices
from ..api.recommendation import get_recommender
from ..api.log_buffer import get_log_buffer
from ..api.naver import get_naver_collector
from ..api.report import report_search

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


class GridLadderStartRequest(BaseModel):
    ticker: str
    total_budget: int = 10_000_000
    order_amount: int = 500_000
    entry_tick_levels: List[int] = [6, 7, 8]
    trigger_level: int = 6
    env_dv: str = "real"
    poll_interval: float = 1.0



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
    
    app.include_router(report_search.router, prefix="/api/reports", tags=["reports"])

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = os.path.join(static_dir, "index.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return HTMLResponse("<h1>Deep Dive Platform</h1><p>Static files not found</p>")
    
    @app.get("/api/indices")
    async def get_market_indices():
        return await fetch_indices()

    @app.get("/api/recommendations")
    async def get_ai_recommendations():
        recommender = get_recommender()
        return await recommender.get_market_recommendations()

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
    
    @app.websocket("/ws/maga")
    async def websocket_maga(websocket: WebSocket):
        await websocket.accept()
        maga_engine = get_maga_engine()
        
        async def send_maga_event(event: dict):
            try:
                await websocket.send_text(json.dumps(event))
            except Exception:
                maga_engine.unsubscribe(send_maga_event)
        
        maga_engine.subscribe(send_maga_event)
        
        try:
            while True:
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            maga_engine.unsubscribe(send_maga_event)

    @app.get("/api/macro/trade-stats")
    async def get_trade_stats(limit: int = 12):
        service = get_trade_stats_service()
        data = await service.get_monthly_stats(limit)
        return {"stats": data}

    @app.get("/api/maga/latest")
    async def get_maga_latest():
        try:
            # Read actual tweets from the file generated by the host
            file_path = os.path.join(os.path.dirname(__file__), "..", "api", "trump_tweets.txt")
            if not os.path.exists(file_path):
                return {"tweets": [], "error": "Tweet data file not found"}
                
            with open(file_path, "r") as f:
                result = f.read()
                
            tweets = []
            sections = result.split('──────────────────────────────────────────────────')
            for section in sections:
                if section.strip():
                    lines = [l.strip() for l in section.strip().split('\n') if l.strip()]
                    # Look for date line first
                    time_line = [l for l in lines if l.startswith('📅')]
                    time = time_line[0].replace('📅', '').strip() if time_line else "Unknown"
                    
                    # Text is usually the first non-header line
                    # lines[0] is usually "@realDonaldTrump..."
                    text = ""
                    for l in lines[1:]:
                        if not l.startswith('📅') and not l.startswith('🔗') and not l.startswith('🖼️') and not l.startswith('🎬') and not l.startswith('┌─'):
                            text = l
                            break
                    
                    if not text: continue

                    # AI Insight logic
                    insight = "트럼프의 발언 분석 중..."
                    stocks = []
                    if "MELANIA" in text.upper(): 
                        insight = "멜라니아 관련 개인적 소회. 시장 영향 미미."
                    elif "COLD WAVE" in text.upper(): 
                        insight = "미국 한파 경고. 천연가스/에너지 섹터 변동성 주의."
                        stocks = [{"name": "한국석유", "ticker": "004090", "score": 85, "reason": "에너지 가격 상승 수혜"}]
                    elif "TARIFFS" in text.upper():
                        insight = "관세 위력 강조. 국내 수출 기업 타격 및 반사이익 테마(철강 등) 주목."
                        stocks = [{"name": "유니온스틸", "ticker": "004850", "score": 92, "reason": "철강 관세 반사이익"}]
                    
                    tweets.append({
                        "time": time,
                        "tags": "#RealTime #Trump",
                        "text": text,
                        "insight": insight,
                        "stocks": stocks
                    })
            return {"tweets": tweets}
        except Exception as e:
            return {"tweets": [], "error": str(e)}

    @app.on_event("startup")
    async def startup_event():
        db.create_tables()
        _init_grid_table()
        await get_trade_stats_service().seed_data()
        await scheduler.initialize()
        scheduler.start()
        await get_maga_engine().start()
    
    @app.on_event("shutdown")
    def shutdown_event():
        manager.cleanup()
        scheduler.stop()
        get_maga_engine().stop()
        _grid_cleanup()
        # Stop WS engines (best-effort sync wrapper)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(stop_all_engines())
            else:
                loop.run_until_complete(stop_all_engines())
        except Exception:
            pass
    
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

    # ================================================================
    # Grid Ladder Manager (동적 그리드 계단식 매수)
    # ================================================================
    import threading
    from collections import deque
    from ..strategies.grid_ladder_manager import (
        GridLadderManager, GridLadderConfig, load_all_grid_states, 
        delete_grid_state, _init_grid_table, price_n_ticks_below
    )

    _grid_lock = threading.Lock()
    _grid_instances: dict[str, GridLadderManager] = {}
    _grid_tasks: dict[str, asyncio.Task] = {}

    def _grid_cleanup():
        """Shutdown: cancel tasks + cancel pending orders"""
        with _grid_lock:
            for ticker, task in _grid_tasks.items():
                if not task.done():
                    task.cancel()
            for ticker, mgr in _grid_instances.items():
                for ono, order in list(mgr.pending_orders.items()):
                    try:
                        mgr._cancel_order(order)
                    except Exception:
                        pass
            _grid_tasks.clear()
            _grid_instances.clear()

    def _get_stock_name(ticker: str) -> str:
        """DB에서 종목명 조회"""
        try:
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            row = conn.execute("SELECT name FROM stock_info WHERE ticker=?", (ticker,)).fetchone()
            conn.close()
            return row[0] if row else ticker
        except:
            return ticker

    def _recalc_saved_pending(saved_row: dict) -> dict:
        """Saved 상태의 pending 주문을 현재가 기준으로 재계산"""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples_user', 'domestic_stock'))
            import kis_auth as ka
            import domestic_stock_functions as ds
            
            ka.auth(svr="prod")
            ticker = saved_row['ticker']
            
            # 현재가 조회
            df = ds.inquire_price(env_dv="real", fid_cond_mrkt_div_code="J", fid_input_iscd=ticker)
            if df.empty:
                return saved_row
            
            current_price = int(df.iloc[0].get('stck_prpr', 0))
            if current_price <= 0:
                return saved_row
            
            # 기준가를 현재가로 갱신
            saved_row['base_price'] = current_price
            
            # entry_tick_levels로 pending 재계산
            levels = json.loads(saved_row.get('entry_tick_levels', '[6,7,8]'))
            order_amount = saved_row.get('order_amount', 500000)
            
            new_pending = []
            for level in levels:
                target_price = price_n_ticks_below(current_price, level)
                quantity = int(order_amount / target_price) if target_price > 0 else 0
                if quantity > 0:
                    new_pending.append({
                        'order_no': f'SAVED_L{level}',
                        'price': target_price,
                        'quantity': quantity,
                        'tick_level': level,
                    })
            
            saved_row['pending_order_details'] = new_pending
            saved_row['pending_orders'] = len(new_pending)
            return saved_row
        except Exception as e:
            return saved_row

    def _build_saved_response(s: dict, recalc: bool = True) -> dict:
        """DB row → API response"""
        result = {
            "ticker": s['ticker'], "name": _get_stock_name(s['ticker']), "running": False, "saved": True,
            "total_budget": s['total_budget'],
            "order_amount": s['order_amount'],
            "entry_tick_levels": json.loads(s.get('entry_tick_levels', '[6,7,8]')),
            "trigger_level": s.get('trigger_level', 6),
            "round": s['current_round'], "base_price": s['base_price'],
            "total_invested": s['total_invested'],
            "budget_remaining": s['total_budget'] - s['total_invested'],
            "pending_orders": 0, "executed_orders": 0,
            "holdings": json.loads(s.get('holdings', '[]')),
            "last_error": s.get('last_error', ''),
            "paused": False, "pause_reason": "",
            "env_dv": s['env_dv'],
            "pending_order_details": json.loads(s.get("pending_order_details", "[]")),
            "status": s.get('status', 'stopped'),
            "updated_at": s.get('updated_at', ''),
        }
        
        if recalc and result['pending_order_details']:
            # 현재가 기준으로 재계산
            recalced = _recalc_saved_pending(s)
            result['base_price'] = recalced['base_price']
            result['pending_order_details'] = recalced.get('pending_order_details', [])
            result['pending_orders'] = len(result['pending_order_details'])
        
        return result

    def _grid_key(ticker: str, env_dv: str) -> str:
        """Unique key: TICKER:real or TICKER:demo"""
        return f"{ticker.upper()}:{env_dv}"

    @app.post("/api/grid-ladder/start")
    async def start_grid_ladder(req: GridLadderStartRequest):
        ticker = req.ticker.upper()
        key = _grid_key(ticker, req.env_dv)
        with _grid_lock:
            if key in _grid_tasks and not _grid_tasks[key].done():
                raise HTTPException(status_code=400, detail=f"{ticker} ({req.env_dv}) already running")

        config = GridLadderConfig(
            stock_code=ticker,
            total_budget=req.total_budget,
            order_amount=req.order_amount,
            entry_tick_levels=req.entry_tick_levels,
            trigger_level=req.trigger_level,
            env_dv=req.env_dv,
            poll_interval=req.poll_interval,
        )
        mgr = GridLadderManager(config)

        with _grid_lock:
            _grid_instances[key] = mgr

        async def _run_grid():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mgr.run)

        task = asyncio.create_task(_run_grid())
        with _grid_lock:
            _grid_tasks[key] = task

        return {
            "status": "started",
            "ticker": ticker,
            "env": req.env_dv,
            "total_budget": req.total_budget,
            "order_amount": req.order_amount,
            "levels": req.entry_tick_levels,
            "trigger": req.trigger_level,
        }

    @app.post("/api/grid-ladder/stop/{ticker}")
    async def stop_grid_ladder(ticker: str, env_dv: str = "real"):
        t = ticker.upper()
        key = _grid_key(t, env_dv)
        # Also try without env for backward compat
        if key not in _grid_instances:
            # Try finding any key starting with this ticker
            matches = [k for k in _grid_instances if k.startswith(t + ":")]
            if len(matches) == 1:
                key = matches[0]
            elif not matches:
                raise HTTPException(status_code=404, detail=f"{t} not found")
            else:
                raise HTTPException(status_code=400, detail=f"Multiple instances for {t}. Specify env_dv=real or env_dv=demo")

        with _grid_lock:
            if key in _grid_instances:
                _grid_instances[key].request_stop()
            task = _grid_tasks.get(key)
            if task and not task.done():
                task.cancel()
            if key in _grid_instances:
                mgr = _grid_instances[key]
                for ono, order in list(mgr.pending_orders.items()):
                    try: mgr._cancel_order(order)
                    except: pass
                mgr.pending_orders.clear()
            status_data = _grid_instances[key].get_status() if key in _grid_instances else {}
            _grid_tasks.pop(key, None)
            _grid_instances.pop(key, None)

        return {"status": "stopped", "ticker": t, "final_state": status_data}

    @app.get("/api/grid-ladder/status")
    async def grid_ladder_status(ticker: Optional[str] = None, include_saved: bool = True):
        with _grid_lock:
            if ticker:
                t = ticker.upper()
                matches = {k: v for k, v in _grid_instances.items() if k.startswith(t + ":") or k == t}
                if not matches:
                    # Check DB for saved state
                    if include_saved:
                        saved = load_all_grid_states()
                        saved_matches = [s for s in saved if s['ticker'] == t]
                        if saved_matches:
                            results = [_build_saved_response(s) for s in saved_matches]
                            if len(results) == 1:
                                return results[0]
                            return {"grid_ladders": results}
                    raise HTTPException(status_code=404, detail=f"{t} not found")
                results = []
                for key, mgr in matches.items():
                    running = key in _grid_tasks and not _grid_tasks[key].done()
                    results.append({"ticker": t, "name": _get_stock_name(t), "running": running, "saved": False, **mgr.get_status()})
                if len(results) == 1:
                    return results[0]
                return {"grid_ladders": results}

            # All instances: active + saved
            results = []
            active_keys = set()
            for key, mgr in _grid_instances.items():
                t = key.split(":")[0]
                running = key in _grid_tasks and not _grid_tasks[key].done()
                results.append({"ticker": t, "name": _get_stock_name(t), "running": running, "saved": False, **mgr.get_status()})
                active_keys.add(key)

        # Add saved instances that aren't currently active
        if include_saved:
            try:
                saved = load_all_grid_states()
                for s in saved:
                    key = f"{s['ticker']}:{s['env_dv']}"
                    if key not in active_keys:
                        results.append(_build_saved_response(s))
            except Exception:
                pass

        return {"grid_ladders": results}

    class GridLadderUpdateConfig(BaseModel):
        total_budget: Optional[int] = None
        order_amount: Optional[int] = None
        entry_tick_levels: Optional[List[int]] = None
        trigger_level: Optional[int] = None

    @app.put("/api/grid-ladder/config/{ticker}")
    async def update_grid_config(ticker: str, req: GridLadderUpdateConfig, env_dv: str = "demo"):
        t = ticker.upper()
        key = _grid_key(t, env_dv)

        # Update running instance
        with _grid_lock:
            if key in _grid_instances:
                mgr = _grid_instances[key]
                if req.total_budget is not None:
                    mgr.config.total_budget = req.total_budget
                if req.order_amount is not None:
                    mgr.config.order_amount = req.order_amount
                if req.entry_tick_levels is not None:
                    mgr.config.entry_tick_levels = req.entry_tick_levels
                if req.trigger_level is not None:
                    mgr.config.trigger_level = req.trigger_level
                from ..strategies.grid_ladder_manager import save_grid_state
                save_grid_state(mgr)
                return {"status": "updated", "ticker": t, "env_dv": env_dv}

        # Update saved instance in DB
        import sqlite3
        from ..strategies.grid_ladder_manager import _get_db_path
        conn = sqlite3.connect(_get_db_path())
        updates = []
        params = []
        if req.total_budget is not None:
            updates.append("total_budget=?"); params.append(req.total_budget)
        if req.order_amount is not None:
            updates.append("order_amount=?"); params.append(req.order_amount)
        if req.entry_tick_levels is not None:
            updates.append("entry_tick_levels=?"); params.append(json.dumps(req.entry_tick_levels))
        if req.trigger_level is not None:
            updates.append("trigger_level=?"); params.append(req.trigger_level)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        updates.append("updated_at=datetime('now')")
        params.extend([t, env_dv])
        conn.execute(f"UPDATE grid_ladder_instances SET {', '.join(updates)} WHERE ticker=? AND env_dv=?", params)
        conn.commit()
        conn.close()
        return {"status": "updated", "ticker": t, "env_dv": env_dv}

    @app.delete("/api/grid-ladder/saved/{ticker}")
    async def delete_saved_grid(ticker: str, env_dv: str = "demo"):
        t = ticker.upper()
        delete_grid_state(t, env_dv)
        return {"status": "deleted", "ticker": t, "env_dv": env_dv}

    @app.get("/api/grid-ladder/logs/{ticker}")
    async def grid_ladder_logs(ticker: str, env_dv: str = "real"):
        t = ticker.upper()
        key = _grid_key(t, env_dv)
        if key not in _grid_instances:
            matches = [k for k in _grid_instances if k.startswith(t + ":")]
            key = matches[0] if matches else key
        with _grid_lock:
            if key not in _grid_instances:
                raise HTTPException(status_code=404, detail=f"{t} not found")
            logs = list(_grid_instances[key].trade_log)
        return {"ticker": t, "trade_log": logs}

    @app.post("/api/grid-ladder/retry/{ticker}")
    async def grid_ladder_retry(ticker: str, env_dv: str = "real"):
        t = ticker.upper()
        key = _grid_key(t, env_dv)
        if key not in _grid_instances:
            matches = [k for k in _grid_instances if k.startswith(t + ":")]
            key = matches[0] if matches else key
        with _grid_lock:
            if key not in _grid_instances:
                raise HTTPException(status_code=404, detail=f"{t} not found")
            mgr = _grid_instances[key]
            if not mgr.paused:
                raise HTTPException(status_code=400, detail=f"{t} is not paused")
            mgr.resume()
        return {"status": "resumed", "ticker": t}

    @app.post("/api/grid-ladder/skip/{ticker}")
    async def grid_ladder_skip(ticker: str, env_dv: str = "real"):
        t = ticker.upper()
        key = _grid_key(t, env_dv)
        if key not in _grid_instances:
            matches = [k for k in _grid_instances if k.startswith(t + ":")]
            key = matches[0] if matches else key
        with _grid_lock:
            if key not in _grid_instances:
                raise HTTPException(status_code=404, detail=f"{t} not found")
            mgr = _grid_instances[key]
            if not mgr.paused:
                raise HTTPException(status_code=400, detail=f"{t} is not paused")
            mgr.skip()
        return {"status": "skipped", "ticker": t}

    # ================================================================
    # Grid Ladder WebSocket Endpoints (실시간 호가 + 이벤트)
    # ================================================================
    from ..strategies.grid_ws_engine import get_or_create_engine, stop_engine, stop_all_engines

    @app.websocket("/ws/grid-ladder/orderbook/{ticker}")
    async def ws_grid_orderbook(websocket: WebSocket, ticker: str):
        """Stream real-time orderbook data to frontend"""
        await websocket.accept()
        t = ticker.upper()
        engine = None
        q = None
        try:
            engine = await get_or_create_engine(t)
            q = engine.subscribe_orderbook(t)

            # Send current snapshot immediately
            snapshot = engine.get_current_orderbook(t)
            if snapshot.get("asks") or snapshot.get("bids"):
                await websocket.send_text(json.dumps(snapshot))

            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=30)
                    await websocket.send_text(json.dumps(data))
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    await websocket.send_text(json.dumps({"type": "ping"}))
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"[WS orderbook] Error: {e}")
        finally:
            if engine and q:
                engine.unsubscribe_orderbook(t, q)

    @app.websocket("/ws/grid-ladder/events/{ticker}")
    async def ws_grid_events(websocket: WebSocket, ticker: str):
        """Stream grid ladder events (fill, order, cancel, error) to frontend"""
        await websocket.accept()
        t = ticker.upper()
        engine = None
        q = None
        try:
            engine = await get_or_create_engine(t)
            q = engine.subscribe_events(t)

            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    await websocket.send_text(json.dumps(event))
                except asyncio.TimeoutError:
                    await websocket.send_text(json.dumps({"type": "ping"}))
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"[WS events] Error: {e}")
        finally:
            if engine and q:
                engine.unsubscribe_events(t, q)

    @app.get("/grid-ladder", response_class=HTMLResponse)
    async def grid_ladder_page():
        html_path = os.path.join(static_dir, "grid_ladder.html")
        if os.path.exists(html_path):
            return FileResponse(html_path)
        return HTMLResponse("<h1>Grid Ladder UI not found</h1>", status_code=404)

    return app
