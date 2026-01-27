
import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "data", "deep_dive.db")

print(f"Checking database at: {db_path}")

if not os.path.exists(db_path):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM stock_info WHERE ticker = '005930'")
row = cursor.fetchone()

if row:
    print(f"Found: {row}")
else:
    print("Ticker 005930 not found in stock_info")

cursor.execute("SELECT COUNT(*) FROM stock_info")
total = cursor.fetchone()[0]
print(f"Total stocks in DB: {total}")

conn.close()
