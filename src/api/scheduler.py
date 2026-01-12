# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .collector import DataCollector, get_collector
from .stock_master import get_stock_master_service
from .human_index import get_human_index_calculator
from .log_buffer import get_log_buffer

logger = logging.getLogger(__name__)


class CollectionScheduler:
    
    def __init__(self, is_live: bool = False):
        self.scheduler = AsyncIOScheduler()
        self.is_live = is_live
        self.collector = get_collector(is_live=is_live)
        self.human_index = get_human_index_calculator()
        self._is_running = False
        self._last_collection: Optional[datetime] = None
        self._on_complete_callback: Optional[Callable] = None
        self._log_buffer = get_log_buffer()
    
    def set_on_complete_callback(self, callback: Callable):
        self._on_complete_callback = callback
    
    async def _run_daily_collection(self):
        start_time = datetime.now()
        log_msg = f"[{start_time.strftime('%H:%M')}] Daily collection triggered"
        logger.info(f"[Scheduler] {log_msg}")
        self._log_buffer.add_sync(log_msg)
        try:
            result = await self.collector.run_daily_collection()
            
            human_result = await self._collect_human_index()
            result['human_index'] = human_result
            
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
    
    def stop(self):
        if not self._is_running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("[Scheduler] Stopped")
    
    async def run_now(self, include_human_index: bool = True, force: bool = False) -> dict:
        start_time = datetime.now()
        mode = "[FORCE] " if force else ""
        logger.info(f"[Scheduler] [{start_time.strftime('%H:%M')}] {mode}Manual collection triggered")
        result = await self.collector.run_daily_collection(force=force)
        
        if include_human_index:
            human_result = await self._collect_human_index(force=force)
            result['human_index'] = human_result
        
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
            'jobs': jobs
        }


_scheduler_instance: Optional[CollectionScheduler] = None

def get_scheduler(is_live: bool = False) -> CollectionScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CollectionScheduler(is_live=is_live)
    return _scheduler_instance
