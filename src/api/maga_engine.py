# -*- coding: utf-8 -*-
import asyncio
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)

class MagaEngine:
    def __init__(self):
        self._is_running = False
        self._subscribers: List[Callable] = []
        self._last_tweet_id = None
        
        # Target stocks for volatility radar
        self.target_stocks = [
            {"name": "한화에어로스페이스", "ticker": "012450"},
            {"name": "오리엔탈정공", "ticker": "014940"},
            {"name": "유니온스틸", "ticker": "004850"},
            {"name": "대한제강", "ticker": "002310"},
            {"name": "현대로템", "ticker": "064350"}
        ]
        
        # Mock price history for volatility detection
        self.price_history = {s['ticker']: [] for s in self.target_stocks}

    def subscribe(self, callback: Callable):
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _notify(self, data: Dict):
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"[MagaEngine] Notify error: {e}")

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        asyncio.create_task(self._loop())
        logger.info("[MagaEngine] Started")

    def stop(self):
        self._is_running = False
        logger.info("[MagaEngine] Stopped")

    async def _loop(self):
        while self._is_running:
            try:
                # 1. Poll for "Tweets" (Mocked for now, will integrate bird later)
                await self._check_tweets()
                
                # 2. Check Volatility
                await self._check_volatility()
                
                await asyncio.sleep(10) # Check every 10 seconds
            except Exception as e:
                logger.error(f"[MagaEngine] Loop error: {e}")
                await asyncio.sleep(5)

    async def _check_tweets(self):
        # In a real scenario, this would use a scraper or API.
        # For simulation/training, we occasionally trigger a mock tweet.
        if random.random() < 0.05: # 5% chance every 10s
            mock_data = {
                "type": "tweet",
                "time": datetime.now().strftime("%H:%M:%S"),
                "tags": "#MAGA #Energy",
                "text": "We have more OIL and GAS than any other nation. We will DRILL, BABY, DRILL!",
                "insight": "에너지 자립 정책 강조. 원유/가스 및 시추 관련주 수혜 예상.",
                "stocks": [
                    {"name": "한국석유", "ticker": "004090", "score": 98},
                    {"name": "흥구석유", "ticker": "024060", "score": 95}
                ]
            }
            await self._notify(mock_data)

    async def _check_volatility(self):
        for stock in self.target_stocks:
            ticker = stock['ticker']
            # Simulate real-time price change
            # In real life, this would fetch from a ticker stream
            change = (random.random() - 0.5) * 2 # -1% to +1%
            
            self.price_history[ticker].append(change)
            if len(self.price_history[ticker]) > 10:
                self.price_history[ticker].pop(0)
            
            # Detect "Whale" movement (simulated)
            if abs(change) > 1.5:
                alert = {
                    "type": "volatility",
                    "ticker": ticker,
                    "name": stock['name'],
                    "change": round(change, 2),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "msg": f"⚠️ [고래 포착] {stock['name']} 급격한 수급 변동 감지!"
                }
                await self._notify(alert)

_engine_instance = None

def get_maga_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MagaEngine()
    return _engine_instance
