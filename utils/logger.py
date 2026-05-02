"""
============================================
STRUCTURED LOGGING SYSTEM
Color-coded, leveled logging for all modules
============================================
"""

import logging
import sys
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler

console = Console()

# Custom log format
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create a structured logger for any module"""

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Rich console handler (beautiful output)
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(logging.DEBUG)

    # File handler
    import os
    log_dir = "/app/logs" if os.path.exists("/app") else "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    log_file = os.path.join(log_dir, "nifty_ai.log")
    
    file_handler = logging.FileHandler(
        log_file,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)

    return logger


class AgentLogger:
    """Specialized logger for agents with emoji indicators"""

    EMOJIS = {
        "market": "📊",
        "momentum": "📈",
        "oi": "📦",
        "trap": "⚠️",
        "sentiment": "🌍",
        "risk": "🧮",
        "decision": "🧠",
        "alert": "🔔",
        "system": "⚙️",
    }

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.emoji = self.EMOJIS.get(agent_name, "🔹")
        self.logger = get_logger(f"agent.{agent_name}")

    def info(self, message: str):
        self.logger.info(f"{self.emoji} {message}")

    def signal(self, message: str):
        self.logger.info(f"{self.emoji} {message}")

    def warning(self, message: str):
        self.logger.warning(f"{self.emoji} {message}")

    def error(self, message: str):
        self.logger.error(f"{self.emoji} {message}")

    def debug(self, message: str):
        self.logger.debug(f"{self.emoji} {message}")
