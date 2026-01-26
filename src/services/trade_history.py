"""
Trade History Database for Trading Bot Dashboard
Stores all trades in SQLite for analysis and querying.
"""

import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Database path
DB_DIR = Path(__file__).parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "trade_history.db"

def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            ticker TEXT NOT NULL,
            ticker_code TEXT,
            action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            avg_buy_price REAL,
            profit_rate REAL,
            profit_amt REAL,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Trade history DB initialized at {DB_PATH}")

# Initialize DB on module import
init_db()

def log_trade(
    ticker: str,
    action: str,
    qty: int,
    price: float,
    bot_id: str = None,
    ticker_code: str = None,
    avg_buy_price: float = None,
    profit_rate: float = None,
    profit_amt: float = None,
    reason: str = None
) -> int:
    """
    Log a trade to the database.
    
    Returns:
        int: The ID of the inserted trade record
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (bot_id, ticker, ticker_code, action, qty, price, 
                               avg_buy_price, profit_rate, profit_amt, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bot_id, ticker, ticker_code, action.upper(), qty, price,
              avg_buy_price, profit_rate, profit_amt, reason))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Trade logged: {action} {ticker} x{qty} @ {price}")
        return trade_id
        
    except Exception as e:
        logger.error(f"Failed to log trade: {e}")
        return -1

def get_trades(
    ticker: str = None,
    bot_id: str = None,
    action: str = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Query trades from the database.
    
    Args:
        ticker: Filter by ticker name
        bot_id: Filter by bot ID
        action: Filter by action (BUY/SELL)
        limit: Max number of records to return
        offset: Number of records to skip
    
    Returns:
        List of trade dictionaries
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)
        if bot_id:
            query += " AND bot_id = ?"
            params.append(bot_id)
        if action:
            query += " AND action = ?"
            params.append(action.upper())
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"Failed to query trades: {e}")
        return []

def get_daily_summary(days: int = 7) -> Dict:
    """
    Get daily profit/loss summary for the last N days.
    
    Returns:
        Dict with daily P&L data
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                date(timestamp) as trade_date,
                COUNT(*) as total_trades,
                SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN action = 'SELL' THEN profit_amt ELSE 0 END) as total_profit
            FROM trades 
            WHERE timestamp >= date('now', ? || ' days')
            GROUP BY date(timestamp)
            ORDER BY trade_date DESC
        ''', (f'-{days}',))
        
        rows = cursor.fetchall()
        conn.close()
        
        return {
            "days": [dict(row) for row in rows],
            "total_profit": sum(row["total_profit"] or 0 for row in rows)
        }
        
    except Exception as e:
        logger.error(f"Failed to get daily summary: {e}")
        return {"days": [], "total_profit": 0}
