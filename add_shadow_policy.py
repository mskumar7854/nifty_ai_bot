import re

with open("core/pipelines/decision_pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()

# Update _record_v2_snapshot to support Lineage and Shadow Candidate Policy
new_method = """    def _record_v2_snapshot(self, signal, snapshot, outputs=None, filter_result=None, final_decision="REJECTED", rejection_reason="", timeline=None):
        if signal.signal_type == SignalType.NO_TRADE:
            return
            
        try:
            from models.snapshot_v2 import DecisionSnapshotV2, SnapshotMetadata, AgentOpinion, GateResult, ReplayStatus
            from core.snapshot_v2 import persist_snapshot_v2
            import datetime
            import uuid
            
            mode_str = self.settings.system_mode.mode if hasattr(self.settings.system_mode, "mode") else str(self.settings.system_mode)
            
            # --- Lineage ---
            trade_id = None
            shadow_trade_id = None
            
            if final_decision == "EXECUTE":
                trade_id = signal.id
            
            # --- Shadow Candidate Policy ---
            if final_decision == "REJECTED":
                # Check eligibility
                conf_valid = getattr(signal, "confidence", 0.0) >= 0.60
                ev_valid = getattr(signal, "ev_info", {}).get("ev_r", 0.0) > 0
                
                # Check gates failed
                gates_failed = 0
                if filter_result and hasattr(filter_result, "gate_details"):
                    gates_failed = sum(1 for g in filter_result.gate_details if not g.get("pass", False))
                elif filter_result is None and "Master Gate" in rejection_reason:
                    gates_failed = 1
                    
                if conf_valid and ev_valid and gates_failed == 1:
                    shadow_trade_id = f"shadow-{signal.id}"
            
            metadata = SnapshotMetadata(
                snapshot_id=signal.id,
                timestamp=datetime.datetime.now().isoformat(),
                symbol="NIFTY",
                expiry="UNKNOWN",
                mode=mode_str,
                parent_snapshot_id=None,
                trade_id=trade_id,
                shadow_trade_id=shadow_trade_id,
                experiment_id=None,
                replay_run_id=None
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
                event_timeline=timeline or {},
                replay=replay_status,
                outcome=None
            )
            persist_snapshot_v2(snap_v2)
        except Exception as e:
            logger.error(f"Failed to record V2 snapshot: {e}")"""

# find the start and end of _record_v2_snapshot
start_idx = code.find("    def _record_v2_snapshot")
end_idx = code.find("    def evaluate", start_idx)

code = code[:start_idx] + new_method + "\n\n" + code[end_idx:]

with open("core/pipelines/decision_pipeline.py", "w", encoding="utf-8") as f:
    f.write(code)
    
print("Updated decision_pipeline.py")
