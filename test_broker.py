"""
============================================
🧪 DHAN API BRIDGING TEST
Verify that your API credentials are valid
and that the VPS has network access to Dhan.
============================================
"""

import os
from dotenv import load_dotenv
from dhanhq import dhanhq

def test_connection():
    print("\n" + "="*50)
    print("🏦 DHAN BROKER API TEST - VPS READINESS")
    print("="*50)

    # 1. Load Credentials
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token or "your_" in client_id:
        print("❌ ERROR: Credentials not found in .env file.")
        print("   Please set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN.")
        return

    print(f"📡 Connecting for Client ID: {client_id[:4]}...{client_id[-4:]}")

    try:
        # 2. Initialize Client
        dhan = dhanhq(client_id, access_token)
        
        # 3. Test API Call: Get Fund Limits
        response = dhan.get_fund_limits()
        
        if response.get("status") == "success":
            data = response.get("data", {})
            print("✅ CONNECTION SUCCESSFUL!")
            print(f"💰 Available Funds: ₹{data.get('availabelBalance', 0):,.2f}")
            print(f"📊 Margin Used: ₹{data.get('utilisedAmount', 0):,.2f}")
        else:
            print("❌ API REJECTED:")
            print(f"   Reason: {response.get('remarks', 'Unknown error')}")
            print(f"   Note: Dhan tokens expire every 24 hours.")
            
    except Exception as e:
        print(f"❌ NETWORK/API ERROR: {e}")

    print("="*50 + "\n")

if __name__ == "__main__":
    test_connection()
