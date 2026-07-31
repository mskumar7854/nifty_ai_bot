from typing import Optional, Dict, Any
from models.decision_trace import DecisionTrace

class TraceComparer:
    @staticmethod
    def compare(baseline: DecisionTrace, experiment: DecisionTrace) -> str:
        out = []
        out.append(f"Cycle: {baseline.cycle_id} ({baseline.timestamp})")
        out.append("")
        
        out.append("BASELINE")
        out.append("───────────────")
        for stage in baseline.stages:
            out.append(f"{stage.stage_name:<22} {stage.action.value}")
            
        out.append("")
        out.append("EXPERIMENT")
        out.append("───────────────")
        for stage in experiment.stages:
            out.append(f"{stage.stage_name:<22} {stage.action.value}")
            
        out.append("")
        
        # Find divergence
        divergence_type = "None"
        first_diff_stage = None
        b_action = None
        e_action = None
        impact = "No difference"
        
        for i in range(max(len(baseline.stages), len(experiment.stages))):
            if i >= len(baseline.stages):
                first_diff_stage = experiment.stages[i]
                b_action = "MISSING"
                e_action = first_diff_stage.action.value
                break
            if i >= len(experiment.stages):
                first_diff_stage = baseline.stages[i]
                b_action = first_diff_stage.action.value
                e_action = "MISSING"
                break
                
            b = baseline.stages[i]
            e = experiment.stages[i]
            if b.action != e.action or b.stage_name != e.stage_name or b.reason != e.reason:
                first_diff_stage = e
                b_action = b.action.value
                e_action = e.action.value
                break

        if first_diff_stage:
            out.append("FIRST DIVERGENCE")
            out.append("────────────────────────")
            out.append(f"Stage:")
            out.append(first_diff_stage.stage_name)
            out.append("")
            
            # Divergence Type logic
            if "MAV" in first_diff_stage.stage_name or "Acceptance" in first_diff_stage.stage_name:
                divergence_type = "Classifier Divergence"
            elif "Confidence" in first_diff_stage.stage_name or "Integrity" in first_diff_stage.stage_name:
                divergence_type = "Threshold Divergence"
            elif "Execution" in first_diff_stage.stage_name:
                divergence_type = "Execution Divergence"
            else:
                divergence_type = "Configuration Divergence"
                
            out.append("DIVERGENCE TYPE")
            out.append(f"{divergence_type}")
            out.append("")
            
            out.append("Reason:")
            out.append(first_diff_stage.reason or "No explicit reason provided.")
            out.append("")
            
            # Impact logic
            if b_action == "PASSED" and e_action != "PASSED":
                out.append("IMPACT")
                out.append("Execution prevented")
                # Can be extended to compute R-multiple avoided if PnL available
                out.append("Expected Loss Avoided / Opportunity Missed")
            elif b_action != "PASSED" and e_action == "PASSED":
                out.append("IMPACT")
                out.append("New execution triggered")
                out.append("Trade taken that was previously blocked")
                
        return "\n".join(out)
