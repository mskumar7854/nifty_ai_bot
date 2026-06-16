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
    
    Includes an LRU cache for high-frequency methods (option_chain, expiry_list)
    to prevent Dhan 805 Rate Limit errors across components.
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
        self._api_cache = {}
        self._cache_lock = __import__('threading').Lock()
        self._rate_limit_until = 0.0
        self._failure_count = 0
        self._telemetry = {
            "quote_requests": 0,
            "quote_cache_hits": 0,
            "quote_api_calls": 0,
            "quote_805_errors": 0,
            "circuit_breaker_trips": 0,
            "stale_cache_served": 0,
            "signals_blocked_by_quotes": 0,
            "signals_saved_by_cache": 0,
            "cache_hit_rate": 0.0
        }

    def _get_normalized_key(self, method_name: str, *args, **kwargs):
        # Map positional and keyword args to a stable format to prevent mismatch
        if method_name == "option_chain":
            security_id = kwargs.get("under_security_id") or (args[0] if len(args) > 0 else "")
            segment = kwargs.get("under_exchange_segment") or (args[1] if len(args) > 1 else "")
            expiry = kwargs.get("expiry") or (args[2] if len(args) > 2 else "")
            return f"option_chain_{security_id}_{segment}_{expiry}"
        elif method_name == "expiry_list":
            security_id = kwargs.get("under_security_id") or (args[0] if len(args) > 0 else "")
            segment = kwargs.get("under_exchange_segment") or (args[1] if len(args) > 1 else "")
            return f"expiry_list_{security_id}_{segment}"
        else:
            return f"{method_name}_{str(args)}_{str(kwargs)}"

    def __getattr__(self, name: str):
        """Intercept attribute access. Guard order methods; pass through everything else."""
        if name in self._ORDER_METHODS:
            return self._guarded_order_call(name)
        if name in ("option_chain", "expiry_list"):
            return self._cached_api_call(name)
        # Pass through all other attributes (get_positions, get_fund_limits, etc.)
        return getattr(self._real_client, name)

    def _cached_api_call(self, method_name: str):
        import time as _time
        import logging
        
        local_logger = logging.getLogger("dhan_client.cache")
        
        def _wrapper(*args, **kwargs):
            # Extract is_execution flag from kwargs (custom flag to determine TTL / risk logic)
            is_execution = kwargs.pop("is_execution", False)
            
            # Key normalization
            key = self._get_normalized_key(method_name, *args, **kwargs)
            now = _time.time()
            
            # Increment request count
            self._telemetry["quote_requests"] += 1
            
            # Check circuit breaker
            if now < self._rate_limit_until:
                self._telemetry["circuit_breaker_trips"] += 1
                
                # Check stale cache fallback (up to 60s)
                if key in self._api_cache:
                    timestamp, cached_result = self._api_cache[key]
                    age = now - timestamp
                    
                    if age < 60.0:
                        self._telemetry["stale_cache_served"] += 1
                        
                        # Calculate cache hit rate before returning
                        reqs = self._telemetry["quote_requests"]
                        hits = self._telemetry["quote_cache_hits"] + self._telemetry["stale_cache_served"]
                        self._telemetry["cache_hit_rate"] = round((hits / reqs) * 100, 1) if reqs > 0 else 0.0
                        
                        # Copy cached result and inject stale metadata
                        fallback_result = dict(cached_result) if isinstance(cached_result, dict) else cached_result
                        if isinstance(fallback_result, dict):
                            fallback_result["cache_metadata"] = {
                                "is_stale": True,
                                "cache_age": age,
                                "source": "cache"
                            }
                        
                        local_logger.warning(
                            f"⚠️ Central Circuit Breaker ACTIVE. Serving stale cache fallback for {method_name} "
                            f"(age={age:.1f}s, is_execution={is_execution})"
                        )
                        return fallback_result

                # If no cache fallback exists or it is too old, return rate limit error representation
                local_logger.error(
                    f"🚨 Central Circuit Breaker ACTIVE and no fresh cache for {method_name}. "
                    f"Returning rate limit error response."
                )
                return {"status": "error", "remarks": "RATE_LIMIT_ACTIVE", "data": {"data": {"error": "805"}}}

            # Determine cache TTL
            # - For option_chain: 5.0s for execution context, 30.0s for analysis context
            # - For expiry_list: 1 hour (3600s)
            if method_name == "option_chain":
                ttl = 5.0 if is_execution else 30.0
            else:
                ttl = 3600.0

            # Check fresh cache hit
            if key in self._api_cache:
                timestamp, cached_result = self._api_cache[key]
                age = now - timestamp
                if age < ttl:
                    self._telemetry["quote_cache_hits"] += 1
                    
                    # Update hit rate
                    reqs = self._telemetry["quote_requests"]
                    hits = self._telemetry["quote_cache_hits"] + self._telemetry["stale_cache_served"]
                    self._telemetry["cache_hit_rate"] = round((hits / reqs) * 100, 1) if reqs > 0 else 0.0
                    
                    # Return cached result with fresh metadata
                    fresh_result = dict(cached_result) if isinstance(cached_result, dict) else cached_result
                    if isinstance(fresh_result, dict):
                        fresh_result["cache_metadata"] = {
                            "is_stale": False,
                            "cache_age": age,
                            "source": "cache"
                        }
                    return fresh_result

            # Cache miss: execute actual API call
            with self._cache_lock:
                # Double-check fresh cache hit inside the lock to prevent cache stampede
                now = _time.time()
                if key in self._api_cache:
                    timestamp, cached_result = self._api_cache[key]
                    age = now - timestamp
                    if age < ttl:
                        self._telemetry["quote_cache_hits"] += 1
                        
                        # Update hit rate
                        reqs = self._telemetry["quote_requests"]
                        hits = self._telemetry["quote_cache_hits"] + self._telemetry["stale_cache_served"]
                        self._telemetry["cache_hit_rate"] = round((hits / reqs) * 100, 1) if reqs > 0 else 0.0
                        
                        # Return cached result with fresh metadata
                        fresh_result = dict(cached_result) if isinstance(cached_result, dict) else cached_result
                        if isinstance(fresh_result, dict):
                            fresh_result["cache_metadata"] = {
                                "is_stale": False,
                                "cache_age": age,
                                "source": "cache"
                            }
                        return fresh_result

                self._telemetry["quote_api_calls"] += 1
                try:
                    result = getattr(self._real_client, method_name)(*args, **kwargs)
                except Exception as e:
                    local_logger.error(f"API call to {method_name} failed: {e}")
                    raise e

                # Inspect result for rate limits
                is_rate_limited = False
                if isinstance(result, dict):
                    status = str(result.get("status", "")).lower()
                    # Only check for 805 if the API actually reported a failure
                    if status == "failure" or status == "error":
                        error_str = str(result.get("remarks", "")) + " " + str(result.get("errorCode", "")) + " " + str(result.get("errorMsg", ""))
                        inner_data = result.get("data", {})
                        if isinstance(inner_data, dict):
                            error_str += " " + str(inner_data.get("errorCode", "")) + " " + str(inner_data.get("errorMsg", ""))
                        if "805" in error_str:
                            is_rate_limited = True

                if is_rate_limited:
                    local_logger.error(f"RAW {method_name.upper()} RESPONSE: %s", repr(result))
                    local_logger.error(f"RAW {method_name.upper()} TYPE: %s", type(result))
                    self._telemetry["quote_805_errors"] += 1
                    self._failure_count += 1
                    backoff = min(30 * (2 ** (self._failure_count - 1)), 300)
                    self._rate_limit_until = now + backoff
                    local_logger.warning(
                        f"🚨 Dhan API rate limit 805 detected in {method_name}! "
                        f"Tripping central circuit breaker for {backoff}s."
                    )

                    # Serve stale cache if available as emergency fallback
                    if key in self._api_cache:
                        timestamp, cached_result = self._api_cache[key]
                        age = now - timestamp
                        self._telemetry["stale_cache_served"] += 1
                        
                        fallback_result = dict(cached_result) if isinstance(cached_result, dict) else cached_result
                        if isinstance(fallback_result, dict):
                            fallback_result["cache_metadata"] = {
                                "is_stale": True,
                                "cache_age": age,
                                "source": "cache"
                            }
                        return fallback_result
                else:
                    # Cache successful response
                    if isinstance(result, dict) and (result.get("status") == "success" or "data" in result):
                        self._api_cache[key] = (now, result)
                        self._failure_count = 0  # Reset on successful API response
                        
                        # Inject fresh API metadata
                        result["cache_metadata"] = {
                            "is_stale": False,
                            "cache_age": 0.0,
                            "source": "api"
                        }

                # Update cache hit rate
                reqs = self._telemetry["quote_requests"]
                hits = self._telemetry["quote_cache_hits"] + self._telemetry["stale_cache_served"]
                self._telemetry["cache_hit_rate"] = round((hits / reqs) * 100, 1) if reqs > 0 else 0.0

                return result
            
        return _wrapper

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
        # Increased read timeout to 5.0s to ensure option chain/large data fetches succeed under load
        real_client.timeout = (0.5, 5.0)
        logger.info(f"Dhan API client initialized ✓ (token valid ~{hours_left}h)")

        # ── P0-A: Wrap with simulation guard ──
        _client = _SimulationGuardedClient(real_client)

    return _client


def get_dhan_telemetry() -> dict:
    """Public helper function to get current telemetry of the central wrapper client."""
    global _client
    if _client is not None and hasattr(_client, "_telemetry"):
        return _client._telemetry
    return {
        "quote_requests": 0,
        "quote_cache_hits": 0,
        "quote_api_calls": 0,
        "quote_805_errors": 0,
        "circuit_breaker_trips": 0,
        "stale_cache_served": 0,
        "signals_blocked_by_quotes": 0,
        "signals_saved_by_cache": 0,
        "cache_hit_rate": 0.0
    }
