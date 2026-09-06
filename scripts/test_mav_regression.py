import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Ensure core is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.market_acceptance_validator import MarketAcceptanceValidator, AcceptanceState
import logging

def run_regression_test():
    logging.basicConfig(level=logging.WARNING) # suppress info logs from other modules
    mav = MarketAcceptanceValidator()
    
    print("Trade Candidate #1 (10:25)\n")
    start_time = datetime(2026, 5, 14, 10, 25, 58)
    print(f"10:25:58  CANDIDATE_CREATED")
    mav.track_candidate("Candidate_1", "BEARISH", 22000.0, start_time)
    
    # 10:26:00 - Structural Break (Close below 22000)
    print("10:26:00  STRUCTURAL_BREAK")
    df_1 = pd.DataFrame({
        'open': [22010.0, 21995.0],
        'high': [22010.0, 21995.0],
        'low': [21990.0, 21990.0],
        'close': [21995.0, 21990.0]
    }, index=[start_time, start_time + timedelta(minutes=1)])
    state = mav.evaluate_1m_candle(df_1)
    
    if state == AcceptanceState.WAITING_ACCEPTANCE:
        print(f"10:27:00  WAITING_ACCEPTANCE")
    else:
        print(f"10:27:00  {state.name}")
    
    # 10:28:00 - Acceptance Candle Reclaimed Support (Close above 22000)
    df_2 = pd.DataFrame({
        'open': [22010.0, 21995.0, 22005.0],
        'high': [22010.0, 22005.0, 22005.0],
        'low': [21990.0, 21990.0, 21990.0],
        'close': [21995.0, 22005.0, 22005.0]  # 2nd candle closes above 22000
    }, index=[start_time, start_time + timedelta(minutes=1), start_time + timedelta(minutes=2)])
    state = mav.evaluate_1m_candle(df_2)
    
    print(f"10:28:00  {state.name}")
    if state == AcceptanceState.FALSE_BREAKOUT:
        print(f"Reason: Acceptance candle reclaimed support, closed at 22005.0")
        print("Result: NO TRADE")
        
    print("\n--------------------------------------------\n")
    
    # Trade 2
    mav.reset()
    print("Trade Candidate #2 (10:32)\n")
    start_time_2 = datetime(2026, 5, 14, 10, 32, 55)
    print(f"10:32:55  CANDIDATE_CREATED")
    mav.track_candidate("Candidate_2", "BULLISH", 22050.0, start_time_2)
    
    # 10:33:00 - Structural Break (Close above 22050)
    print("10:33:00  STRUCTURAL_BREAK")
    df_3 = pd.DataFrame({
        'open': [22040.0, 22055.0],
        'high': [22055.0, 22060.0],
        'low': [22040.0, 22055.0],
        'close': [22055.0, 22060.0]
    }, index=[start_time_2, start_time_2 + timedelta(minutes=1)])
    state = mav.evaluate_1m_candle(df_3)
    
    if state == AcceptanceState.WAITING_ACCEPTANCE:
        print(f"10:34:00  WAITING_ACCEPTANCE")
    else:
        print(f"10:34:00  {state.name}")
    
    # 10:35:00 - Acceptance candle failed (Close below 22050)
    df_4 = pd.DataFrame({
        'open': [22040.0, 22055.0, 22045.0],
        'high': [22055.0, 22060.0, 22060.0],
        'low': [22040.0, 22045.0, 22040.0],
        'close': [22055.0, 22045.0, 22045.0]  # 2nd candle closes below 22050
    }, index=[start_time_2, start_time_2 + timedelta(minutes=1), start_time_2 + timedelta(minutes=2)])
    state = mav.evaluate_1m_candle(df_4)
    
    print(f"10:35:00  {state.name}")
    if state == AcceptanceState.FALSE_BREAKOUT:
        print(f"Reason: Acceptance candle failed to hold structure, closed at 22045.0")
        print("Result: NO TRADE")

if __name__ == '__main__':
    run_regression_test()
