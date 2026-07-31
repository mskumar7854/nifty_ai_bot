import asyncio
import sqlite3
from core.db_manager import DBManager

async def test_migration():
    db = DBManager("data/trading_v4_sim.db")
    await db.initialize()
    print("Migration completed.")

asyncio.run(test_migration())

conn = sqlite3.connect("data/trading_v4_sim.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])
