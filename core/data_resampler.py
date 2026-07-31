import pandas as pd
import datetime
from typing import List, Dict

class DataResampler:
    """
    Deterministically constructs 1-minute OHLC candles from tick data.
    Ensures that regardless of replay speed, 09:15:00 to 09:15:59.999 
    always produces the exact same candle.
    """
    
    @staticmethod
    def ticks_to_1m_ohlc(ticks: List[Dict]) -> pd.DataFrame:
        """
        Converts a list of dicts [{"ts": datetime, "price": float}, ...] 
        into a 1-minute OHLC pandas DataFrame.
        """
        if not ticks:
            return pd.DataFrame()
            
        df = pd.DataFrame(ticks)
        df.set_index('ts', inplace=True)
        
        # Resample to 1 minute
        # label='left' and closed='left' means 09:15:00 to 09:15:59.999 maps to 09:15:00
        ohlc = df['price'].resample('1min', label='left', closed='left').ohlc()
        
        # Drop minutes with no data
        ohlc.dropna(inplace=True)
        
        return ohlc
