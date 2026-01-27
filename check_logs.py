
import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "data", "deep_dive.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking collection_log table:")
cursor.execute("SELECT * FROM collection_log ORDER BY date DESC, created_at DESC LIMIT 20")
rows = cursor.fetchall()
for r in rows:
    print(r)

print("\nChecking scheduler status in system_config:")
cursor.execute("SELECT * FROM system_config WHERE key LIKE '%scheduler%'")
rows = cursor.fetchall()
for r in rows:
    print(r)

conn.close()
