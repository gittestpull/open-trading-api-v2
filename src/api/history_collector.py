# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
import pandas as pd
from .database import Database, get_database
from .stock_master import get_stock_master_service
import kis_auth

logger = logging.getLogger(__name__)

API_DELAY_SECONDS = 0.5

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
        today = datetime.now().strftime("%Y-%m-%d")
        return await self.collect_minute_for_date(ticker, today)

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

    async def collect_overseas_history(self, ticker: str, exchange: str, start_date: str, end_date: str, timeframe: str = "D") -> dict:
        """Collect overseas historical data."""
        # Exchange Code Mapping (AI -> KIS)
        # AI: NASDAQ, NYSE, AMEX, TOKYO, SHANGHAI, SHENZHEN, HONGKONG
        # KIS: NAS, NYS, AMS, TSE, SHS, SZS, HKS
        ex_map = {
            "NASDAQ": "NAS", "NYSE": "NYS", "AMEX": "AMS",
            "TOKYO": "TSE", "JP": "TSE",
            "SHANGHAI": "SHS", "SHENZHEN": "SZS", "CHINA": "SHS", # Default to SHS if generic
            "HONGKONG": "HKS", "HK": "HKS",
            "HANOI": "HASE", "HOCHIMINH": "VNSE", "VN": "VNSE"
        }
        
        kis_ex = ex_map.get(exchange.upper(), exchange.upper())
        if len(kis_ex) > 3 and kis_ex not in ["HASE", "VNSE"]:
             # Heuristic: if mapped value is still long (e.g. "KOSPI"), maybe it's domestic or unmapped
             # But here we assume it's overseas.
             pass

        # Determine TR_ID and URL
        url = "/uapi/overseas-price/v1/quotations/dailyprice"
        if kis_ex in ["NAS", "NYS", "AMS"]:
            tr_id = "HHDFS76200200" # US Daily
        else:
            tr_id = "TTTS30270400" # Other Overseas Daily (JP, CN, HK, VN)

        # Pagination/Loop logic
        # Overseas daily price usually returns 100 records. KIS doesn't support date range strictly for some overseas APIs,
        # often it returns 'n' days from today or end date.
        # However, `dailyprice` endpoint typically takes specific parameters.
        
        # Checking parameters for `HHDFS76200200` (US)
        # SYMB, EXCD, GUBN(0:D, 1:W, 2:M), BYMD(Base Date), MODP(0:No, 1:Yes)
        # It returns 100 records *before* BYMD. So we need to loop backwards.
        
        gubn = {'D': '0', 'W': '1', 'M': '2'}.get(timeframe, '0')
        
        current_date = end_date # YYYYMMDD
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        total_count = 0
        
        # We limit to 1 year approx (3 calls of 100 days) to be safe/fast
        max_calls = 5 
        
        for _ in range(max_calls):
            params = {
                "AUTH": "",
                "EXCD": kis_ex,
                "SYMB": ticker,
                "GUBN": gubn,
                "BYMD": current_date,
                "MODP": "1" # Adjusted price
            }
            
            res = kis_auth._url_fetch(url, tr_id, "", params)
            
            if not res.isOK():
                logger.error(f"Overseas API error for {ticker}({kis_ex}): {res.getErrorMessage()}")
                return {"error": res.getErrorMessage()}
                
            output = res.getBody().output2
            if not output:
                break
                
            page_count = 0
            oldest_date = None
            
            for item in output:
                dt = item.get('xymd') # Date key for US/Overseas
                if not dt: continue
                
                item_dt = datetime.strptime(dt, "%Y%m%d")
                if item_dt < start_dt:
                    continue
                    
                oldest_date = dt
                fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
                
                # Price keys are different for overseas
                # clos, sign, diff, rate, open, high, low, tvol
                open_p = float(item.get('open', 0))
                high_p = float(item.get('high', 0))
                low_p = float(item.get('low', 0))
                close_p = float(item.get('clos', 0))
                vol = int(item.get('tvol', 0))
                
                await self.db.execute("""
                    INSERT INTO price_history (ticker, datetime, timeframe, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker, datetime, timeframe) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume
                """, (ticker, fmt_date, timeframe, open_p, high_p, low_p, close_p, vol))
                page_count += 1
                
            total_count += page_count
            
            if not oldest_date or page_count == 0:
                break
                
            # Next loop starts from day before oldest_date
            next_end_dt = datetime.strptime(oldest_date, "%Y%m%d") - timedelta(days=1)
            if next_end_dt < start_dt:
                break
                
            current_date = next_end_dt.strftime("%Y%m%d")
            await asyncio.sleep(API_DELAY_SECONDS)
            
        return {"status": "success", "count": total_count, "ticker": ticker, "exchange": kis_ex}

    async def collect_sector_history(self, sector_data: dict, days: int = 365) -> dict:
        """Collect history for all stocks in sector data."""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        results = {}
        
        # Iterate over regions: KR, US, JP, CN
        for region, stocks in sector_data.items():
            if region in ["sector", "updated_at"]: continue
            if not isinstance(stocks, list): continue
            
            for stock in stocks:
                ticker = stock.get('ticker')
                exchange = stock.get('exchange', '') # e.g. "NASDAQ", "KOSPI"
                
                if not ticker: continue
                
                # Determine if domestic or overseas
                is_domestic = region == "KR" or exchange.upper() in ["KOSPI", "KOSDAQ", "KONEX"]
                
                try:
                    if is_domestic:
                        # Clean ticker for KR (remove KS/KQ if present)
                        clean_ticker = ticker
                        res = await self.collect_history(clean_ticker, start_date, end_date, "D")
                    else:
                        # For overseas, we need exchange code.
                        # If exchange is empty, try to infer from region
                        if not exchange:
                            if region == "US": exchange = "NAS" # Default attempt
                            elif region == "JP": exchange = "TSE"
                            elif region == "CN": exchange = "SHS"
                        
                        res = await self.collect_overseas_history(ticker, exchange, start_date, end_date, "D")
                    
                    results[ticker] = res
                except Exception as e:
                    logger.error(f"Failed to collect {ticker}: {e}")
                    results[ticker] = {"error": str(e)}
                
                await asyncio.sleep(API_DELAY_SECONDS)
                
        return {"status": "completed", "results": results}

    async def get_history(self, ticker: str, timeframe: str = 'D', limit: int = 100):
        return await self.db.fetch_all("""
            SELECT * FROM price_history 
            WHERE ticker = ? AND timeframe = ?
            ORDER BY datetime DESC
            LIMIT ?
        """, (ticker, timeframe, limit))

    async def collect_bulk_history(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframes: list[str],
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ) -> dict:
        stock = await self.stock_service.get_stock_info(ticker)
        if not stock:
            stocks = await self.stock_service.search_stocks(ticker)
            if stocks:
                ticker = stocks[0]['ticker']
            else:
                return {"error": "Stock not found", "ticker": ticker}

        results = {}
        total_count = 0

        for tf in timeframes:
            if tf == '1m':
                result = await self.collect_minute_history(ticker)
                results[tf] = result
                total_count += result.get('count', 0)
                continue

            tf_count = await self._collect_with_pagination(
                ticker, start_date, end_date, tf, on_progress
            )
            results[tf] = {"count": tf_count, "status": "success"}
            total_count += tf_count
            await asyncio.sleep(API_DELAY_SECONDS)

        return {
            "status": "success",
            "ticker": ticker,
            "total_count": total_count,
            "by_timeframe": results
        }

    async def _collect_with_pagination(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        timeframe: str,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ) -> int:
        url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"
        period_code = {'D': 'D', 'W': 'W', 'M': 'M'}.get(timeframe, 'D')

        total_count = 0
        current_end = end_date
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        page = 0
        max_pages = 20

        while page < max_pages:
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": current_end,
                "FID_PERIOD_DIV_CODE": period_code,
                "FID_ORG_ADJ_PRC": "0"
            }

            res = kis_auth._url_fetch(url, tr_id, "", params)
            if not res.isOK():
                logger.error(f"API error for {ticker}/{timeframe}: {res.getErrorMessage()}")
                break

            output = res.getBody().output2
            if not output:
                break

            page_count = 0
            oldest_date = None

            for item in output:
                dt = item.get('stck_bsop_date')
                if not dt:
                    continue

                item_dt = datetime.strptime(dt, "%Y%m%d")
                if item_dt < start_dt:
                    continue

                fmt_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:]}"
                oldest_date = dt

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
                page_count += 1

            total_count += page_count

            if on_progress:
                on_progress(timeframe, page + 1, total_count)

            if not oldest_date or page_count < 50:
                break

            next_end_dt = datetime.strptime(oldest_date, "%Y%m%d") - timedelta(days=1)
            if next_end_dt < start_dt:
                break

            current_end = next_end_dt.strftime("%Y%m%d")
            page += 1
            await asyncio.sleep(API_DELAY_SECONDS)

        logger.info(f"Collected {total_count} {timeframe} records for {ticker}")
        return total_count

    async def collect_minute_for_date(self, ticker: str, date_str: str) -> dict:
        url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        tr_id = "FHKST03010200"

        count = 0
        current_time = "153000"
        seen_times = set()

        for _ in range(20):
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_HOUR_1": current_time,
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": ""
            }

            res = kis_auth._url_fetch(url, tr_id, "", params)
            if not res.isOK():
                logger.error(f"Minute API error for {ticker}: {res.getErrorMessage()}")
                break

            output = res.getBody().output2
            if not output:
                break

            oldest_time = None
            new_count = 0
            for item in output:
                stck_time = item.get('stck_cntg_hour')
                if not stck_time or stck_time in seen_times:
                    continue

                seen_times.add(stck_time)
                dt_str = f"{date_str} {stck_time[:2]}:{stck_time[2:4]}:{stck_time[4:]}"
                oldest_time = stck_time

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
                new_count += 1

            if not oldest_time or oldest_time <= "090000" or new_count == 0:
                break

            h = int(oldest_time[:2])
            m = int(oldest_time[2:4])
            m -= 1
            if m < 0:
                m = 59
                h -= 1
            current_time = f"{h:02d}{m:02d}00"
            
            await asyncio.sleep(API_DELAY_SECONDS)

        return {"status": "success", "count": count, "ticker": ticker, "date": date_str}

    async def get_coverage_stats(self, ticker: str, timeframe: str = 'D'):
        """Returns a list of dates that have data for the given ticker."""
        if timeframe == 'H': 
            logger.info(f"[History] Fetching Human Index coverage for {ticker}")
            rows = await self.db.fetch_all("""
                SELECT date as datetime FROM human_index
                WHERE ticker = ?
                ORDER BY date ASC
            """, (ticker,))
            logger.info(f"[History] Found {len(rows)} rows for {ticker} (Human Index)")
        else:
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

    async def get_history_summary(self):
        """Returns summary of collected data counts per ticker and timeframe."""
        rows = await self.db.fetch_all("""
            SELECT ticker, timeframe, count(*) as count, min(datetime) as start_date, max(datetime) as end_date
            FROM price_history 
            GROUP BY ticker, timeframe
            ORDER BY ticker, timeframe
        """)
        
        # Enrich with stock names
        summary = []
        for r in rows:
            stock = await self.stock_service.get_stock_info(r['ticker'])
            name = stock['name'] if stock else 'Unknown'
            summary.append({
                "ticker": r['ticker'],
                "name": name,
                "timeframe": r['timeframe'],
                "count": r['count'],
                "start_date": r['start_date'],
                "end_date": r['end_date']
            })
        return summary

_history_collector: HistoryCollector = None

def get_history_collector() -> HistoryCollector:
    global _history_collector
    if _history_collector is None:
        _history_collector = HistoryCollector()
    return _history_collector
