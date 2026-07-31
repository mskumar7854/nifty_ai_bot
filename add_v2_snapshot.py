import re

with open("core/pipelines/decision_pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()

# Add _record_v2_snapshot method to DecisionPipeline class
record_method = """
    def _record_v2_snapshot(self, signal, snapshot, outputs=None, filter_result=None, final_decision="REJECTED", rejection_reason=""):
        if signal.signal_type == SignalType.NO_TRADE:
            return
            
        try:
            from models.snapshot_v2 import DecisionSnapshotV2, SnapshotMetadata, AgentOpinion, GateResult, ReplayStatus
            from core.snapshot_v2 import persist_snapshot_v2
            import datetime
            
            mode_str = self.settings.system_mode.mode if hasattr(self.settings.system_mode, "mode") else str(self.settings.system_mode)
            
            metadata = SnapshotMetadata(
                snapshot_id=signal.id,
                timestamp=datetime.datetime.now().isoformat(),
                symbol="NIFTY",
                expiry="UNKNOWN",
                mode=mode_str
            )
            
            market_json = {
                "spot_price": getattr(snapshot, "price", 0.0),
                "vix": getattr(snapshot, "vix", None),
                "atr": getattr(snapshot, "atr", None),
            }
            
            agents_json = {}
            if outputs:
                for name, out in outputs.items():
                    if isinstance(out, dict):
                        agents_json[name] = AgentOpinion(signal=out.get("direction", "UNKNOWN"), confidence=out.get("confidence", 0.0), details=out)
                    elif hasattr(out, "direction"):
                        agents_json[name] = AgentOpinion(signal=out.direction, confidence=out.confidence, details=getattr(out, "details", {}))
            
            conf_json = {
                "raw": getattr(signal, "confidence", 0.0),
                "calibrated": signal.metadata.get("calibrated_pwin", getattr(signal, "confidence", 0.0))
            }
            
            confluence_json = {}
            if getattr(signal, "confluence", None):
                confluence_json = {
                    "ratio": signal.confluence.confluence_ratio,
                    "bullish": signal.confluence.bullish_agents,
                    "bearish": signal.confluence.bearish_agents
                }
                
            ev_json = getattr(signal, "ev_info", {})
            
            gate_results = {}
            if filter_result and hasattr(filter_result, "gate_details"):
                for g in filter_result.gate_details:
                    gate_results[g.get("gate", "Unknown")] = GateResult(
                        passed=g.get("pass", False),
                        actual=g.get("score", 0.0),
                        required=0.0,
                        detail=g.get("detail", "")
                    )
                    
            decision_json = {
                "action": final_decision,
                "reason": rejection_reason
            }
            
            execution_json = {}
            
            replay_status = ReplayStatus(
                deterministic=True,
                missing_fields=[],
                fallback_values=[]
            )
            
            snap_v2 = DecisionSnapshotV2(
                metadata=metadata,
                market=market_json,
                agents=agents_json,
                confidence=conf_json,
                confluence=confluence_json,
                expected_value=ev_json,
                structure={},
                risk={},
                gate_results=gate_results,
                decision=decision_json,
                execution=execution_json,
                event_timeline={},
                replay=replay_status
            )
            persist_snapshot_v2(snap_v2)
        except Exception as e:
            logger.error(f"Failed to record V2 snapshot: {e}")

"""

# Insert it before evaluate method
code = code.replace("    def evaluate(", record_method + "\n    def evaluate(")

# Now replace the old try/except block for build_snapshot
old_snapshot_block = """            # Shadow Journal
            try:
                from core.snapshot import build_snapshot, persist_snapshot
                _gap_mgr = getattr(self.decision_engine, "gap_penalty_manager", None)
                _gap_status = _gap_mgr.get_status() if _gap_mgr else {}
                rej_snap = build_snapshot(
                    signal=signal, snapshot=snapshot, filter_result=filter_result,
                    agent_outputs=outputs, gate_results={}, final_decision="REJECTED",
                    rejection_reason=rej_reason, gap_context={
                        "gap_penalty_active": _gap_mgr.is_active() if _gap_mgr else False,
                        "gap_penalty_multiplier": _gap_status.get("multiplier", 1.0),
                        "gap_severity":  _gap_status.get("severity", "NONE"),
                        "gap_points":    _gap_status.get("gap_points", 0.0),
                    }
                )
                persist_snapshot(rej_snap)
            except Exception:
                pass"""

new_snapshot_block = """            self._record_v2_snapshot(signal, snapshot, outputs, filter_result, "REJECTED", rej_reason)"""

code = code.replace(old_snapshot_block, new_snapshot_block)

# Add it to EXECUTE
old_execute = """        self.trend_tracker.record_trade_execution(sig_dir_str, snapshot.price)
        
        return signal, log_entry, latencies["decision_ms"]"""

new_execute = """        self.trend_tracker.record_trade_execution(sig_dir_str, snapshot.price)
        
        self._record_v2_snapshot(signal, snapshot, outputs, filter_result, "EXECUTE", "Passed all gates")
        
        return signal, log_entry, latencies["decision_ms"]"""

code = code.replace(old_execute, new_execute)

# Simulation guard
old_sim_guard = """                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                return None, {}, latencies["decision_ms"]"""

new_sim_guard = """                self._record_v2_snapshot(signal, snapshot, None, None, "REJECTED", "Max Open Positions")
                if hasattr(self.ctx.system, "_update_dashboard"):
                    self.ctx.system._update_dashboard(snapshot, signal)
                return None, {}, latencies["decision_ms"]"""

code = code.replace(old_sim_guard, new_sim_guard, 1)

# Master gate
old_master_gate = """            self._log_canonical_truth(signal, cycle_count, False, master_result.reason, latencies)
            return None, {}, latencies["decision_ms"]"""

new_master_gate = """            self._record_v2_snapshot(signal, snapshot, None, None, "REJECTED", master_result.reason)
            self._log_canonical_truth(signal, cycle_count, False, master_result.reason, latencies)
            return None, {}, latencies["decision_ms"]"""

code = code.replace(old_master_gate, new_master_gate, 1)

with open("core/pipelines/decision_pipeline.py", "w", encoding="utf-8") as f:
    f.write(code)

print("decision_pipeline.py updated successfully.")
