"""
============================================
DNS HEALTH MONITOR
Lightweight DNS resolution checker to detect
system-wide network/DNS outages before they
cascade into bootstrap loops and stale feeds.
============================================
"""

import socket
import time
import logging

logger = logging.getLogger("dns_health")

# ── Host classification ──
# CRITICAL: Must resolve for trading to proceed. Failure here blocks all API calls.
# AUXILIARY: Nice-to-have. Failure is logged but doesn't block trading.
#            Used to distinguish "Dhan-only outage" from "system-wide DNS outage".
CRITICAL_HOSTS = ["api.dhan.co"]
AUXILIARY_HOSTS = ["api.telegram.org"]

# ── Module-level state ──
_last_check_ts: float = 0.0
_last_result: bool = True
_CHECK_INTERVAL: float = 10.0  # Don't probe more than once every 10s
_consecutive_failures: int = 0

# Per-host status for telemetry
_host_status: dict = {}


def dns_ok(force: bool = False) -> bool:
    """
    Check if DNS resolution is working for CRITICAL hosts.

    Results are cached for 10 seconds to avoid hammering DNS on every
    engine cycle (~1/sec). Pass force=True to bypass the cache
    (e.g. at boot time).

    Returns True only if ALL CRITICAL hosts resolve successfully.
    Auxiliary hosts are checked for telemetry but don't affect the result.
    """
    global _last_check_ts, _last_result, _consecutive_failures, _host_status
    now = time.time()

    if not force and (now - _last_check_ts) < _CHECK_INTERVAL:
        return _last_result

    _last_check_ts = now
    critical_ok = True

    # ── Check critical hosts (Dhan) ──
    for host in CRITICAL_HOSTS:
        try:
            socket.gethostbyname(host)
            _host_status[host] = True
        except (socket.gaierror, OSError):
            _host_status[host] = False
            critical_ok = False

    # ── Check auxiliary hosts (Telegram) — telemetry only ──
    for host in AUXILIARY_HOSTS:
        try:
            socket.gethostbyname(host)
            _host_status[host] = True
        except (socket.gaierror, OSError):
            _host_status[host] = False

    # ── Logging ──
    if not critical_ok:
        _consecutive_failures += 1
        if _consecutive_failures == 1:
            failed = [h for h in CRITICAL_HOSTS if not _host_status.get(h, True)]
            logger.error(f"🌐 DNS RESOLUTION FAILED for critical host(s): {', '.join(failed)}")
        elif _consecutive_failures % 10 == 0:
            logger.error(
                f"🌐 DNS still failing ({_consecutive_failures} consecutive failures)"
            )
        _last_result = False
        return False

    # ── Recovery path ──
    if not _last_result:
        logger.info(
            f"✅ DNS resolution restored after {_consecutive_failures} consecutive failures"
        )
    _consecutive_failures = 0
    _last_result = True

    # Log auxiliary failures as warnings (don't block trading)
    aux_failed = [h for h in AUXILIARY_HOSTS if not _host_status.get(h, True)]
    if aux_failed and _consecutive_failures == 0:
        logger.warning(f"⚠️ Auxiliary DNS failure (non-blocking): {', '.join(aux_failed)}")

    return True


def get_dns_status() -> dict:
    """
    Returns current DNS health for telemetry/dashboard consumption.
    Per-host resolution status enables precise root cause analysis.
    """
    return {
        "dns_healthy": _last_result,
        "dhan_dns_ok": _host_status.get("api.dhan.co", True),
        "telegram_dns_ok": _host_status.get("api.telegram.org", True),
        "dns_consecutive_failures": _consecutive_failures,
        "dns_last_check_ts": _last_check_ts,
    }
