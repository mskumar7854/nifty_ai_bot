"""
============================================
DHAN API CREDENTIALS LOADER
============================================
Loads DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN
from the .env file safely.

Usage:
    from config.config import CLIENT_ID, ACCESS_TOKEN

NEVER hardcode credentials in source files.
Token expires every 24 hours — update .env daily.
============================================
"""

import os
from dotenv import load_dotenv

# Load .env from project root (one level up from config/)
load_dotenv()

CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# ── Fail-fast validation ──────────────────────────────────────
_PLACEHOLDER_VALUES = {"your_client_id_here", "your_access_token_here", "", None}

def _validate():
    errors = []
    if CLIENT_ID in _PLACEHOLDER_VALUES:
        errors.append(
            "DHAN_CLIENT_ID is missing or not set.\n"
            "  → Open .env and set: DHAN_CLIENT_ID=1100XXXXXX"
        )
    if ACCESS_TOKEN in _PLACEHOLDER_VALUES:
        errors.append(
            "DHAN_ACCESS_TOKEN is missing or not set.\n"
            "  → Open .env and set: DHAN_ACCESS_TOKEN=<your_token>\n"
            "  → Generate at: https://dhanhq.co → My Account → API"
        )
    if errors:
        separator = "\n" + "─" * 50 + "\n"
        raise EnvironmentError(
            separator
            + "🚨  DHAN API credentials not configured!\n\n"
            + "\n\n".join(errors)
            + separator
        )

_validate()
