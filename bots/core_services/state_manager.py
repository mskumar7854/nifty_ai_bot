from typing import Dict, Any, Optional

class StateManager:
    """
    Centralized StateManager. 
    Encapsulates all persistent state (Trend, Risk, Position, Learning).
    This ensures bots remain stateless and replay remains deterministic.
    """
    def __init__(self):
        # In memory for now. Can be replaced with Redis/DB later.
        self._positions: Dict[str, Any] = {}
        self._trend_state: Dict[str, Any] = {"structure": "UNKNOWN", "last_reset_time": None}
        self._risk_budget: Dict[str, Any] = {"daily_limit": 1000, "used": 0}
        self._learning_state: Dict[str, Any] = {}
        
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._positions.get(symbol)
        
    def update_position(self, symbol: str, data: Dict[str, Any]):
        self._positions[symbol] = data
        
    def get_trend_state(self) -> Dict[str, Any]:
        return self._trend_state.copy()
        
    def update_trend_state(self, state: Dict[str, Any]):
        self._trend_state.update(state)
        
    def get_risk_budget(self) -> Dict[str, Any]:
        return self._risk_budget.copy()
        
    def consume_risk(self, amount: float) -> bool:
        if self._risk_budget["used"] + amount <= self._risk_budget["daily_limit"]:
            self._risk_budget["used"] += amount
            return True
        return False
