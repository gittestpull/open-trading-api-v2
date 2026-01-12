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
        kis_auth.auth() # Ensure auth is called

    async def init_db(self):
        """Create price_history table if not exists."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                ticker TEXT,
                datetime TEXT,
                timeframe TEXT, -- 'D', 'W', 'M', '1m', '5m'
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, datetime, timeframe)
            );
        """)

    async def collect_history(self, ticker: str, start_date: str, end_date: str, timeframe: str = 'D'):
        """
        Collect historical data from KIS API.
        ticker: Stock code (e.g. 005930)
        start_date: YYYYMMDD
        end_date: YYYYMMDD
        timeframe: 'D' (Daily), 'W' (Weekly), 'M' (Monthly)
        """
        # Ensure ticker is resolved
        stock = await self.stock_service.get_stock_info(ticker)
        if not stock:
            # Try to resolve by name if not found
            stocks = await self.stock_service.search_stocks(ticker)
            if stocks:
                ticker = stocks[0]['ticker']
            else:
                return {"error": "Stock not found"}

        period_code = {
            'D': 'D', # Daily
            'W': 'W', # Weekly
            'M': 'M'  # Monthly
        }.get(timeframe, 'D')

        # KIS API URL for Daily/Weekly/Monthly
        url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"

        # KIS API requests start/end date logic
        # Note: KIS usually returns data backwards from end_date. 
        # We might need to handle pagination if range is huge, but KIS allows ~100 rows per call.
        # For simple implementation, we request the range.

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date,  # Start YYYYMMDD
            "FID_INPUT_DATE_2": end_date,    # End YYYYMMDD
            "FID_PERIOD_DIV_CODE": period_code,
            "FID_ORG_ADJ_PRC": "0" # 0: Adjusted price, 1: Unadjusted
        }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        
        count = 0
        if res.isOK():
            output = res.getBody().output2
            # output2 contains the list of prices
            for item in output:
                dt = item.get('stck_bsop_date')
                if not dt: continue
                
                # Format date to YYYY-MM-DD
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
