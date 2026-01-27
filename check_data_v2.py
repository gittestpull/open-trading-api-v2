
import sqlite3
import os
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "data", "deep_dive.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking daily_investor table details:")
cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_investor")
stats = cursor.fetchone()
print(f"Overall: Total={stats[0]}, MinDate={stats[1]}, MaxDate={stats[2]}")

cursor.execute("SELECT * FROM daily_investor ORDER BY date DESC LIMIT 5")
rows = cursor.fetchall()
print("\nLatest 5 entries in daily_investor:")
for r in rows:
    print(r)

print("\nChecking daily_short_credit table details:")
cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_short_credit")
stats = cursor.fetchone()
print(f"Overall: Total={stats[0]}, MinDate={stats[1]}, MaxDate={stats[2]}")

cursor.execute("SELECT * FROM daily_short_credit ORDER BY date DESC LIMIT 5")
rows = cursor.fetchall()
print("\nLatest 5 entries in daily_short_credit:")
for r in rows:
    print(r)

conn.close()
