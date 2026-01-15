# -*- coding: utf-8 -*-
import os
import sys
import asyncio
import time
import logging
from datetime import datetime, timedelta
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
    
    async def get_existing_short_credit_data(self, tickers: List[str]) -> Dict[str, Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        if not tickers:
            return {}
        placeholders = ','.join(['?' for _ in tickers])
        rows = await self.db.fetch_all(
            f"SELECT ticker, short_ratio, credit_ratio FROM daily_short_credit WHERE date = ? AND ticker IN ({placeholders})",
            (today, *tickers)
        )
        return {r['ticker']: {'short_ratio': r['short_ratio'], 'credit_ratio': r['credit_ratio']} for r in rows}
    
    def _has_meaningful_change(self, old_data: Dict, new_data: Dict, threshold: float = 0.01) -> bool:
        if not old_data:
            return True
        old_short = old_data.get('short_ratio', 0) or 0
        old_credit = old_data.get('credit_ratio', 0) or 0
        new_short = new_data.get('short_ratio', 0) or 0
        new_credit = new_data.get('credit_ratio', 0) or 0
        
        if old_short == 0 and new_short > 0:
            return True
        if old_credit == 0 and new_credit > 0:
            return True
        if old_short > 0 and abs(new_short - old_short) / old_short > threshold:
            return True
        if old_credit > 0 and abs(new_credit - old_credit) / old_credit > threshold:
            return True
        return False
    
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
                
                row = None
                data_date = None
                
                for idx, r in df.iterrows():
                    frgn = str(r.get('frgn_ntby_qty', '')).strip()
                    orgn = str(r.get('orgn_ntby_qty', '')).strip()
                    prsn = str(r.get('prsn_ntby_qty', '')).strip()
                    
                    if frgn and orgn and prsn:
                        row = r
                        date_str = str(r.get('stck_bsop_date', ''))
                        if len(date_str) == 8:
                            data_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                        break
                
                if row is None:
                    return None
                
                def safe_int(val):
                    try:
                        val_str = str(val).strip()
                        if not val_str or val_str == '':
                            return 0
                        return int(float(val_str))
                    except (ValueError, TypeError):
                        return 0
                
                def safe_float(val):
                    try:
                        val_str = str(val).strip()
                        if not val_str or val_str == '':
                            return 0.0
                        return float(val_str)
                    except (ValueError, TypeError):
                        return 0.0
                
                return {
                    'ticker': ticker,
                    'date': data_date or datetime.now().strftime("%Y-%m-%d"),
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
            today = datetime.now()
            today_str = today.strftime("%Y%m%d")
            # 공매도 데이터는 T-2~T-3일 지연됨. 최근 7일 조회하여 가장 최근 유효 데이터 사용
            start_date = (today - timedelta(days=7)).strftime("%Y%m%d")
            
            # 공매도 조회
            # output1은 종합정보, output2는 일별추이
            df_short_sum, df_short_daily = self._functions.daily_short_sale("J", ticker, start_date, today_str)
            
            short_volume = 0
            short_balance = 0
            short_ratio = 0.0
            
            # 일별 데이터에서 가장 최근 유효 데이터 찾기
            if not df_short_daily.empty:
                # 날짜 기준 내림차순 정렬 (최신 먼저)
                df_sorted = df_short_daily.sort_values('stck_bsop_date', ascending=False)
                valid_found = False
                for _, row in df_sorted.iterrows():
                    # 실제 KIS API 필드명 (2026-01 기준 검증됨)
                    ratio = float(row.get('ssts_vol_rlim', 0) or 0)
                    if ratio > 0:
                        short_volume = int(float(row.get('ssts_cntg_qty', 0) or 0))
                        short_balance = int(float(row.get('acml_ssts_cntg_qty', 0) or 0))
                        short_ratio = ratio
                        break  # 가장 최근 유효 데이터 사용

            # 신용 조회
            # daily_credit_balance는 일별 추이를 반환
            df_credit = self._functions.daily_credit_balance("J", "20476", ticker, today_str)
            
            credit_balance = 0
            credit_ratio = 0.0
            
            if not df_credit.empty:
                row = df_credit.iloc[0]
                # 실제 KIS API 필드명 (2026-01 기준 검증됨)
                # whol_loan_rmnd_stcn: 융자 잔고 수량
                # whol_loan_rmnd_rate: 융자 잔고 비율 (%)
                credit_balance = int(float(row.get('whol_loan_rmnd_stcn', 0) or 0))
                credit_ratio = float(row.get('whol_loan_rmnd_rate', 0) or 0)
            
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
    
    async def collect_all_short_credit(self, tickers: List[str], delay: float = 0.5, force: bool = False, detect_changes: bool = False) -> Dict:
        start_time = time.time()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        unchanged_count = 0
        data = []
        
        existing_data = {}
        if detect_changes:
            collected = await self.get_collected_tickers_for_today("daily_short_credit")
            zero_value_tickers = []
            if collected:
                existing_data = await self.get_existing_short_credit_data(list(collected))
                # Re-collect if short_ratio is 0 (likely missing data due to T-2 delay) OR credit_ratio is 0
                zero_value_tickers = [t for t in collected if existing_data.get(t, {}).get('short_ratio', 0) == 0 or existing_data.get(t, {}).get('credit_ratio', 0) == 0]
            never_collected = [t for t in tickers if t not in collected]
            remaining = never_collected + zero_value_tickers
            skipped_count = len(tickers) - len(remaining)
            mode = "[DETECT]"
        elif force:
            remaining = tickers
            skipped_count = 0
            mode = "[FORCE]"
        else:
            collected = await self.get_collected_tickers_for_today("daily_short_credit")
            remaining = [t for t in tickers if t not in collected]
            skipped_count = len(tickers) - len(remaining)
            mode = ""
        
        total = len(remaining)
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] {mode} Short/Credit collection: {total} remaining ({skipped_count} already collected)"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped_count, 'unchanged': 0, 'duration': 0}
        
        for i, ticker in enumerate(remaining):
            if i > 0 and i % 50 == 0:
                progress = i * 100 // total
                now = datetime.now().strftime('%H:%M')
                log_msg = f"[{now}] Short/Credit: {i}/{total} ({progress}%)"
                logger.info(f"[Collector] {log_msg}")
                self._log_buffer.add_sync(log_msg)
            
            result = self.collect_short_credit_sync(ticker)
            if result:
                if detect_changes and ticker in existing_data:
                    if self._has_meaningful_change(existing_data[ticker], result):
                        data.append(result)
                        success_count += 1
                    else:
                        unchanged_count += 1
                else:
                    data.append(result)
                    success_count += 1
            else:
                failed_count += 1
            
            await asyncio.sleep(delay)

            # Batch upsert every 50 items
            if len(data) >= 50:
                await self.db.upsert_daily_short_credit(data)
                data = []
        
        if data:
            await self.db.upsert_daily_short_credit(data)
        
        duration = time.time() - start_time
        await self.db.log_collection("short_credit", total, success_count, failed_count, duration)
        
        now = datetime.now().strftime('%H:%M')
        log_msg = f"[{now}] Short/Credit complete: {success_count}/{total} (unchanged: {unchanged_count}) in {duration:.1f}s"
        logger.info(f"[Collector] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'unchanged': unchanged_count,
            'duration': duration
        }
    
    async def run_daily_collection(self, collect_price: bool = True, collect_investor: bool = True, collect_short: bool = True, force: bool = False, detect_changes: bool = False) -> Dict:
        now = datetime.now().strftime('%H:%M')
        mode = "[DETECT] " if detect_changes else ("[FORCE] " if force else "")
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
            results['short_credit'] = await self.collect_all_short_credit(tickers, force=force, detect_changes=detect_changes)
        
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
