import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

if not CLIENT_ID or not ACCESS_TOKEN:
    print("FAILED: Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN in .env")
    exit(1)

# Dhan API v2 Expiry List Endpoint
url = "https://api.dhan.co/v2/expirylist"
headers = {
    "access-token": ACCESS_TOKEN,
    "client-id": CLIENT_ID,
    "Content-Type": "application/json"
}

payload = {
    "UnderlyingScrip": 13,
    "UnderlyingSeg": "IDX_I"
}

print("Fetching Expiry List from Dhan...")
try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"FAILED: Exception occurred - {e}")
