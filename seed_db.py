"""Creates advisor.db with sample data for local runs: python seed_db.py"""
import os
import random
from datetime import datetime, timedelta, timezone

from app.db import DB_PATH, connect, init_db

random.seed(17)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
conn = connect()
init_db(conn)
funds = [("FND-101", "Maple Canadian Equity", 24.51), ("FND-102", "Maple Canadian Bond", 10.18),
         ("FND-103", "Maple Balanced Income", 15.77), ("FND-107", "Maple US Equity ETF", 52.30)]
conn.executemany("INSERT INTO funds VALUES (?, ?, ?)", funds)
start = datetime(2026, 8, 1, 13, 0, 0, tzinfo=timezone.utc)
for i in range(5):
    acc = f"ACC-{1001 + i}"
    conn.execute("INSERT INTO accounts VALUES (?, ?, ?, ?)",
                 (acc, f"Client {i + 1}", f"00{random.randint(10**9, 10**10 - 1)}", 25000.00))
    for code, _, _ in random.sample(funds, 3):
        conn.execute("INSERT INTO positions (account_id, fund_code, units) VALUES (?, ?, ?)",
                     (acc, code, round(random.uniform(10, 900), 4)))
    ts = start
    for _ in range(80):
        ts += timedelta(minutes=random.choice([0, 0, 7, 45, 180]))  # many shared timestamps
        conn.execute("INSERT INTO transactions (account_id, type, amount, created_at) VALUES (?, ?, ?, ?)",
                     (acc, random.choice(["deposit", "withdrawal"]), round(random.uniform(10, 2000), 2),
                      ts.isoformat(timespec="seconds")))
conn.commit()
print(f"seeded {DB_PATH}")
