"""
============================================
OPPORTUNITY RANKING ENGINE (v2.1)

Replaces first-come-first-served execution with a composite opportunity ranker:
    S_opp = 0.40 * S_EV + 0.30 * Pwin_calibrated + 0.20 * S_Grade + 0.10 * S_Liquidity

Ranks candidate setups so that the BEST opportunities win, rather than just the earliest.
============================================
"""

from typing import List, Dict, Any


class OpportunityRanker:
    def __init__(self):
        self.grade_scores = {
            "A+": 100.0,
            "A": 85.0,
            "B+": 70.0,
            "B": 55.0,
            "C": 35.0,
            "D": 10.0
        }

    def compute_composite_score(self, candidate: Dict[str, Any]) -> float:
        """
        Compute composite opportunity score (0.0 to 100.0).
        
        Candidate dict keys:
          - ev_score: float (0 to 100)
          - calibrated_pwin: float (0.0 to 1.0)
          - grade: str ("A+", "A", "B+", etc.)
          - liquidity_score: float (0 to 100, optional, default 75)
        """
        s_ev = float(candidate.get("ev_score", 50.0))
        pwin = float(candidate.get("calibrated_pwin", 0.50))
        s_pwin = pwin * 100.0
        
        grade_str = str(candidate.get("grade", "B")).upper()
        if "." in grade_str:
            grade_str = grade_str.split(".")[1]
        s_grade = self.grade_scores.get(grade_str, 50.0)
        
        s_liq = float(candidate.get("liquidity_score", 75.0))

        # Composite formula: 40% EV + 30% Calibrated Pwin + 20% Grade + 10% Liquidity
        s_opp = (0.40 * s_ev) + (0.30 * s_pwin) + (0.20 * s_grade) + (0.10 * s_liq)
        return round(s_opp, 2)

    def rank_candidates(self, candidates: List[Dict[str, Any]], max_select: int = 1) -> List[Dict[str, Any]]:
        """
        Rank candidate setups descending by composite opportunity score
        and return top N setups.
        """
        if not candidates:
            return []

        ranked = []
        for cand in candidates:
            c = dict(cand)
            c["composite_opp_score"] = self.compute_composite_score(c)
            ranked.append(c)

        # Sort descending by composite score
        ranked.sort(key=lambda x: x["composite_opp_score"], reverse=True)

        return ranked[:max_select]
