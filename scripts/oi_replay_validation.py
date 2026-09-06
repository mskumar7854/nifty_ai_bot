import os
import pandas as pd
import numpy as np

import glob

BASE_DIR = "data/oi_validation"

def compute_metrics():
    csv_files = glob.glob(f"{BASE_DIR}/**/oi_analytics.csv", recursive=True)
    if not csv_files:
        print(f"Error: No CSV files found in {BASE_DIR}. Please run a simulation first to generate data.")
        return

    print(f"Loading {len(csv_files)} week(s) of data...")
    dfs = []
    for f in csv_files:
        try:
            dfs.append(pd.read_csv(f, parse_dates=['Timestamp']))
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not dfs:
        print("Dataset is empty.")
        return
        
    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values('Timestamp').reset_index(drop=True)
    
    if len(df) == 0:
        print("Dataset is empty.")
        return

    # 1. Backfill future deltas if they are empty
    print("Computing future returns (15m, 30m, 60m) based on Timestamp...")
    df = df.set_index('Timestamp')
    
    results = []
    for symbol, group in df.groupby('Symbol'):
        group = group.sort_index()
        
        future_15m = group.index + pd.Timedelta(minutes=15)
        future_30m = group.index + pd.Timedelta(minutes=30)
        future_60m = group.index + pd.Timedelta(minutes=60)
        
        idx_15 = group.index.searchsorted(future_15m)
        idx_30 = group.index.searchsorted(future_30m)
        idx_60 = group.index.searchsorted(future_60m)
        
        idx_15 = np.clip(idx_15, 0, len(group)-1)
        idx_30 = np.clip(idx_30, 0, len(group)-1)
        idx_60 = np.clip(idx_60, 0, len(group)-1)
        
        group['Future_Price_15m'] = group['Spot_Price'].iloc[idx_15].values
        group['Future_Price_30m'] = group['Spot_Price'].iloc[idx_30].values
        group['Future_Price_60m'] = group['Spot_Price'].iloc[idx_60].values
        
        group['Delta_15m'] = group['Future_Price_15m'] - group['Spot_Price']
        group['Delta_30m'] = group['Future_Price_30m'] - group['Spot_Price']
        group['Delta_60m'] = group['Future_Price_60m'] - group['Spot_Price']
        
        results.append(group)

    df = pd.concat(results)
    
    print("-" * 50)
    print("OI Replay Validation Report")
    print("-" * 50)
    
    TARGET_MOVE = 20
    
    df['OI_Direction'] = np.where(df['Pressure_Score'] >= 20, 1, np.where(df['Pressure_Score'] <= -20, -1, 0))
    df['Actual_Direction'] = np.where(df['Delta_30m'] >= TARGET_MOVE, 1, np.where(df['Delta_30m'] <= -TARGET_MOVE, -1, 0))
    
    active_signals = df[df['OI_Direction'] != 0].copy()
    total_active = len(active_signals)
    
    if total_active == 0:
        print("No active directional signals (Pressure > 20) found in dataset.")
        return
        
    correct_signals = active_signals[active_signals['OI_Direction'] == active_signals['Actual_Direction']]
    
    precision = len(correct_signals) / total_active if total_active > 0 else 0
    
    actual_moves = df[df['Actual_Direction'] != 0]
    total_moves = len(actual_moves)
    caught_moves = actual_moves[actual_moves['OI_Direction'] == actual_moves['Actual_Direction']]
    recall = len(caught_moves) / total_moves if total_moves > 0 else 0
    
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"Total Signals Generated: {total_active}")
    print(f"Precision (Accuracy of OI calls): {precision*100:.1f}%")
    print(f"Recall (Market moves caught): {recall*100:.1f}%")
    print(f"F1 Score: {f1:.2f}")
    
    print("-" * 50)
    print("Calibration: Pressure vs Win Rate")
    
    active_signals.loc[:, 'Abs_Pressure'] = active_signals['Pressure_Score'].abs()
    bins = [20, 40, 60, 80, 100]
    labels = ["20-40", "40-60", "60-80", "80-100"]
    active_signals.loc[:, 'Pressure_Bucket'] = pd.cut(active_signals['Abs_Pressure'], bins=bins, labels=labels)
    
    calibration = active_signals.groupby('Pressure_Bucket', observed=False).apply(
        lambda x: pd.Series({
            'Signals': len(x),
            'Win Rate': (len(x[x['OI_Direction'] == x['Actual_Direction']]) / len(x) * 100) if len(x) > 0 else 0
        })
    )
    print(calibration.to_string())
    
    print("-" * 50)
    print("Calibration: Reliability vs Win Rate")
    rel_bins = [0, 50, 70, 90, 100]
    rel_labels = ["0-50", "50-70", "70-90", "90-100"]
    active_signals.loc[:, 'Reliability_Bucket'] = pd.cut(active_signals['Reliability'], bins=rel_bins, labels=rel_labels)
    
    rel_calibration = active_signals.groupby('Reliability_Bucket', observed=False).apply(
        lambda x: pd.Series({
            'Signals': len(x),
            'Win Rate': (len(x[x['OI_Direction'] == x['Actual_Direction']]) / len(x) * 100) if len(x) > 0 else 0
        })
    )
    print(rel_calibration.to_string())
    
    print("-" * 50)
    print("Performance by Regime")
    regime_perf = active_signals.groupby('Regime', observed=False).apply(
        lambda x: pd.Series({
            'Signals': len(x),
            'Win Rate': (len(x[x['OI_Direction'] == x['Actual_Direction']]) / len(x) * 100) if len(x) > 0 else 0
        })
    )
    print(regime_perf.to_string())
    
    print("-" * 50)
    print("Trade Filtering Impact (Simulated)")
    
    trades = df[df['Engine_Decision'].isin(['BUY_CE', 'BUY_PE'])].copy()
    if len(trades) > 0:
        trades.loc[:, 'Engine_Dir'] = np.where(trades['Engine_Decision'] == 'BUY_CE', 1, -1)
        
        trades.loc[:, 'PnL_30m'] = trades['Engine_Dir'] * trades['Delta_30m']
        existing_winners = trades[trades['PnL_30m'] > 0]
        existing_losers = trades[trades['PnL_30m'] <= 0]
        
        existing_win_rate = len(existing_winners) / len(trades)
        existing_pf = existing_winners['PnL_30m'].sum() / abs(existing_losers['PnL_30m'].sum()) if len(existing_losers) > 0 else float('inf')
        existing_ev = trades['PnL_30m'].mean()
        
        print(f"Existing Engine: {len(trades)} trades, {existing_win_rate*100:.1f}% WR, PF: {existing_pf:.2f}, EV: {existing_ev:.2f} pts")
        
        filtered_trades = trades[
            ~((trades['Engine_Dir'] == 1) & (trades['Pressure_Score'] <= -20)) &
            ~((trades['Engine_Dir'] == -1) & (trades['Pressure_Score'] >= 20))
        ].copy()
        
        if len(filtered_trades) > 0:
            filtered_winners = filtered_trades[filtered_trades['PnL_30m'] > 0]
            filtered_losers = filtered_trades[filtered_trades['PnL_30m'] <= 0]
            
            new_win_rate = len(filtered_winners) / len(filtered_trades)
            new_pf = filtered_winners['PnL_30m'].sum() / abs(filtered_losers['PnL_30m'].sum()) if len(filtered_losers) > 0 else float('inf')
            new_ev = filtered_trades['PnL_30m'].mean()
            
            print(f"With OI Filter : {len(filtered_trades)} trades, {new_win_rate*100:.1f}% WR, PF: {new_pf:.2f}, EV: {new_ev:.2f} pts")
            
            false_breakouts_avoided = len(existing_losers) - len(filtered_losers)
            winners_blocked = len(existing_winners) - len(filtered_winners)
            
            print(f"False Breakouts Avoided: {false_breakouts_avoided}")
            print(f"Good Trades Blocked: {winners_blocked}")
        else:
            print("OI Filter blocked all trades.")
    else:
        print("No actual Engine_Decision trades found in dataset to evaluate filtering.")

if __name__ == "__main__":
    compute_metrics()
