
import os
import sys
import asyncio
import logging
import time
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.api.database import get_database
from src.core import kis_auth as ka

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
START_DATE = "20260115"
END_DATE = "20260126" # Covers up to today
DELAY = 0.3 # KIS limits (approx 20 requests per sec, safest is 0.1-0.2 per call). 
# We have 2500 tickers. 4 calls per ticker = 10000 calls. 
# 0.3s delay => 3000s (50 mins). 
# We might need to go faster or accept it takes time. 
# Real env allows 20/sec transactions.
# 4 calls * 2000 tickers = 8000 calls. 
# At 10 calls/sec -> 800 seconds (13 mins). 
# Let's try 0.1s delay between tickers.

class DataBackfiller:
    def __init__(self):
        self.db = get_database()
        ka.auth() # Initialize API token

    async def get_all_tickers(self):
        rows = await self.db.fetch_all("SELECT ticker, name, listed_shares FROM stock_info")
        return {r['ticker']: r for r in rows}

    async def backfill_price(self, ticker, start, end):
        # TR: FHKST03010100 (Daily Chart)
        url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": end,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0"
        }
        
        res = ka._url_fetch(url, tr_id, "", params)
        if not res.isOK():
            return 0
        
        output = res.getBody().output2
        if not output:
            return 0
            
        data_list = []
        for item in output:
            dt = item.get('stck_bsop_date')
            if not dt: continue
            
            fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
            
            # Extract fields
            open_p = float(item.get('stck_oprc', 0))
            high_p = float(item.get('stck_hgpr', 0))
            low_p = float(item.get('stck_lwpr', 0))
            close_p = float(item.get('stck_clpr', 0))
            vol = int(item.get('acml_vol', 0))
            
            # Estimate market cap since specific daily cap might not be in this TR
            # Use 'hts_avls' if available? output2 usually doesn't have it. output1 has current.
            # We can leave market_cap 0 or update later.
            # actually daily_price needs market_cap for sorting?
            # Let's rely on update triggering if we can, or just set 0.
            
            change_rate = 0.0 # Calculate or ignore
            # daily_price usually needs change_rate.
            # output item has 'flng_cls_code' etc? No.
            # Let's try to get change rate if possible.
            # 'prdy_ctrt' might be in output.
            # checking domestic_stock_functions for itemchartprice...
            # The item usually has 'diff' not rate.
            # Let's just insert OHLCV which is critical.
            
            data_list.append((fmt_date, ticker, open_p, high_p, low_p, close_p, vol))
            
        if data_list:
            await self.db.execute_many("""
                INSERT INTO daily_price (date, ticker, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
            """, data_list)
            
        return len(data_list)

    async def backfill_investor(self, ticker):
        # TR: FHKST01010900 (Investor Daily)
        url = "/uapi/domestic-stock/v1/quotations/inquire-investor"
        tr_id = "FHKST01010900"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker
        }
        
        res = ka._url_fetch(url, tr_id, "", params)
        if not res.isOK():
            return 0
            
        output = res.getBody().output
        if not output:
            return 0
            
        data_list = []
        for item in output:
            dt = item.get('stck_bsop_date')
            if not dt: continue
            
            # Filter Range
            if dt < START_DATE or dt > END_DATE:
                continue
                
            fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
            
            frgn = int(item.get('frgn_ntby_tr_pbmn', 0) or 0)
            orgn = int(item.get('orgn_ntby_tr_pbmn', 0) or 0)
            prsn = int(item.get('prsn_ntby_tr_pbmn', 0) or 0)
            frgn_ratio = float(item.get('frgn_hold_rate', 0) or 0)
            
            data_list.append((fmt_date, ticker, frgn, orgn, prsn, frgn_ratio))
            
        if data_list:
            await self.db.execute_many("""
                INSERT INTO daily_investor (date, ticker, foreign_net, inst_net, retail_net, foreign_ratio)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    foreign_net=excluded.foreign_net, inst_net=excluded.inst_net,
                    retail_net=excluded.retail_net, foreign_ratio=excluded.foreign_ratio
            """, data_list)
            
        return len(data_list)

    async def backfill_short_credit(self, ticker, start, end):
        # 1. Short Sale (FHPST04830000)
        url_short = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
        tr_short = "FHPST04830000"
        params_short = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": end
        }
        
        short_data = {}
        res = ka._url_fetch(url_short, tr_short, "", params_short)
        if res.isOK():
            output = res.getBody().output2
            if output:
                for item in output:
                    dt = item.get('stck_bsop_date')
                    if not dt: continue
                    fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
                    
                    short_data[fmt_date] = {
                        'short_volume': int(item.get('ssts_cntg_qty', 0) or 0),
                        'short_balance': int(item.get('acml_ssts_cntg_qty', 0) or 0),
                        'short_ratio': float(item.get('ssts_vol_rlim', 0) or 0)
                    }

        # 2. Credit Balance (FHPST04760000)
        # Returns 30 days from recent.
        url_credit = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"
        tr_credit = "FHPST04760000"
        params_credit = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20476",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": end # Query until end date (returns previous 30 days)
        }
        
        credit_data = {}
        res = ka._url_fetch(url_credit, tr_credit, "", params_credit)
        if res.isOK():
            output = res.getBody().output
            if output:
                 for item in output:
                    dt = item.get('stck_bsop_date')
                    if not dt: continue
                    # Filter Range
                    if dt < start or dt > end: continue
                    
                    fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
                    
                    credit_data[fmt_date] = {
                        'credit_balance': int(item.get('whol_loan_rmnd_stcn', 0) or 0),
                        'credit_ratio': float(item.get('whol_loan_rmnd_rate', 0) or 0)
                    }
        
        # Merge and Insert
        all_dates = set(short_data.keys()) | set(credit_data.keys())
        data_list = []
        for d in all_dates:
            s = short_data.get(d, {})
            c = credit_data.get(d, {})
            
            data_list.append((
                d, ticker,
                s.get('short_volume', 0), s.get('short_ratio', 0), s.get('short_balance', 0),
                c.get('credit_balance', 0), c.get('credit_ratio', 0)
            ))
            
        if data_list:
            await self.db.execute_many("""
                INSERT INTO daily_short_credit 
                (date, ticker, short_volume, short_ratio, short_balance, credit_balance, credit_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    short_volume=excluded.short_volume, short_ratio=excluded.short_ratio,
                    short_balance=excluded.short_balance, credit_balance=excluded.credit_balance,
                    credit_ratio=excluded.credit_ratio
            """, data_list)
            
        return len(data_list)

    async def run(self):
        logger.info(f"Starting backfill from {START_DATE} to {END_DATE}")
        
        stocks = await self.get_all_tickers()
        tickers = list(stocks.keys())
        total = len(tickers)
        
        logger.info(f"Target tickers: {total}")
        
        for i, ticker in enumerate(tickers):
            try:
                p_cnt = await self.backfill_price(ticker, START_DATE, END_DATE)
                i_cnt = await self.backfill_investor(ticker)
                s_cnt = await self.backfill_short_credit(ticker, START_DATE, END_DATE)
                
                if i % 10 == 0:
                     logger.info(f"[{i}/{total}] {ticker}: P({p_cnt}) I({i_cnt}) S({s_cnt})")
                
                # Small delay to respect rate limit
                await asyncio.sleep(0.1) # 10/sec
                
            except Exception as e:
                logger.error(f"Failed {ticker}: {e}")
                
        logger.info("Backfill Complete")

if __name__ == "__main__":
    backfiller = DataBackfiller()
    asyncio.run(backfiller.run())
