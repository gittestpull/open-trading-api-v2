# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import List, Dict, Optional
from .database import get_database

logger = logging.getLogger(__name__)

class TradeStatsService:
    def __init__(self):
        self.db = get_database()

    async def get_monthly_stats(self, limit: int = 12) -> List[Dict]:
        query = "SELECT * FROM trade_stats ORDER BY date DESC LIMIT ?"
        return await self.db.fetch_all(query, (limit,))

    async def seed_data(self):
        # Data collected from index.go.kr on 2026-02-05
        data = [
            {"date": "2024-12", "export": 614, "import": 549, "balance": 65},
            {"date": "2025-01", "export": 492, "import": 511, "balance": -19},
            {"date": "2025-02", "export": 523, "import": 483, "balance": 40},
            {"date": "2025-03", "export": 581, "import": 533, "balance": 48},
            {"date": "2025-04", "export": 581, "import": 532, "balance": 49},
            {"date": "2025-05", "export": 573, "import": 503, "balance": 70},
            {"date": "2025-06", "export": 598, "import": 507, "balance": 91},
            {"date": "2025-07", "export": 607, "import": 542, "balance": 65},
            {"date": "2025-08", "export": 583, "import": 518, "balance": 65},
            {"date": "2025-09", "export": 659, "import": 564, "balance": 95},
            # Estimates based on news
            {"date": "2025-12", "export": 695, "import": 574, "balance": 121},
            {"date": "2026-01", "export": 658, "import": 540, "balance": 118},
        ]
        await self.db.upsert_trade_stats(data)
        logger.info(f"[TradeStats] Seeded {len(data)} records")

_service_instance = None

def get_trade_stats_service():
    global _service_instance
    if _service_instance is None:
        _service_instance = TradeStatsService()
    return _service_instance
