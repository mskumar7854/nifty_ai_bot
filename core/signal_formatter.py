"""
============================================
📱 SIGNAL FORMATTER v4.8
Unified Telegram signal message builder.

Produces the two-section format:
  Section 1: Execution Block (Nifty + Premium levels)
  Section 2: AI Context Block (Confidence, Regime, Scores)

Used by all 3 TelegramController notification modes
(AUTO, SEMI_AUTO, MANUAL) to ensure consistent formatting.

⚠️ AI WARNING: This module is display-only.
It does NOT modify signal state or trigger execution.
============================================
"""

import time
from datetime import datetime, timedelta
from typing import Optional

from models.signals import SignalStatus


def format_signal_message(signal, snapshot_summary: Optional[dict] = None) -> str:
    """
    Formats a Signal object into the two-section Telegram message.

    Args:
        signal: Signal dataclass with all trade data
        snapshot_summary: Optional dict with live market context:
            {"spot", "pcr", "vix", "vwap"}

    Returns:
        HTML-formatted string ready for Telegram parse_mode='HTML'
    """
    # ── Extract Signal Properties ──
    sig_type = signal.signal_type.value  # BUY_CE / BUY_PE
    direction_val = signal.direction.value.upper()
    
    # Action label + emoji
    if "CE" in sig_type:
        action_emoji = "🟢"
        action_label = "BUY"
        option_type = "CE"
    elif "PE" in sig_type:
        action_emoji = "🔴"
        action_label = "BUY"
        option_type = "PE"
    else:
        action_emoji = "⚪"
        action_label = sig_type
        option_type = ""

    # ── Instrument Details (from options resolver metadata) ──
    instrument = signal.metadata.get("instrument", {})
    symbol = getattr(signal, "symbol", "") or instrument.get("symbol", "NIFTY")
    expiry_raw = instrument.get("expiry", "")
    
    # Format expiry date nicely
    expiry_str = _format_expiry(expiry_raw) if expiry_raw else "—"

    # ── Premium Levels (option premium) ──
    premium = signal.metadata.get("premium_levels", {})
    has_premium = bool(premium)
    p_entry = premium.get("premium_entry", 0)
    p_sl = premium.get("premium_sl", 0)
    p_t1 = premium.get("premium_t1", 0)
    p_t2 = premium.get("premium_t2", 0)
    p_t3 = premium.get("premium_t3", 0)

    # ── Nifty Spot Levels ──
    spot_entry = signal.entry_price
    spot_sl = signal.stop_loss
    spot_t1 = signal.target_1
    spot_t2 = signal.target_2

    # ── R:R Ratio + Rupee Risk ──
    # Prefer premium-based R:R if available, fallback to spot-based
    if has_premium and p_entry > 0 and p_sl > 0 and p_t1 > 0:
        risk_pts = abs(p_entry - p_sl)
        reward_pts = abs(p_t1 - p_entry)
        rr = round(reward_pts / risk_pts, 1) if risk_pts > 0.01 else signal.risk_reward_ratio
    else:
        risk_pts = abs(spot_entry - spot_sl) if spot_entry > 0 and spot_sl > 0 else 0
        reward_pts = abs(spot_t1 - spot_entry) if spot_t1 > 0 and spot_entry > 0 else 0
        rr = signal.risk_reward_ratio
    rr_str = f"1:{rr}" if rr > 0 else "—"

    # ── Signal Freshness & Status ──
    age_seconds = int(time.time() - signal.created_at) if signal.created_at else 0
    age_str = f"{age_seconds}s" if age_seconds < 120 else f"{age_seconds // 60}m"

    # Determine signal status based on age vs expiry
    expiry_secs_for_status = signal.metadata.get("signal_expiry_seconds", 30)
    if age_seconds > expiry_secs_for_status:
        status = SignalStatus.EXPIRED
    elif age_seconds < 5:
        status = SignalStatus.FRESH
    elif age_seconds < expiry_secs_for_status * 0.7:
        status = SignalStatus.ACTIVE
    else:
        status = SignalStatus.EXPIRING

    # ── Validity Time ──
    # Get expiry seconds from settings default (30s) or signal metadata
    expiry_secs = signal.metadata.get("signal_expiry_seconds", 30)
    valid_until = datetime.fromtimestamp(signal.created_at + expiry_secs) if signal.created_at else None
    valid_str = valid_until.strftime("%I:%M %p") if valid_until else "—"

    # ── Trade ID ──
    trade_id = signal.id if signal.id else "—"
    # Truncate UUID-style IDs but keep readable IDs intact
    if len(str(trade_id)) > 12:
        trade_id_display = str(trade_id)[:8]
    else:
        trade_id_display = str(trade_id)

    # ── Confluence ──
    conf = signal.confluence
    if conf:
        confluence_str = f"{conf.bullish_agents} Bull / {conf.bearish_agents} Bear"
        agreement_pct = round(conf.confluence_ratio * 100) if conf.confluence_ratio else 0
    else:
        confluence_str = "—"
        agreement_pct = 0

    # ── Market Context from snapshot ──
    snap = snapshot_summary or {}
    spot_price = snap.get("spot", spot_entry)
    pcr_val = snap.get("pcr", 0)
    vix_val = snap.get("vix", 0)

    # ── Spread & Liquidity ──
    quote = signal.metadata.get("quote")
    if quote and hasattr(quote, "spread_pct") and hasattr(quote, "ask") and quote.ask > 0:
        spread_pct = round(quote.spread_pct, 2)
        if spread_pct < 1.0:
            liquidity = "EXCELLENT"
        elif spread_pct < 3.0:
            liquidity = "GOOD"
        elif spread_pct < 5.0:
            liquidity = "OK"
        else:
            liquidity = "POOR"
    else:
        spread_pct = None
        liquidity = None

    # ── Agent Sub-Scores ──
    agent_scores = signal.metadata.get("agent_scores", {})

    # ── Regime ──
    regime_str = signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime)
    grade_str = signal.grade.value if hasattr(signal.grade, "value") else str(signal.grade)
    strength_str = signal.strength.value if hasattr(signal.strength, "value") else str(signal.strength)

    # ── Reasons (top 3, bullet points) ──
    reasons = signal.reasons[:3] if signal.reasons else []

    # ── Setup Quality Score (composite 0-100) ──
    setup_score, setup_drivers = _compute_setup_quality(
        confidence=signal.confidence,
        agreement_pct=agreement_pct,
        rr=rr,
        regime_str=regime_str,
        liquidity=liquidity,
    )
    setup_grade = _score_to_grade(setup_score)

    # ── Market Bias / Structure ──
    market_bias = _extract_market_bias(signal)

    # ═══════════════════════════════════════════
    # BUILD THE MESSAGE
    # ═══════════════════════════════════════════

    lines = []

    # ── HEADER ──
    lines.append(f"🚨 <b>AI TRADE ALERT</b>")
    lines.append("")
    lines.append(f"Setup Quality : <b>{setup_grade}</b>")
    lines.append("")
    lines.append(f"{action_emoji} <b>{action_label} {symbol}</b>")
    if expiry_str != "—":
        lines.append(f"Expiry: {expiry_str}")
    lines.append("")

    # ── NIFTY LEVELS ──
    lines.append(f"<b>NIFTY LEVELS</b>")
    lines.append(f"Entry : {spot_entry:,.0f}")
    lines.append(f"SL    : {spot_sl:,.0f}")
    if spot_t1 > 0:
        lines.append(f"T1    : {spot_t1:,.0f}")
    if spot_t2 > 0:
        lines.append(f"T2    : {spot_t2:,.0f}")
    lines.append("")

    # ── OPTION PREMIUM ──
    if has_premium:
        lines.append(f"<b>OPTION PREMIUM</b>")
        lines.append(f"Entry : ₹{p_entry:,.1f}")
        lines.append(f"SL    : ₹{p_sl:,.1f}")
        if p_t1 > 0:
            lines.append(f"T1    : ₹{p_t1:,.1f}")
        if p_t2 > 0:
            lines.append(f"T2    : ₹{p_t2:,.1f}")
        if p_t3 > 0:
            lines.append(f"T3    : ₹{p_t3:,.1f}")
        lines.append("")

    # ── Risk & Reward ──
    if risk_pts > 0:
        lines.append(f"Risk   : ₹{risk_pts:,.0f}")
    if reward_pts > 0:
        lines.append(f"Reward : ₹{reward_pts:,.0f}")
    lines.append(f"R:R    : <b>{rr_str}</b>")
    lines.append("")

    # ── AI Context (essential only) ──
    lines.append(f"<b>📊 AI ANALYSIS</b>")
    lines.append(f"Confidence : <b>{signal.confidence:.0f}%</b>")
    lines.append(f"Regime     : {regime_str}")
    if market_bias:
        lines.append(f"Structure  : {market_bias}")
    lines.append("")

    # ── Status Footer ──
    lines.append(f"Status : {status.value}")
    lines.append(f"Valid  : {valid_str}")


    return "\n".join(lines)


def format_trade_close_message(trade_id: str, pnl: float, outcome: str,
                                symbol: str = "", hold_mins: float = 0) -> str:
    """
    Formats a trade close notification.
    Kept simple and focused — traders need result, not analysis.
    """
    outcome_upper = outcome.upper()
    if outcome_upper == "WIN":
        emoji, colour = "🟢", "WIN"
    elif outcome_upper == "LOSS":
        emoji, colour = "🔴", "LOSS"
    else:
        emoji, colour = "⚪", "BREAKEVEN"

    pnl_sign = "+" if pnl >= 0 else ""
    
    lines = [
        f"{emoji} <b>Trade Closed — {colour}</b>",
        "",
        f"ID     : <code>{str(trade_id)[:8]}</code>",
    ]
    
    if symbol:
        lines.append(f"Symbol : {symbol}")
    
    lines.append(f"PnL    : <b>₹{pnl_sign}{pnl:,.0f}</b>")
    lines.append(f"Result : <b>{colour}</b>")
    
    if hold_mins > 0:
        lines.append(f"Held   : {hold_mins:.0f} min")

    return "\n".join(lines)


# ── HELPERS ──

def _format_expiry(raw: str) -> str:
    """Convert '2026-06-04' to '04-Jun-2026'."""
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
        return dt.strftime("%d-%b-%Y")
    except (ValueError, TypeError):
        return raw


def _score_label(key: str) -> str:
    """Human-readable label for agent score keys."""
    labels = {
        "oi": "OI",
        "trend": "Trend",
        "flow": "Flow",
        "volatility": "Volatility",
        "momentum": "Momentum",
        "structure": "Structure",
        "price_action": "Price Act",
    }
    return labels.get(key, key.title())


def _compute_setup_quality(confidence: float, agreement_pct: int, rr: float,
                           regime_str: str, liquidity: Optional[str]) -> tuple:
    """
    Composite Setup Quality Score (0-100) with quality drivers.

    Weighted formula:
      - Confidence (0-100)     × 0.35  → max 35 pts
      - Confluence agreement   × 0.25  → max 25 pts
      - R:R ratio (capped 3)   × 0.15  → max 15 pts
      - Regime alignment       × 0.15  → max 15 pts
      - Liquidity              × 0.10  → max 10 pts

    Returns:
        (score: int, drivers: list[str]) — drivers are '+'/'-' lines
        explaining what helped and what hurt the score.
    """
    drivers = []

    # 1. Confidence (already 0-100)
    conf_pts = min(confidence, 100) * 0.35
    if confidence >= 80:
        drivers.append("+ Strong Confidence")
    elif confidence < 65:
        drivers.append("- Low Confidence")

    # 2. Confluence agreement (0-100)
    agree_pts = min(agreement_pct, 100) * 0.25
    if agreement_pct >= 75:
        drivers.append("+ Strong Confluence")
    elif agreement_pct < 50:
        drivers.append("- Weak Confluence")

    # 3. R:R ratio — cap contribution at R:R=3.0
    rr_norm = min(rr / 3.0, 1.0) * 100 if rr > 0 else 0
    rr_pts = rr_norm * 0.15
    if rr >= 2.0:
        drivers.append("+ Good R:R")
    elif rr < 1.0:
        drivers.append("- Poor R:R")
    elif rr < 1.5:
        drivers.append("- Average R:R")

    # 4. Regime alignment
    regime_scores = {
        "TRENDING_UP": 100, "TRENDING_DOWN": 100,
        "BREAKOUT": 90,
        "SQUEEZE": 70,
        "RANGING": 40,
        "VOLATILE": 20,
    }
    regime_norm = regime_scores.get(regime_str, 50)
    regime_pts = regime_norm * 0.15
    if regime_norm >= 90:
        drivers.append("+ Strong Trend")
    elif regime_norm <= 40:
        drivers.append("- Weak Regime")

    # 5. Liquidity
    liq_scores = {"EXCELLENT": 100, "GOOD": 80, "OK": 50, "POOR": 10}
    liq_norm = liq_scores.get(liquidity or "", 60)
    liq_pts = liq_norm * 0.10
    if liquidity == "POOR":
        drivers.append("- Poor Liquidity")

    raw = conf_pts + agree_pts + rr_pts + regime_pts + liq_pts
    return min(int(round(raw)), 100), drivers


def _score_to_grade(score: int) -> str:
    """Map composite score to letter grade."""
    if score >= 92:
        return "A+"
    elif score >= 82:
        return "A"
    elif score >= 72:
        return "B+"
    elif score >= 62:
        return "B"
    elif score >= 50:
        return "C"
    else:
        return "D"


def _extract_market_bias(signal) -> str:
    """
    Extract market structure / bias from signal context.
    Checks reasons for BOS/CHoCH patterns, then falls back to direction.
    """
    # 1. Check reasons for structure keywords
    for reason in (signal.reasons or []):
        r_upper = reason.upper()
        if "BOS" in r_upper:
            direction = "BULLISH" if "BULL" in r_upper or "UP" in r_upper else "BEARISH"
            return f"BOS {direction}"
        if "CHOCH" in r_upper:
            return f"CHoCH detected"

    # 2. Check agent_votes for structure agent
    votes = getattr(signal, "agent_votes", {}) or {}
    struct_vote = votes.get("structure", {})
    if struct_vote:
        struct_dir = struct_vote.get("direction", "")
        struct_conf = struct_vote.get("confidence", 0)
        if struct_conf > 0.5 and struct_dir in ("BULLISH", "BEARISH"):
            return f"{struct_dir} structure"

    # 3. Fallback to overall direction
    direction_val = signal.direction.value.upper() if hasattr(signal.direction, "value") else ""
    if direction_val in ("BULLISH", "BEARISH"):
        return f"{direction_val} bias"

    return ""
