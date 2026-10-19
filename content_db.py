"""
Content database — reads/writes the CSV content calendar.
Each row is one topic moving through the pipeline.

Statuses: new → scripted → compliance_ok → voiced → rendered → captioned → ready → posted → failed
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from config import CONTENT_DB_PATH, OUTPUT_DIR
from modules.logger import get_logger, log_event

log = get_logger("content_db")

COLUMNS = [
    "topic_id",
    "topic",
    "angle",
    "target_audience",
    "status",
    "scheduled_date",
    "script",
    "hook",
    "on_screen_text",
    "compliance_status",
    "compliance_notes",
    "voiceover_file",
    "video_file",
    "caption",
    "hashtags",
    "cta",
    "cover_text",
    "posted_status",
    "post_url",
    "tiktok_post_id",
    "error",
    "needs_review",
    "notes",
    "created_at",
    "updated_at",
]


def init_db() -> pd.DataFrame:
    """Load existing CSV or create empty one with correct columns."""
    if CONTENT_DB_PATH.exists():
        df = pd.read_csv(CONTENT_DB_PATH)
        # Add any missing columns
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df
    else:
        df = pd.DataFrame(columns=COLUMNS)
        save_db(df)
        log.info(f"Created new content database at {CONTENT_DB_PATH}")
        return df


def save_db(df: pd.DataFrame):
    """Persist dataframe back to CSV."""
    CONTENT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CONTENT_DB_PATH, index=False)


def get_topics_by_status(df: pd.DataFrame, status: str) -> pd.DataFrame:
    """Filter topics by pipeline status."""
    return df[df["status"] == status]


def update_topic(df: pd.DataFrame, topic_id: str, updates: dict) -> pd.DataFrame:
    """Update fields for a specific topic and save."""
    updates["updated_at"] = datetime.now().isoformat()
    mask = df["topic_id"] == topic_id
    if not mask.any():
        log.error(f"Topic {topic_id} not found")
        return df
    for key, val in updates.items():
        if key in df.columns:
            df.loc[mask, key] = val
    save_db(df)
    log_event("topic_updated", topic_id, updates)
    return df


def add_topics(df: pd.DataFrame, topics: list[dict]) -> pd.DataFrame:
    """Add new topics from a list of dicts. Auto-generates topic_id if missing."""
    now = datetime.now()
    for i, t in enumerate(topics):
        if "topic_id" not in t or not t["topic_id"]:
            t["topic_id"] = f"t_{now.strftime('%Y%m%d')}_{i:03d}"
        t.setdefault("status", "new")
        t.setdefault("created_at", now.isoformat())
        t.setdefault("updated_at", now.isoformat())
        t.setdefault("needs_review", "false")
    new_rows = pd.DataFrame(topics, columns=COLUMNS)
    # Fill missing columns with empty strings
    for col in COLUMNS:
        if col not in new_rows.columns:
            new_rows[col] = ""
    df = pd.concat([df, new_rows], ignore_index=True)
    save_db(df)
    log.info(f"Added {len(topics)} new topics")
    return df


def get_next_batch(df: pd.DataFrame, status: str, limit: int = 5) -> pd.DataFrame:
    """Get the next N topics ready for a given pipeline stage."""
    batch = df[df["status"] == status].head(limit)
    return batch
