import sqlite3
import os

db_path = "data/staging/deep_dive.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== daily_investor (Last 5) ===")
try:
    cursor.execute("SELECT * FROM daily_investor ORDER BY date DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    if not rows:
        print("No data found.")
except Exception as e:
    print(f"Error: {e}")

print("\n=== daily_short_credit (Last 5) ===")
try:
    cursor.execute("SELECT * FROM daily_short_credit ORDER BY date DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    if not rows:
        print("No data found.")
except Exception as e:
    print(f"Error: {e}")

conn.close()
