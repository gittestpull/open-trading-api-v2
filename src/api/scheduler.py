# -*- coding: utf-8 -*-
import asyncio
import logging
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .collector import DataCollector, get_collector
from .stock_master import get_stock_master_service
from .human_index import get_human_index_calculator
from .log_buffer import get_log_buffer
from .history_collector import get_history_collector
from .news import get_news_collector

logger = logging.getLogger(__name__)


class CollectionScheduler:
    
    def __init__(self, is_live: bool = False):
        self.scheduler = AsyncIOScheduler()
        self.is_live = is_live
        self.collector = get_collector(is_live=is_live)
        self.human_index = get_human_index_calculator()
        self.history_collector = get_history_collector()
        self.news_collector = get_news_collector()
        self._is_running = False
        self._last_collection: Optional[datetime] = None
        self._on_complete_callback: Optional[Callable] = None
        self._log_buffer = get_log_buffer()
        self._minute_tickers: list[str] = []
    
    def set_on_complete_callback(self, callback: Callable):
        self._on_complete_callback = callback
    
    async def initialize(self):
        """Initialize scheduler state from database"""
        from .database import get_database
        db = get_database()
        
        # Load minute tickers
        tickers_json = await db.get_config("minute_tickers")
        if tickers_json:
            try:
                self._minute_tickers = json.loads(tickers_json)
                logger.info(f"[Scheduler] Loaded minute tickers: {self._minute_tickers}")
            except json.JSONDecodeError:
                logger.error("[Scheduler] Failed to decode minute_tickers config")

    async def _run_daily_collection(self):
        start_time = datetime.now()
        log_msg = f"[{start_time.strftime('%H:%M')}] Daily collection triggered"
        logger.info(f"[Scheduler] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        try:
            # 1. Base Market Data
            result = await self.collector.run_daily_collection()
            
            # 2. Human Index (Youtube, Naver, etc)
            human_result = await self._collect_human_index()
            result['human_index'] = human_result
            
            # 3. News Collection
            news_result = await self._collect_news()
            result['news'] = news_result
            
            self._last_collection = datetime.now()
            duration = (self._last_collection - start_time).total_seconds()
            log_msg = f"[{self._last_collection.strftime('%H:%M')}] Daily collection completed in {duration:.1f}s"
            logger.info(f"[Scheduler] {log_msg}: {result}")
            self._log_buffer.add_sync(log_msg)
            
            if self._on_complete_callback:
                self._on_complete_callback(result)
        except Exception as e:
            log_msg = f"[{datetime.now().strftime('%H:%M')}] Daily collection failed: {e}"
            logger.error(f"[Scheduler] {log_msg}")
            self._log_buffer.add_sync(log_msg, "ERROR")
    
    async def _collect_human_index(self, tickers: list = None, force: bool = False) -> dict:
        stock_service = get_stock_master_service()
        
        if tickers is None:
            stocks = await stock_service.get_top_stocks_by_market_cap(limit=100)
            tickers = [(s['ticker'], s['name']) for s in stocks]
        
        if not force:
            today = datetime.now().strftime("%Y-%m-%d")
            from .database import get_database
            db = get_database()
            collected = await db.fetch_all(
                "SELECT ticker FROM human_index WHERE date = ?", (today,)
            )
            collected_set = {r['ticker'] for r in collected}
            original_count = len(tickers)
            tickers = [(t, n) for t, n in tickers if t not in collected_set]
            skipped = original_count - len(tickers)
        else:
            skipped = 0
        
        total = len(tickers)
        success = 0
        failed = 0
        start_time = datetime.now()
        
        mode = "[FORCE] " if force else ""
        log_msg = f"[{start_time.strftime('%H:%M')}] {mode}HumanIndex collection: {total} remaining ({skipped} already collected)"
        logger.info(f"[HumanIndex] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped, 'duration': 0}
        
        for i, (ticker, name) in enumerate(tickers):
            progress = (i + 1) * 100 // total
            current_time = datetime.now().strftime('%H:%M')
            
            if i % 10 == 0:
                log_msg = f"[{current_time}] HumanIndex: {i+1}/{total} ({progress}%)"
                logger.info(f"[HumanIndex] {log_msg}")
                self._log_buffer.add_sync(log_msg)
            
            try:
                result = await self.human_index.collect_all_human_data(ticker, name)
                if result.get('human_index'):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.debug(f"[HumanIndex] Failed for {ticker}: {e}")
                failed += 1
            
            await asyncio.sleep(1.0)
        
        duration = (datetime.now() - start_time).total_seconds()
        log_msg = f"[{datetime.now().strftime('%H:%M')}] HumanIndex complete: {success}/{total} ({skipped} skipped) in {duration:.1f}s"
        logger.info(f"[HumanIndex] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'duration': duration
        }

    async def _collect_news(self, tickers: list = None, force: bool = False) -> dict:
        stock_service = get_stock_master_service()
        
        if tickers is None:
            # News collection for top 50 stocks (news is heavy)
            stocks = await stock_service.get_top_stocks_by_market_cap(limit=50)
            tickers = [s['ticker'] for s in stocks]
        
        # Check already collected if not force
        if not force:
            today = datetime.now().strftime("%Y-%m-%d")
            from .database import get_database
            db = get_database()
            # Check news_metrics for today
            collected = await db.fetch_all(
                "SELECT ticker FROM news_metrics WHERE date = ?", (today,)
            )
            collected_set = {r['ticker'] for r in collected}
            original_count = len(tickers)
            tickers = [t for t in tickers if t not in collected_set]
            skipped = original_count - len(tickers)
        else:
            skipped = 0
            
        total = len(tickers)
        success = 0
        failed = 0
        start_time = datetime.now()
        
        mode = "[FORCE] " if force else ""
        log_msg = f"[{start_time.strftime('%H:%M')}] {mode}News collection: {total} remaining ({skipped} already collected)"
        logger.info(f"[News] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': skipped, 'duration': 0}
            
        for i, ticker in enumerate(tickers):
            try:
                result = await self.news_collector.collect_for_stock(ticker, days=2)
                if result.get('details'):
                    success += 1
                else:
                    pass
            except Exception as e:
                logger.error(f"[News] Failed for {ticker}: {e}")
                failed += 1
            
            if i % 5 == 0:
                self._log_buffer.add_sync(f"[News] Processing {i+1}/{total}...")
                
            await asyncio.sleep(1.0)
            
        duration = (datetime.now() - start_time).total_seconds()
        log_msg = f"[{datetime.now().strftime('%H:%M')}] News complete: {success}/{total} in {duration:.1f}s"
        logger.info(f"[News] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'duration': duration
        }
    
    def _schedule_job(self, func, trigger):
        def job_wrapper():
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(func())
            else:
                loop.run_until_complete(func())
        
        self.scheduler.add_job(job_wrapper, trigger, id='daily_collection', replace_existing=True)
    
    def start(self, hour: int = 15, minute: int = 50):
        if self._is_running:
            logger.warning("[Scheduler] Already running")
            return
        
        trigger = CronTrigger(hour=hour, minute=minute, day_of_week='mon-fri', timezone=ZoneInfo('Asia/Seoul'))
        self._schedule_job(self._run_daily_collection, trigger)
        
        self.scheduler.start()
        self._is_running = True
        logger.info(f"[Scheduler] Started - Daily collection at {hour:02d}:{minute:02d} (Mon-Fri)")
        
        # Start minute collection if configured
        if self._minute_tickers:
            self.start_minute_collection()
    
    def stop(self):
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("[Scheduler] Stopped")
    
    async def run_now(self, include_human_index: bool = True, force: bool = False, detect_changes: bool = False) -> dict:
        start_time = datetime.now()
        mode = "[DETECT] " if detect_changes else ("[FORCE] " if force else "")
        logger.info(f"[Scheduler] [{start_time.strftime('%H:%M')}] {mode}Manual collection triggered")
        result = await self.collector.run_daily_collection(force=force, detect_changes=detect_changes)
        
        if include_human_index:
            human_result = await self._collect_human_index(force=force)
            result['human_index'] = human_result
            
            # News collection on manual trigger too
            news_result = await self._collect_news(force=force)
            result['news'] = news_result
        
        self._last_collection = datetime.now()
        return result
    
    async def load_stocks_only(self) -> int:
        stock_service = get_stock_master_service()
        count = await stock_service.load_all_stocks()
        return count
    
    def get_status(self) -> dict:
        jobs = []
        if self._is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
        
        return {
            'is_running': self._is_running,
            'is_live': self.is_live,
            'last_collection': self._last_collection.isoformat() if self._last_collection else None,
            'jobs': jobs,
            'minute_tickers': self._minute_tickers
        }

    async def set_minute_tickers(self, tickers: list[str]):
        self._minute_tickers = tickers
        logger.info(f"[Scheduler] Minute collection tickers set: {tickers}")
        
        # Save to DB
        from .database import get_database
        db = get_database()
        await db.set_config("minute_tickers", json.dumps(tickers))

    async def _run_minute_collection(self):
        if not self._minute_tickers:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        log_msg = f"[{datetime.now().strftime('%H:%M')}] Minute collection for {len(self._minute_tickers)} tickers"
        logger.info(f"[Scheduler] {log_msg}")
        self._log_buffer.add_sync(log_msg)

        await self.history_collector.init_db()

        for ticker in self._minute_tickers:
            try:
                result = await self.history_collector.collect_minute_for_date(ticker, today)
                logger.info(f"[Scheduler] Minute data for {ticker}: {result.get('count', 0)} records")
            except Exception as e:
                logger.error(f"[Scheduler] Minute collection failed for {ticker}: {e}")
            await asyncio.sleep(0.5)

    def start_minute_collection(self):
        if not self._minute_tickers:
            logger.warning("[Scheduler] No minute tickers configured")
            return

        trigger = CronTrigger(
            hour=15, minute=35,
            day_of_week='mon-fri',
            timezone=ZoneInfo('Asia/Seoul')
        )

        def job_wrapper():
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._run_minute_collection())
            else:
                loop.run_until_complete(self._run_minute_collection())

        self.scheduler.add_job(
            job_wrapper, trigger,
            id='minute_collection',
            replace_existing=True
        )
        logger.info(f"[Scheduler] Minute collection scheduled for 15:35 (Mon-Fri)")

    async def run_minute_now(self) -> dict:
        if not self._minute_tickers:
            return {"error": "No minute tickers configured", "tickers": []}

        await self.history_collector.init_db()
        today = datetime.now().strftime("%Y-%m-%d")
        results = []

        for ticker in self._minute_tickers:
            try:
                result = await self.history_collector.collect_minute_for_date(ticker, today)
                results.append(result)
            except Exception as e:
                results.append({"ticker": ticker, "error": str(e)})
            await asyncio.sleep(0.5)

        total = sum(r.get('count', 0) for r in results if 'error' not in r)
        return {"status": "success", "total_records": total, "results": results}


_scheduler_instance: Optional[CollectionScheduler] = None

def get_scheduler(is_live: bool = False) -> CollectionScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CollectionScheduler(is_live=is_live)
    return _scheduler_instance
