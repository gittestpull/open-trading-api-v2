# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from .database import Database, get_database
from .ai_analyst import get_ai_analyst

logger = logging.getLogger(__name__)


class TradeJournal:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.ai_analyst = get_ai_analyst()
    
    async def add_entry(self, ticker: str, side: str, price: float, qty: int,
                        thesis: str = None, pnl: float = None) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        
        await self.db.execute("""
            INSERT INTO trade_journal (ticker, side, price, qty, thesis, pnl, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker, side.upper(), price, qty, thesis, pnl, today))
        
        result = await self.db.fetch_one(
            "SELECT id FROM trade_journal ORDER BY id DESC LIMIT 1"
        )
        return result['id'] if result else 0
    
    async def update_entry(self, entry_id: int, ticker: str = None, side: str = None,
                           price: float = None, qty: int = None, thesis: str = None,
                           pnl: float = None) -> bool:
        fields = []
        params = []
        
        if ticker:
            fields.append("ticker = ?")
            params.append(ticker)
        if side:
            fields.append("side = ?")
            params.append(side.upper())
        if price is not None:
            fields.append("price = ?")
            params.append(price)
        if qty is not None:
            fields.append("qty = ?")
            params.append(qty)
        if thesis is not None:
            fields.append("thesis = ?")
            params.append(thesis)
        if pnl is not None:
            fields.append("pnl = ?")
            params.append(pnl)
            
        if not fields:
            return False
            
        params.append(entry_id)
        
        await self.db.execute(f"""
            UPDATE trade_journal 
            SET {", ".join(fields)}
            WHERE id = ?
        """, tuple(params))
        return True

    async def delete_entry(self, entry_id: int) -> bool:
        await self.db.execute("DELETE FROM trade_journal WHERE id = ?", (entry_id,))
        return True

    async def update_ai_feedback(self, entry_id: int, feedback: str) -> bool:
        await self.db.execute(
            "UPDATE trade_journal SET ai_feedback = ? WHERE id = ?",
            (feedback, entry_id)
        )
        return True
    
    async def get_entries(self, ticker: str = None, start_date: str = None,
                          end_date: str = None, limit: int = 50) -> List[Dict]:
        conditions = []
        params = []
        
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        return await self.db.fetch_all(f"""
            SELECT tj.*, si.name as stock_name
            FROM trade_journal tj
            LEFT JOIN stock_info si ON tj.ticker = si.ticker
            WHERE {where_clause}
            ORDER BY tj.created_at DESC
            LIMIT ?
        """, tuple(params))
    
    async def get_entry(self, entry_id: int) -> Optional[Dict]:
        return await self.db.fetch_one(
            "SELECT * FROM trade_journal WHERE id = ?",
            (entry_id,)
        )
    
    async def get_statistics(self, start_date: str = None, end_date: str = None) -> Dict:
        conditions = []
        params = []
        
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        total_trades = await self.db.fetch_one(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN side = 'BUY' THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN side = 'SELL' THEN 1 ELSE 0 END) as sells
            FROM trade_journal
            WHERE {where_clause}
        """, tuple(params))
        
        pnl_stats = await self.db.fetch_one(f"""
            SELECT 
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as max_profit,
                MIN(pnl) as max_loss,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades
            FROM trade_journal
            WHERE {where_clause} AND pnl IS NOT NULL
        """, tuple(params))
        
        by_ticker = await self.db.fetch_all(f"""
            SELECT 
                ticker,
                COUNT(*) as trades,
                SUM(pnl) as total_pnl
            FROM trade_journal
            WHERE {where_clause}
            GROUP BY ticker
            ORDER BY total_pnl DESC
            LIMIT 10
        """, tuple(params))
        
        winning = pnl_stats['winning_trades'] or 0
        losing = pnl_stats['losing_trades'] or 0
        win_rate = winning / (winning + losing) * 100 if (winning + losing) > 0 else 0
        
        return {
            'total_trades': total_trades['total'] or 0,
            'buys': total_trades['buys'] or 0,
            'sells': total_trades['sells'] or 0,
            'total_pnl': pnl_stats['total_pnl'] or 0,
            'avg_pnl': pnl_stats['avg_pnl'] or 0,
            'max_profit': pnl_stats['max_profit'] or 0,
            'max_loss': pnl_stats['max_loss'] or 0,
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': round(win_rate, 2),
            'by_ticker': by_ticker
        }
    
    async def analyze_entry(self, entry_id: int) -> Dict:
        entry = await self.get_entry(entry_id)
        if not entry:
            return {"error": "Entry not found"}
        
        ticker = entry['ticker']
        
        price_at_trade = await self.db.fetch_one("""
            SELECT * FROM daily_price 
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC LIMIT 1
        """, (ticker, entry['date']))
        
        later_prices = await self.db.fetch_all("""
            SELECT * FROM daily_price 
            WHERE ticker = ? AND date > ?
            ORDER BY date ASC LIMIT 5
        """, (ticker, entry['date']))
        
        outcome = "unknown"
        if later_prices and entry['side'] == 'BUY':
            entry_price = entry['price']
            max_price = max(p['high'] for p in later_prices)
            min_price = min(p['low'] for p in later_prices)
            
            if max_price > entry_price * 1.02:
                outcome = "profitable"
            elif min_price < entry_price * 0.98:
                outcome = "loss"
            else:
                outcome = "neutral"
        
        feedback = f"매매 결과: {outcome}. "
        if entry['thesis']:
            feedback += f"당시 판단: {entry['thesis']}"
        
        await self.update_ai_feedback(entry_id, feedback)
        
        return {
            "entry": entry,
            "outcome": outcome,
            "feedback": feedback,
            "later_prices": later_prices
        }


_journal_instance: Optional[TradeJournal] = None

def get_trade_journal() -> TradeJournal:
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = TradeJournal()
    return _journal_instance
