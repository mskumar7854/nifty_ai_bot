"""
============================================
🏅 SIGNAL QUALITY GRADER v2
Why: Not all 70% confidence signals are equal.
     A+ setups have HTF alignment + low risk.
============================================
"""

from models.signals import Signal, SignalGrade, Direction, MarketRegime
from config.settings import Settings


class SignalQualityGrader:
    """
    Grades a signal from A+ down to D based on multiple criteria:
    - Confluence ratio
    - Risk Reward ratio
    - Agent warnings
    - Regime alignment
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def grade(self, signal: Signal) -> SignalGrade:
        score = 0
        
        # 1. Confluence Base Score (max 40)
        conf_ratio = signal.confluence.confluence_ratio if signal.confluence else 0
        if conf_ratio >= 0.9: score += 40
        elif conf_ratio >= 0.8: score += 30
        elif conf_ratio >= 0.7: score += 20
        elif conf_ratio >= 0.6: score += 10

        # 2. Risk/Reward Score (max 30)
        rr = signal.risk_reward_ratio
        if rr >= 3.0: score += 30
        elif rr >= 2.0: score += 20
        elif rr >= 1.5: score += 10

        # 3. Confidence Base Score (max 20)
        if signal.confidence >= 85: score += 20
        elif signal.confidence >= 75: score += 15
        elif signal.confidence >= 65: score += 10
        
        # 4. Regime Alignment (max 10)
        if signal.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.BREAKOUT]:
            score += 10
            
        # Penalties
        # Excessive warnings
        if len(signal.warnings) > 2:
            score -= (len(signal.warnings) * 5)

        # Clean alignment check
        clean_mtf = "multi_timeframe" in (signal.confluence.agreeing_agents if signal.confluence else [])

        # Assign Grade
        if score >= 90 and clean_mtf and rr >= 2.0:
            return SignalGrade.A_PLUS
        elif score >= 80:
            return SignalGrade.A
        elif score >= 65:
            return SignalGrade.B
        elif score >= 50:
            return SignalGrade.C
        else:
            return SignalGrade.D
