import time
import asyncio
import aiohttp
from typing import Tuple, Optional
import pandas as pd

from core.data_manager import DataManager
from models.market import MarketSnapshot
from utils.logger import get_logger

logger = get_logger("market_pipeline")

class MarketDataPipeline:
    def __init__(self, ctx):
        self.ctx = ctx
        self.settings = ctx.settings
        
        # Instantiate the DataManager which handles API calls, caching, and technicals
        self.data_manager = DataManager(self.settings)
        self.ctx.data_manager = self.data_manager

    def bootstrap(self):
        """Runs the synchronous startup bootstrap to build history."""
        try:
            self.data_manager.startup_bootstrap()
        except Exception as e:
            logger.critical(f"Data Core bootstrap failed: {e}")
            raise e

    async def start_background_tasks(self, session: aiohttp.ClientSession):
        """Starts background workers like the 2-minute OI updater."""
        return asyncio.create_task(self.data_manager.start_oi_updater(session))

    async def fetch_latest(self, session: aiohttp.ClientSession) -> Tuple[Optional[pd.DataFrame], Optional[MarketSnapshot], float]:
        """
        Fetches the latest OHLCV data, calculates indicators, retrieves OI, 
        and builds a MarketSnapshot.
        """
        t0 = time.perf_counter()
        df, snapshot = await self.data_manager.update_latest_candle_async(session)
        fetch_ms = (time.perf_counter() - t0) * 1000
        return df, snapshot, fetch_ms
