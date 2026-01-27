
import sqlite3
import os
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "data", "deep_dive.db")

print(f"Checking data in: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check investor data
cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_investor WHERE date >= '2026-01-15'")
investor_stats = cursor.fetchone()
print(f"Daily Investor Data (from 2026-01-15): Count={investor_stats[0]}, MinDate={investor_stats[1]}, MaxDate={investor_stats[2]}")

# Check short/credit data
cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_short_credit WHERE date >= '2026-01-15'")
sc_stats = cursor.fetchone()
print(f"Daily Short/Credit Data (from 2026-01-15): Count={sc_stats[0]}, MinDate={sc_stats[1]}, MaxDate={sc_stats[2]}")

# Sample for 005930
print("\nSample for Ticker 005930 (since 2026-01-15):")
cursor.execute("""
    SELECT i.date, i.foreign_net, i.inst_net, s.short_balance, s.credit_balance
    FROM daily_investor i
    LEFT JOIN daily_short_credit s ON i.ticker = s.ticker AND i.date = s.date
    WHERE i.ticker = '005930' AND i.date >= '2026-01-15'
    ORDER BY i.date DESC
""")
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
