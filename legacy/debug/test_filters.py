
import logging
import asyncio
from datetime import datetime
from stock_cache import get_stock_cache, StockData
import sqlite3
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

async def test():
    print("Initializing Cache with Dummy Data...")
    cache = get_stock_cache()
    
    # Force DB init
    if getattr(cache, 'db_path', None) is None:
        cache.db_path = 'data/stock_cache.db'
        os.makedirs('data', exist_ok=True)
    
    # Manually populate stocks
    cache.stocks = {
        '005930': StockData(
            code='005930', name='삼성전자', market='kospi', 
            price=70000, volume=5000000, market_cap=4000000, 
            per=10.5, pbr=1.2, op_rate=15.0, debt_rate=30.0, rsrv_rate=20000.0,
            updated_at=datetime.now()
        )
    }
    
    print("Saving cache to trigger history insertion...")
    cache.save_cache()
    
    print("Verifying DB Persistence...")
    conn = sqlite3.connect('data/stock_cache.db')
    cursor = conn.cursor()
    
    # Check 'stocks' table
    cursor.execute("SELECT count(*) FROM stocks")
    count_stocks = cursor.fetchone()[0]
    print(f"Stocks count: {count_stocks}")
    if count_stocks == 1:
        print("✅ Stocks Table OK")
    else:
        print("❌ Stocks Table FAIL")

    # Check 'daily_history' table
    cursor.execute("SELECT count(*) FROM daily_history")
    count_history = cursor.fetchone()[0]
    print(f"History count: {count_history}")
    
    cursor.execute("SELECT date, code, price FROM daily_history")
    row = cursor.fetchone()
    print(f"History Row: {row}")
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    if count_history == 1 and row[0] == today_str and row[1] == '005930':
        print("✅ History Table OK")
    else:
        print("❌ History Table FAIL")
        
    conn.close()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test())
