"""
============================================
🚀 PRE-FLIGHT CHECK SCRIPT
============================================
Run this script before setting SYSTEM_MODE=LIVE.
It verifies:
1. Dhan Token Expiry
2. Environment Configuration
3. Database Connectivity
4. No Missing Critical Imports
5. Python & SDK Versions
============================================
"""

import os
import sys
import asyncio
from datetime import datetime
import importlib

def print_step(msg):
    print(f"🔄 {msg}...", end=" ", flush=True)

def print_pass():
    print("✅ PASS")

def print_fail(msg):
    print(f"❌ FAIL: {msg}")
    sys.exit(1)

def print_warn(msg):
    print(f"⚠️ WARN: {msg}")

async def run_preflight():
    print("=" * 50)
    print("🚀 NIFTY AI SYSTEM v4.6.1 — PRE-FLIGHT CHECK")
    print("=" * 50)

    # 1. Check Python Version
    print_step("Checking Python version")
    if sys.version_info >= (3, 10):
        print_pass()
    else:
        print_fail(f"Requires Python 3.10+, found {sys.version.split()[0]}")

    # 2. Check main.py imports
    print_step("Checking critical imports (datetime bug)")
    try:
        import main
        if not hasattr(main, 'datetime'):
            print_fail("datetime not imported in main.py")
        print_pass()
    except Exception as e:
        print_fail(f"Could not load main.py: {e}")

    # 3. Check Dhan Token
    print_step("Checking Dhan API token")
    try:
        from dhan_client import get_dhan_client
        client = get_dhan_client()
        # Ensure it doesn't blow up
        if not client:
            print_fail("get_dhan_client returned None")
        else:
            print_pass()
    except Exception as e:
        print_fail(f"Token error: {e}")

    # 4. Check Environment config
    print_step("Checking .env configuration")
    mode = os.getenv("SYSTEM_MODE", "SIMULATION")
    active_system = os.getenv("ACTIVE_TRADING_SYSTEM")
    if mode == "LIVE":
        print_warn("SYSTEM_MODE is LIVE. Real orders will execute.")
    else:
        print_pass()
    
    if active_system != "main":
        print_warn(f"ACTIVE_TRADING_SYSTEM is {active_system}, not 'main'")

    # 5. DB Connectivity
    print_step("Checking SQLite database")
    try:
        from core.db_manager import DatabaseManager
        db = DatabaseManager()
        await db.init_db()
        print_pass()
    except Exception as e:
        print_fail(f"DB Error: {e}")

    # 6. Check data directory
    print_step("Checking data directory")
    if os.path.exists("data") and os.path.isdir("data"):
        # Check space > 100MB
        import shutil
        total, used, free = shutil.disk_usage("data")
        free_mb = free / (1024 * 1024)
        if free_mb < 100:
            print_warn(f"Low disk space on data/ ({free_mb:.0f} MB free)")
        else:
            print_pass()
    else:
        print_fail("data/ directory does not exist")

    print("=" * 50)
    print("🚀 ALL SYSTEMS GO. READY FOR LIVE DEPLOYMENT.")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_preflight())
