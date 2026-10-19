"""
Structured logging for every pipeline step.
Writes to both console and a daily rotating log file.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from config import LOGS_DIR


def get_logger(name: str = "tiktok_engine") -> logging.Logger:
    """Return a configured logger that writes to console + file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File (daily)
    today = datetime.now().strftime("%Y-%m-%d")
    fh = logging.FileHandler(LOGS_DIR / f"engine_{today}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def log_event(event_type: str, topic_id: str, data: dict | None = None):
    """Append a structured JSON event to the event log (for analytics)."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "topic_id": topic_id,
        "data": data or {},
    }
    path = LOGS_DIR / "events.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\n")
