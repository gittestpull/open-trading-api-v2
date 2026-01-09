
import sqlite3
import os

db_path = 'data/dev/stock_cache.db'

if not os.path.exists(db_path):
    print("Error: DB file not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

code = "005930" # Samsung Electronics
cursor.execute("SELECT * FROM stocks WHERE code=?", (code,))
row = cursor.fetchone()

if row:
    print(f"[{row['name']} ({row['code']}) Data Check]")
    print(f"PER: {row['per']}")
    print(f"Operating Rate (영업이익률): {row['op_rate']}")
    print(f"Debt Ratio (부채비율): {row['debt_rate']}")
    print(f"Reserve Ratio (유보율): {row['rsrv_rate']}")
    print(f"Updated At: {row['updated_at']}")
    
    if row['op_rate'] > 0 and row['debt_rate'] > 0:
        print("\n✅ Verification SUCCESS: Financial data is present and valid.")
    else:
        print("\n❌ Verification FAILED: Financial data is missing or zero.")
else:
    print(f"Stock {code} not found in DB.")

conn.close()
