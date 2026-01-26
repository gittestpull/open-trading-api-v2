
import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")

db_path = 'data/stock_cache.db'
os.makedirs('data', exist_ok=True)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stocks'")
    if not cursor.fetchone():
        logger.info("Creating table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                updated_at TIMESTAMP
            )
        ''')
    else:
        logger.info("Table exists.")

    # Insert test data
    logger.info("Inserting test data...")
    test_data = [('TEST', 'Test Stock', '2025-01-01T00:00:00')]
    cursor.executemany('INSERT OR REPLACE INTO stocks (code, name, updated_at) VALUES (?, ?, ?)', test_data)
    
    conn.commit()
    logger.info("Commit done.")
    
    # Read back
    cursor.execute("SELECT * FROM stocks WHERE code='TEST'")
    row = cursor.fetchone()
    logger.info(f"Read back: {row}")
    
    cursor.execute("SELECT count(*) FROM stocks")
    count = cursor.fetchone()[0]
    logger.info(f"Total count: {count}")
    
    conn.close()

except Exception as e:
    logger.error(f"Error: {e}")
