# -*- coding: utf-8 -*-
from collections import deque
from datetime import datetime
from typing import List, Callable, Optional
import asyncio


class LogBuffer:
    
    def __init__(self, max_size: int = 500):
        self._logs: deque = deque(maxlen=max_size)
        self._subscribers: List[Callable] = []
        self._lock = asyncio.Lock()
    
    async def add(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        
        async with self._lock:
            self._logs.append(log_entry)
        
        await self._notify_subscribers(log_entry)
    
    def add_sync(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self._logs.append(log_entry)
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._notify_subscribers(log_entry))
        except RuntimeError:
            pass
    
    async def _notify_subscribers(self, log_entry: dict):
        for callback in self._subscribers[:]:
            try:
                await callback(log_entry)
            except Exception:
                self._subscribers.remove(callback)
    
    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def get_recent(self, count: int = 100) -> List[dict]:
        logs = list(self._logs)
        return logs[-count:] if len(logs) > count else logs
    
    def clear(self):
        self._logs.clear()


_log_buffer_instance: Optional[LogBuffer] = None


def get_log_buffer() -> LogBuffer:
    global _log_buffer_instance
    if _log_buffer_instance is None:
        _log_buffer_instance = LogBuffer()
    return _log_buffer_instance
