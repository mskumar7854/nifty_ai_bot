"""
============================================
🌑 SHADOW EXECUTION ENGINE

Purely observational telemetry layer for measuring
Research-to-Runtime execution drift.

Purpose:
  Answers "Would the live market actually have given us the edge we think we have?"
  
Rules:
  1. NEVER mutate runtime behavior.
  2. Runs fully asynchronously (non-blocking).
  3. Uses local timestamps (t0->t3 decay), no dummy pings.
  4. Stores exactly what was executable at the top-of-book.
============================================
"""

import sqlite3
import json
import logging
import asyncio
import uuid
import os
from datetime import datetime
from typing import Dict, Any

from utils.logger import get_logger
from core.execution_fidelity import ExecutionFidelityEngine

logger = get_logger("shadow_exec")


class ShadowExecutionEngine:
    def __init__(self, db_path: str = "data/shadow_execution.db"):
        self.db_path = db_path
        self.logger = logger
        self._init_db()
        
        # Used strictly to calculate the "Theoretical" (replay) baseline
        self.fidelity_engine = ExecutionFidelityEngine()

    def _init_db(self):
        """Initialize the isolated shadow database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                
                # Table 1: Dual-Path Fills & Drift Metrics
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS shadow_records (
                        shadow_id TEXT PRIMARY KEY,
                        signal_id TEXT,
                        intent_id TEXT,
                        snapshot_id TEXT,
                        timestamp TEXT,
                        symbol TEXT,
                        qty INTEGER,
                        
                        -- Theoretical Replay Baseline
                        theo_fill_price REAL,
                        theo_slippage REAL,
                        
                        -- Executable Reality (Top of Book)
                        exec_fill_price REAL,
                        exec_spread REAL,
                        
                        -- Drift & Quality
                        entry_drift REAL,
                        execution_confidence REAL,
                        
                        -- Latency Decay
                        t0_signal_ms REAL,
                        t1_quote_ms REAL,
                        t2_submit_ms REAL,
                        t3_fill_ms REAL,
                        total_latency_ms REAL,
                        
                        -- Metadata
                        raw_payload TEXT
                    )
                """)
                
                # Table 2: Raw Quote Telemetry
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS raw_quotes (
                        shadow_id TEXT PRIMARY KEY,
                        timestamp TEXT,
                        symbol TEXT,
                        bid REAL,
                        ask REAL,
                        ltp REAL,
                        spread_width REAL,
                        quote_age_ms REAL,
                        vix REAL,
                        regime TEXT
                    )
                """)
        except Exception as e:
            self.logger.error(f"Failed to initialize Shadow DB: {e}")

    async def process_signal(
        self,
        signal: Any,
        size_params: Dict,
        t0_signal: datetime,
        t1_quote: datetime,
        t2_submit: datetime
    ):
        """
        FIRE AND FORGET:
        Processes the dual-path execution simulation asynchronously.
        """
        try:
            # 1. Non-blocking isolation
            await asyncio.to_thread(self._process_inner, signal, size_params, t0_signal, t1_quote, t2_submit)
        except Exception as e:
            self.logger.error(f"Shadow Execution Error (Isolated): {e}", exc_info=True)

    def _process_inner(self, signal, size_params, t0_signal, t1_quote, t2_submit):
        """Synchronous inner processing for db writes."""
        t3_fill = datetime.now()
        
        shadow_id = str(uuid.uuid4())
        intent_id = getattr(signal, "intent_id", "")
        signal_id = getattr(signal, "id", "")
        snapshot_id = signal.metadata.get("snapshot_id", "") if hasattr(signal, "metadata") else ""
        
        quote = getattr(signal, "metadata", {}).get("quote")
        vix = size_params.get("volatility", 15.0)
        regime = signal.regime.value if hasattr(signal.regime, "value") else str(signal.regime)
        
        if not quote:
            self.logger.warning("Shadow Execution skipped: Missing quote object.")
            return

        # ── 1. Latency Decay ──
        t0_ms = 0.0
        t1_ms = (t1_quote - t0_signal).total_seconds() * 1000
        t2_ms = (t2_submit - t0_signal).total_seconds() * 1000
        t3_ms = (t3_fill - t0_signal).total_seconds() * 1000
        total_latency = t3_ms

        # ── 2. Raw Quote State ──
        ask = quote.ask
        bid = quote.bid
        ltp = quote.ltp
        spread = ask - bid
        quote_age_ms = (t2_submit - quote.timestamp).total_seconds() * 1000

        # ── 3. Theoretical Execution (Replay Expectations) ──
        # In Replay, we use LTP + Simulation Slippage Model
        theo_result = self.fidelity_engine.simulate_entry(
            signal_price=ltp,
            spot_price=ltp,
            strike=ltp, # Simulating ATM
            option_type="CE" if signal.direction.value.upper() == "BUY" else "PE",
            qty=size_params["qty"],
            regime=regime,
            vix=vix,
            expiry_date=None
        )
        theo_fill = theo_result.fill_price
        theo_slippage = theo_result.slippage_pts

        # ── 4. Executable Execution (Top-of-Book Reality) ──
        # We BUY at the Ask. We SELL at the Bid. (Assuming we trade Options long only, we ALWAYS BUY).
        # We do NOT apply sweep modeling. Just pure top-of-book executable price.
        # But we add latency drift: if latency > 200ms, spread tends to expand slightly against us.
        latency_penalty = max(0, (total_latency - 200) / 1000) * (spread * 0.1) 
        exec_fill = ask + latency_penalty
        
        # ── 5. Entry Drift ──
        # Positive drift = execution reality is WORSE than theoretical backtest (Slippage consumes edge)
        entry_drift = exec_fill - theo_fill

        # ── 6. Execution Confidence Scoring ──
        exec_confidence = self._calculate_execution_confidence(
            spread_pct=(spread / ltp) if ltp > 0 else 0,
            quote_age_ms=quote_age_ms,
            vix=vix,
            total_latency_ms=total_latency
        )

        # ── 7. Persistence ──
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Raw Quote
                conn.execute("""
                    INSERT INTO raw_quotes 
                    (shadow_id, timestamp, symbol, bid, ask, ltp, spread_width, quote_age_ms, vix, regime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shadow_id, t3_fill.isoformat(), signal.symbol, bid, ask, ltp, 
                    spread, quote_age_ms, vix, regime
                ))
                
                # Shadow Record
                payload = {
                    "signal_confidence": signal.confidence,
                    "quality": signal.metadata.get("quality", "UNKNOWN") if hasattr(signal, "metadata") else "UNKNOWN",
                    "t1_delta_ms": round(t1_ms, 1),
                    "t2_delta_ms": round(t2_ms, 1),
                    "t3_delta_ms": round(t3_ms, 1)
                }
                
                conn.execute("""
                    INSERT INTO shadow_records
                    (shadow_id, signal_id, intent_id, snapshot_id, timestamp, symbol, qty,
                     theo_fill_price, theo_slippage, exec_fill_price, exec_spread,
                     entry_drift, execution_confidence, 
                     t0_signal_ms, t1_quote_ms, t2_submit_ms, t3_fill_ms, total_latency_ms, raw_payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    shadow_id, signal_id, intent_id, snapshot_id, t3_fill.isoformat(), signal.symbol, size_params["qty"],
                    theo_fill, theo_slippage, exec_fill, spread,
                    entry_drift, exec_confidence,
                    t0_ms, t1_ms, t2_ms, t3_ms, total_latency, json.dumps(payload)
                ))
                
            self.logger.info(f"🌑 SHADOW CAPTURE | Drift: {entry_drift:+.2f} pts | Theo: ₹{theo_fill:.1f} | Exec: ₹{exec_fill:.1f} | Latency: {total_latency:.0f}ms | ExecConf: {exec_confidence:.2f}")
            
        except Exception as e:
            self.logger.error(f"Failed to persist shadow record: {e}")

    def _calculate_execution_confidence(self, spread_pct: float, quote_age_ms: float, vix: float, total_latency_ms: float) -> float:
        """
        Execution Market Conditions Score (0.0 to 1.0)
        Is the microstructure hostile or favorable right now?
        """
        score = 1.0
        
        # Spread penalty: normal ATM spread is ~0.15-0.3%. Above 0.5% is hostile.
        if spread_pct > 0.005:
            score -= (spread_pct - 0.005) * 50  # Heavy penalty for wide spread
            
        # Age penalty: anything over 500ms starts decaying confidence
        if quote_age_ms > 500:
            score -= (quote_age_ms - 500) / 2000
            
        # Latency penalty: slow processing pipeline eats edge
        if total_latency_ms > 200:
            score -= (total_latency_ms - 200) / 1000
            
        # VIX extremes: high vix makes executable spreads vanish
        if vix > 18.0:
            score -= (vix - 18.0) * 0.02
            
        return max(0.0, min(1.0, score))
