"""
============================================
DHAN CLIENT FACTORY (v3 — Hardened + Sim Lock)
============================================
Single entry-point to get the Dhan API client.

⚠️ AI WARNING: dhan_client.py
This singleton controls ALL broker communication.
Token expires every 24 hours — update DHAN_ACCESS_TOKEN in .env daily.
NEVER hardcode credentials. NEVER commit .env to git.

v2 additions:
  • Token expiry pre-check (JWT decode without verification)
  • Warning when token has < 2 hours remaining
  • Hard failure when token is expired

v3 additions (P0-A):
  • SimulationModeError — hard lock at the broker layer
  • ANY code path calling place_order() in SIMULATION mode raises
  • Full call stack logged on attempted real order in sim mode
  • Prevents bypass of main.py sim check via direct dhan_client calls

Usage:
    from dhan_client import get_dhan_client

    dhan = get_dhan_client()
    print(dhan.get_fund_limits())
============================================
"""

import os
import json
import base64
import logging
import traceback
from datetime import datetime, timezone

from dhanhq import dhanhq
from config.config import CLIENT_ID, ACCESS_TOKEN

logger = logging.getLogger("dhan_client")

# Module-level singleton — initialized once, reused everywhere
_client: dhanhq | None = None


# ══════════════════════════════════════════════════════════════
# P0-A: SIMULATION HARD LOCK
# ══════════════════════════════════════════════════════════════

class SimulationModeError(RuntimeError):
    """Raised when a real order is attempted in SIMULATION mode.
    
    This is a P0 safety net. If you see this exception, it means
    code tried to place a real broker order while SYSTEM_MODE=SIMULATION.
    Check the call stack in the logs to find the offending code path.
    """
    pass


class _SimulationGuardedClient:
    """
    Wraps the real dhanhq client with a simulation guard on order-placing methods.
    
    All read-only methods (get_positions, get_fund_limits, etc.) pass through.
    All order-placing methods (place_order, place_slice_order, modify_order, etc.)
    are blocked in SIMULATION mode with a hard error + full call stack log.
    """

    # Methods that can place or modify real orders on the broker
    _ORDER_METHODS = frozenset({
        "place_order",
        "place_slice_order",
        "modify_order",
        "cancel_order",
        "place_basket_order",
    })

    def __init__(self, real_client: dhanhq):
        self._real_client = real_client

    def __getattr__(self, name: str):
        """Intercept attribute access. Guard order methods; pass through everything else."""
        if name in self._ORDER_METHODS:
            return self._guarded_order_call(name)
        # Pass through all other attributes (get_positions, get_fund_limits, etc.)
        return getattr(self._real_client, name)

    def _guarded_order_call(self, method_name: str):
        """Returns a wrapper that checks SYSTEM_MODE before calling the real method."""
        def _wrapper(*args, **kwargs):
            mode = os.getenv("SYSTEM_MODE", "SIMULATION").upper()

            if mode == "SIMULATION":
                # Log full call stack so you know exactly where the call came from
                logger.critical("=" * 60)
                logger.critical(
                    "🚨 HARD BLOCK: Real order attempted in SIMULATION mode "
                    "via %s()", method_name
                )
                logger.critical("Call stack:\n%s", "".join(traceback.format_stack()))
                logger.critical("=" * 60)
                raise SimulationModeError(
                    f"HARD BLOCK: {method_name}() called in SIMULATION mode. "
                    f"Call stack logged. Check logs immediately."
                )

            # LIVE / SMALL_CAPITAL — allow the real call
            return getattr(self._real_client, method_name)(*args, **kwargs)

        return _wrapper


# ══════════════════════════════════════════════════════════════
# TOKEN EXPIRY CHECK
# ══════════════════════════════════════════════════════════════

def _check_token_expiry(token: str) -> tuple[bool, int]:
    """
    Lightweight JWT expiry check (no signature verification needed).
    
    Returns (is_valid, hours_until_expiry).
    Returns (True, 999) if token format is unrecognizable (fail-open).
    """
    try:
        # JWT has 3 parts: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning("Token format not recognized as JWT — skipping expiry check")
            return True, 999

        # Decode payload (add padding if needed)
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)

        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")

        if exp is None:
            logger.warning("Token has no 'exp' claim — cannot check expiry")
            return True, 999

        now = datetime.now(timezone.utc).timestamp()
        hours_left = (exp - now) / 3600

        return hours_left > 0, int(hours_left)

    except (ValueError, json.JSONDecodeError, KeyError, Exception) as e:
        # Fail-open: if we can't parse the token, don't block trading
        # but log it so the operator knows
        logger.warning(f"Token expiry check failed (non-fatal): {type(e).__name__}: {e}")
        return True, 999


# ══════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════

def get_dhan_client() -> dhanhq:
    """
    Returns the initialized Dhan API client.
    Creates it on first call; returns cached instance thereafter.
    
    In SIMULATION mode, the returned client is wrapped with a guard
    that blocks all order-placing methods (P0-A).
    
    Raises RuntimeError if token is expired.
    Logs warning if token expires within 2 hours.
    """
    global _client
    if _client is None:
        # ── Token Expiry Guard ──
        is_valid, hours_left = _check_token_expiry(ACCESS_TOKEN)

        if not is_valid:
            raise RuntimeError(
                "🚨 DHAN ACCESS TOKEN HAS EXPIRED!\n"
                "   → Update DHAN_ACCESS_TOKEN in .env\n"
                "   → Generate at: https://dhanhq.co → My Account → API\n"
                "   → System CANNOT trade with an expired token."
            )

        if hours_left < 2:
            logger.warning(
                f"⚠️ Dhan token expires in ~{hours_left}h! "
                f"Update .env ASAP to avoid mid-session failure."
            )
        elif hours_left < 8:
            logger.info(f"ℹ️ Dhan token valid for ~{hours_left}h")

        pool_config = {"max_retries": 0}
        real_client = dhanhq(CLIENT_ID, ACCESS_TOKEN, pool=pool_config)
        # 🚀 Fix for Latency/Orphaned Threads: Eliminate 20s stall via tuple timeout (Connect, Read)
        real_client.timeout = (0.5, 2.0)
        logger.info(f"Dhan API client initialized ✓ (token valid ~{hours_left}h)")

        # ── P0-A: Wrap with simulation guard ──
        _client = _SimulationGuardedClient(real_client)

    return _client
