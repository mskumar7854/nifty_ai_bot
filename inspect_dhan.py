from dhanhq import dhanhq
import inspect

try:
    print(inspect.signature(dhanhq.intraday_minute_data))
except Exception as e:
    print(f"Error: {e}")
