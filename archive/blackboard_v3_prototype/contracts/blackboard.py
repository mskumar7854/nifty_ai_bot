from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from bots.contracts.reports import (
    MarketReport, OptionsReport, SentimentReport,
    SignalReport, PortfolioReport, DecisionReport, OMSReport
)

class MarketSnapshot(BaseModel):
    """
    Immutable market data. Facts only. Never changes once created.
    """
    timestamp: datetime
    spot_price: float
    vwap: float = 0.0
    atr: float = 0.0
    vix: Optional[float] = None
    pcr: Optional[float] = None
    # Add other objective facts here over time

class DecisionContext(BaseModel):
    """
    The Trading Blackboard. 
    Where all bots post their opinions/reports based on the MarketSnapshot.
    """
    market: Optional[MarketReport] = None
    options: Optional[OptionsReport] = None
    sentiment: Optional[SentimentReport] = None
    
    signal: Optional[SignalReport] = None
    portfolio: Optional[PortfolioReport] = None
    decision: Optional[DecisionReport] = None
    oms: Optional[OMSReport] = None

class TradingBlackboard(BaseModel):
    """
    The complete state of a single evaluation tick.
    """
    snapshot: MarketSnapshot
    context: DecisionContext = Field(default_factory=DecisionContext)

    def with_report(self, report: BaseModel) -> 'TradingBlackboard':
        """
        Returns a new blackboard with the updated report.
        Maintains immutability of the context.
        """
        new_ctx = self.context.model_copy()
        
        if isinstance(report, MarketReport): new_ctx.market = report
        elif isinstance(report, OptionsReport): new_ctx.options = report
        elif isinstance(report, SentimentReport): new_ctx.sentiment = report
        elif isinstance(report, SignalReport): new_ctx.signal = report
        elif isinstance(report, PortfolioReport): new_ctx.portfolio = report
        elif isinstance(report, DecisionReport): new_ctx.decision = report
        elif isinstance(report, OMSReport): new_ctx.oms = report
        else:
            raise ValueError(f"Unknown report type: {type(report)}")
            
        return TradingBlackboard(snapshot=self.snapshot, context=new_ctx)
