"""
============================================
DHAN API CONNECTION TEST
============================================
Run this first to confirm your credentials work.

    python test.py

Expected output:
    ✅ Dhan client initialized
    {'status': 'success', ...fund details...}
============================================
"""

from dhan_client import get_dhan_client

def main():
    print("🔌 Connecting to Dhan API...")
    dhan = get_dhan_client()
    print("✅ Dhan client initialized")

    print("\n📊 Fund Limits:")
    result = dhan.get_fund_limits()
    print(result)

if __name__ == "__main__":
    main()
