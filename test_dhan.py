import os
from dotenv import load_dotenv
from dhanhq import dhanhq

def test():
    load_dotenv()
    
    CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
    ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
    
    print("Initializing DhanHQ Client...")
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    except Exception as e:
        print("Failed to initialize dhanhq:", e)
        return

    print("\n--- 1. SDK Version & Methods Check ---")
    print(f"hasattr option_chain: {hasattr(dhan, 'option_chain')}")
    print(f"hasattr expiry_list: {hasattr(dhan, 'expiry_list')}")

    print("\n--- 2. Token Validation ---")
    try:
        funds = dhan.get_fund_limits()
        print("get_fund_limits():\n", funds)
    except Exception as e:
        print("get_fund_limits() failed. Token is likely invalid.\nError:", e)

    print("\n--- 3. Historical Data Validation ---")
    try:
        historical = dhan.historical_daily_data(
            security_id="13",
            exchange_segment="IDX_I",
            instrument_type="INDEX",
            from_date="2026-05-25",
            to_date="2026-06-01"
        )
        print("historical_daily_data():\n", historical)
    except Exception as e:
        print("historical_daily_data() failed.\nError:", e)

if __name__ == "__main__":
    test()
