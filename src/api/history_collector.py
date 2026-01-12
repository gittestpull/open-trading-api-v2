# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
from .database import Database, get_database
from .stock_master import get_stock_master_service
import kis_auth

logger = logging.getLogger(__name__)

class HistoryCollector:
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.stock_service = get_stock_master_service()
        kis_auth.auth()

    async def init_db(self):
        """Create price_history table if not exists."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                ticker TEXT,
                datetime TEXT,
                timeframe TEXT, -- 'D', 'W', 'M', '1m'
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, datetime, timeframe)
            );
        """)

    async def collect_minute_history(self, ticker: str, base_time: str = "153000"):
        """Collects intraday minute data (today) from KIS API."""
        url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        tr_id = "FHKST03010200"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_HOUR_1": base_time, 
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_ETC_CLS_CODE": ""
        }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        count = 0
        if res.isOK():
            output = res.getBody().output2
            today = datetime.now().strftime("%Y-%m-%d")
            
            for item in output:
                stck_time = item.get('stck_cntg_hour') # HHMMSS
                if not stck_time: continue
                
                # Format: YYYY-MM-DD HH:MM:SS
                dt_str = f"{today} {stck_time[:2]}:{stck_time[2:4]}:{stck_time[4:]}"
                
                open_p = float(item.get('stck_oprc', 0))
                high_p = float(item.get('stck_hgpr', 0))
                low_p = float(item.get('stck_lwpr', 0))
                close_p = float(item.get('stck_prpr', 0))
                vol = int(item.get('cntg_vol', 0))
                
                await self.db.execute("""
                    INSERT INTO price_history (ticker, datetime, timeframe, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, datetime, timeframe) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume
                """, (ticker, dt_str, '1m', open_p, high_p, low_p, close_p, vol))
                count += 1
                
            return {"status": "success", "count": count, "ticker": ticker, "type": "1m"}
        return {"error": res.getErrorMessage()}

    async def collect_history(self, ticker: str, start_date: str, end_date: str, timeframe: str = "D", time: str = "153000"):
        """Collect historical data (D/W/M/1m)."""
        # Ensure ticker is resolved
        stock = await self.stock_service.get_stock_info(ticker)
        if not stock:
            stocks = await self.stock_service.search_stocks(ticker)
            if stocks:
                ticker = stocks[0]['ticker']
            else:
                return {"error": "Stock not found"}

        if timeframe == '1m':
            return await self.collect_minute_history(ticker, time)

        period_code = {'D': 'D', 'W': 'W', 'M': 'M'}.get(timeframe, 'D')
        url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period_code,
            "FID_ORG_ADJ_PRC": "0"
        }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        count = 0
        if res.isOK():
            output = res.getBody().output2
            for item in output:
                dt = item.get('stck_bsop_date')
                if not dt: continue
                fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
                
                open_p = float(item.get('stck_oprc', 0))
                high_p = float(item.get('stck_hgpr', 0))
                low_p = float(item.get('stck_lwpr', 0))
                close_p = float(item.get('stck_clpr', 0))
                vol = int(item.get('acml_vol', 0))

                await self.db.execute("""
                    INSERT INTO price_history (ticker, datetime, timeframe, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, datetime, timeframe) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume
                """, (ticker, fmt_date, timeframe, open_p, high_p, low_p, close_p, vol))
                count += 1
            
            return {"status": "success", "count": count, "ticker": ticker}
        else:
            msg = res.getErrorMessage()
            logger.error(f"Failed to fetch history for {ticker}: {msg}")
            return {"error": msg}

    async def get_history(self, ticker: str, timeframe: str = 'D', limit: int = 100):
        return await self.db.fetch_all("""
            SELECT * FROM price_history 
            WHERE ticker = ? AND timeframe = ?
            ORDER BY datetime DESC
            LIMIT ?
        """, (ticker, timeframe, limit))

_history_collector: HistoryCollector = None

def get_history_collector() -> HistoryCollector:
    global _history_collector
    if _history_collector is None:
        _history_collector = HistoryCollector()
    return _history_collector

    async def get_coverage_stats(self, ticker: str, timeframe: str = 'D'):
        """Returns a list of dates that have data for the given ticker."""
        rows = await self.db.fetch_all("""
            SELECT datetime FROM price_history 
            WHERE ticker = ? AND timeframe = ?
            ORDER BY datetime ASC
        """, (ticker, timeframe))
        
        # Extract just the date part (YYYY-MM-DD) for grouping
        dates = []
        for r in rows:
            dt = r['datetime']
            # If datetime includes time (YYYY-MM-DD HH:MM:SS), take just date
            if ' ' in dt:
                dt = dt.split(' ')[0]
            dates.append(dt)
            
        return {"ticker": ticker, "timeframe": timeframe, "dates": sorted(list(set(dates)))}
