# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .database import Database, get_database
from .stock_master import StockMasterService, get_stock_master_service
from .log_buffer import get_log_buffer

logger = logging.getLogger(__name__)


class DataCollector:
    
    def __init__(self, db: Database = None, is_live: bool = False):
        self.db = db or get_database()
        self.is_live = is_live
        self._kis_initialized = False
        self._ka = None
        self._functions = None
        self._log_buffer = get_log_buffer()
    
    async def get_collected_tickers_for_today(self, table: str) -> set:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = await self.db.fetch_all(
            f"SELECT ticker FROM {table} WHERE date = ?", (today,)
        )
        return {r['ticker'] for r in rows}
    
    def _init_kis(self):
        if self._kis_initialized:
            return True
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, base_dir)
            sys.path.insert(0, os.path.join(base_dir, "examples_user"))
            sys.path.insert(0, os.path.join(base_dir, "examples_user", "domestic_stock"))
            
            import kis_auth as ka
            self._ka = ka
            
            svr = "prod" if self.is_live else "vps"
            ka.auth(svr=svr, product="01")
            
            import domestic_stock_functions as dsf
            self._functions = dsf
            
            self._kis_initialized = True
            logger.info(f"[Collector] KIS API initialized (mode: {svr})")
            return True
        except Exception as e:
            logger.error(f"[Collector] KIS API init failed: {e}")
            return False
    
    def collect_price_sync(self, ticker: str) -> Optional[Dict]:
        if not self._init_kis():
            return None
        
        try:
            df = self._functions.inquire_price("real" if self.is_live else "demo", "J", ticker)
            if df.empty:
                return None
            
            row = df.iloc[0]
            # Helper to parse values that may have decimals (e.g., '4950.00')
            def safe_int(val):
                try:
                    return int(float(val or 0))
                except (ValueError, TypeError):
                    return 0
            
            def safe_float(val):
                try:
                    return float(val or 0)
                except (ValueError, TypeError):
                    return 0.0
            
            return {
                'ticker': ticker,
                'date': datetime.now().strftime("%Y-%m-%d"),
                'open': safe_int(row.get('stck_oprc', 0)),
                'high': safe_int(row.get('stck_hgpr', 0)),
                'low': safe_int(row.get('stck_lwpr', 0)),
                'close': safe_int(row.get('stck_prpr', 0)),
                'volume': safe_int(row.get('acml_vol', 0)),
                'market_cap': safe_int(row.get('hts_avls', 0)),
                'change_rate': safe_float(row.get('prdy_ctrt', 0)),
                'per': safe_float(row.get('per', 0)),
                'pbr': safe_float(row.get('pbr', 0)),
                'eps': safe_int(row.get('eps', 0)),
                'bps': safe_int(row.get('bps', 0)),
            }
        except Exception as e:
            logger.debug(f"[Collector] Price fetch failed for {ticker}: {e}")
            return None
    
    def collect_investor_sync(self, ticker: str) -> Optional[Dict]:
        if not self._init_kis():
            return None
        
        try:
            if hasattr(self._functions, 'inquire_investor'):
                env_dv = "real" if self.is_live else "demo"
                df = self._functions.inquire_investor(env_dv, "J", ticker)
                if df.empty:
                    return None
                row = df.iloc[0]
                
                # Debug logging for columns
                # logger.debug(f"Investor cols for {ticker}: {row.index.tolist()}")
                
                def safe_int(val):
                    try:
                        return int(float(val or 0))
                    except (ValueError, TypeError):
                        return 0
                
                def safe_float(val):
                    try:
                        return float(val or 0)
                    except (ValueError, TypeError):
                        return 0.0
                
                return {
                    'ticker': ticker,
                    'date': datetime.now().strftime("%Y-%m-%d"),
                    'foreign_net': safe_int(row.get('frgn_ntby_qty', 0)),
                    'inst_net': safe_int(row.get('orgn_ntby_qty', 0)),
                    'retail_net': safe_int(row.get('prsn_ntby_qty', 0)),
                    'foreign_ratio': safe_float(row.get('frgn_hold_rate', 0)),
                }
        except Exception as e:
            logger.debug(f"[Collector] Investor fetch failed for {ticker}: {e}")
        return None

    def collect_short_credit_sync(self, ticker: str) -> Optional[Dict]:
        if not self._init_kis():
            return None
        
        try:
            today = datetime.now().strftime("%Y%m%d")
            
            # 공매도 조회
            # output1은 종합정보, output2는 일별추이
            df_short_sum, df_short_daily = self._functions.daily_short_sale("J", ticker, today, today)
            
            short_volume = 0
            short_balance = 0
            short_ratio = 0.0
            
            # 일별 데이터 확인 (오늘자)
            if not df_short_daily.empty:
                row = df_short_daily.iloc[0]
                # KIS API 필드명 매핑 (문서/예제 기준 추정)
                # ssts_cnt: 공매도수량, ssts_bal_qty: 공매도잔고수량, ssts_rt: 공매도율
                short_volume = int(row.get('ssts_cnt', 0))
                short_balance = int(row.get('ssts_bal_qty', 0))
                short_ratio = float(row.get('ssts_rt', 0))
            
            # 신용 조회
            # daily_credit_balance는 일별 추이를 반환
            df_credit = self._functions.daily_credit_balance("J", "20476", ticker, today)
            
            credit_balance = 0
            credit_ratio = 0.0
            
            if not df_credit.empty:
                row = df_credit.iloc[0]
                # loan_bal: 융자잔고, loan_rt: 융자비율
                credit_balance = int(row.get('loan_bal', 0)) # 보통 수량 단위
                credit_ratio = float(row.get('loan_rt', 0))
            
            return {
                'ticker': ticker,
                'date': datetime.now().strftime("%Y-%m-%d"),
                'short_volume': short_volume,
                'short_ratio': short_ratio,
                'short_balance': short_balance,
                'credit_balance': credit_balance,
                'credit_ratio': credit_ratio
            }
        except Exception as e:
            logger.debug(f"[Collector] Short/Credit fetch failed for {ticker}: {e}")
            return None

    async def collect_all_prices(self, tickers: List[str], delay: float = 0.5, force: bool = False) -> Dict:
        start_time = time.time()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        price_data = []
        stats_data = []
        
        if force:
            remaining = tickers
            skipped_count = 0
        else:
            collected = await self.get_collected_tickers_for_today("daily_price")
            remaining = [t for t in tickers if t not in collected]
            skipped_count = len(tickers) - len(remaining)
        
        total = len(remaining)
        now = datetime.now().strftime('%H:%M')
        mode = "[FORCE]" if force else ""
        log_msg = f"[{now}] {mode} Price collection: {total} remaining ({skipped_count} already collected)"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped_count, 'duration': 0}
        
        for i, ticker in enumerate(remaining):
            if i > 0 and i % 50 == 0:
                progress = i * 100 // total
                now = datetime.now().strftime('%H:%M')
                log_msg = f"[{now}] Price: {i}/{total} ({progress}%)"
                logger.info(f"[Collector] {log_msg}")
                self._log_buffer.add_sync(log_msg)
            
            result = self.collect_price_sync(ticker)
            if result:
                price_data.append({
                    'ticker': result['ticker'],
                    'date': result['date'],
                    'open': result['open'],
                    'high': result['high'],
                    'low': result['low'],
                    'close': result['close'],
                    'volume': result['volume'],
                    'market_cap': result['market_cap'],
                    'change_rate': result['change_rate'],
                })
                
                if result.get('per') or result.get('pbr'):
                    stats_data.append({
                        'ticker': result['ticker'],
                        'date': result['date'],
                        'per': result.get('per'),
                        'pbr': result.get('pbr'),
                        'eps': result.get('eps'),
                        'bps': result.get('bps'),
                        'roe': None,
                        'dividend_yield': None,
                    })
                
                success_count += 1
            else:
                failed_count += 1
            
            await asyncio.sleep(delay)
        
        if price_data:
            await self.db.upsert_daily_price(price_data)
        if stats_data:
            await self.db.upsert_daily_stats(stats_data)
        
        duration = time.time() - start_time
        await self.db.log_collection("price", total, success_count, failed_count, duration)
        
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] Price complete: {success_count}/{total} ({skipped_count} skipped) in {duration:.1f}s"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'duration': duration
        }
    
    async def collect_all_investors(self, tickers: List[str], delay: float = 0.5, force: bool = False) -> Dict:
        start_time = time.time()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        investor_data = []
        
        if force:
            remaining = tickers
            skipped_count = 0
        else:
            collected = await self.get_collected_tickers_for_today("daily_investor")
            remaining = [t for t in tickers if t not in collected]
            skipped_count = len(tickers) - len(remaining)
        
        total = len(remaining)
        now = datetime.now().strftime('%H:%M')
        mode = "[FORCE]" if force else ""
        log_msg = f"[{now}] {mode} Investor collection: {total} remaining ({skipped_count} already collected)"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped_count, 'duration': 0}
        
        for i, ticker in enumerate(remaining):
            if i > 0 and i % 50 == 0:
                progress = i * 100 // total
                now = datetime.now().strftime('%H:%M')
                log_msg = f"[{now}] Investor: {i}/{total} ({progress}%)"
                logger.info(f"[Collector] {log_msg}")
                self._log_buffer.add_sync(log_msg)
            
            result = self.collect_investor_sync(ticker)
            if result:
                investor_data.append(result)
                success_count += 1
            else:
                failed_count += 1
            
            await asyncio.sleep(delay)
        
        if investor_data:
            await self.db.upsert_daily_investor(investor_data)
        
        duration = time.time() - start_time
        await self.db.log_collection("investor", total, success_count, failed_count, duration)
        
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] Investor complete: {success_count}/{total} ({skipped_count} skipped) in {duration:.1f}s"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'duration': duration
        }
    
    async def collect_all_short_credit(self, tickers: List[str], delay: float = 0.5, force: bool = False) -> Dict:
        start_time = time.time()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        data = []
        
        if force:
            remaining = tickers
            skipped_count = 0
        else:
            collected = await self.get_collected_tickers_for_today("daily_short_credit")
            remaining = [t for t in tickers if t not in collected]
            skipped_count = len(tickers) - len(remaining)
        
        total = len(remaining)
        now = datetime.now().strftime('%H:%M')
        mode = "[FORCE]" if force else ""
        log_msg = f"[{now}] {mode} Short/Credit collection: {total} remaining ({skipped_count} already collected)"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped_count, 'duration': 0}
        
        for i, ticker in enumerate(remaining):
            if i > 0 and i % 50 == 0:
                progress = i * 100 // total
                now = datetime.now().strftime('%H:%M')
                log_msg = f"[{now}] Short/Credit: {i}/{total} ({progress}%)"
                logger.info(f"[Collector] {log_msg}")
                self._log_buffer.add_sync(log_msg)
            
            result = self.collect_short_credit_sync(ticker)
            if result:
                data.append(result)
                success_count += 1
            else:
                failed_count += 1
            
            await asyncio.sleep(delay)
        
        if data:
            await self.db.upsert_daily_short_credit(data)
        
        duration = time.time() - start_time
        await self.db.log_collection("short_credit", total, success_count, failed_count, duration)
        
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] Short/Credit complete: {success_count}/{total} in {duration:.1f}s"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'duration': duration
        }
    
    async def run_daily_collection(self, collect_price: bool = True, collect_investor: bool = True, collect_short: bool = True, force: bool = False) -> Dict:
        now = datetime.now().strftime('%H:%M')
        mode = "[FORCE] " if force else ""
        log_msg = f"[{now}] {mode}Starting daily collection..."
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        stock_service = get_stock_master_service()
        await stock_service.load_all_stocks()
        tickers = await stock_service.get_all_tickers()
        
        if not tickers:
            logger.error("[Collector] No tickers found")
            return {'error': 'No tickers found'}
        
        results = {}
        
        if collect_price:
            results['price'] = await self.collect_all_prices(tickers, force=force)
        
        if collect_investor:
            results['investor'] = await self.collect_all_investors(tickers, force=force)
            
        if collect_short:
            results['short_credit'] = await self.collect_all_short_credit(tickers, force=force)
        
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] Daily collection complete"
        logger.info(f"[Collector] {log_msg}: {results}")
        self._log_buffer.add_sync(log_msg)
        return results


_collector_instance: Optional[DataCollector] = None

def get_collector(is_live: bool = False) -> DataCollector:
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = DataCollector(is_live=is_live)
    return _collector_instance
