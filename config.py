"""
Central configuration — loads .env and exposes typed settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
CONTENT_DB_PATH = ROOT_DIR / os.getenv("CONTENT_DB_PATH", "templates/content_calendar.csv")
OUTPUT_DIR = ROOT_DIR / os.getenv("OUTPUT_DIR", "output")
LOGS_DIR = ROOT_DIR / os.getenv("LOGS_DIR", "logs")
ASSETS_DIR = ROOT_DIR / os.getenv("ASSETS_DIR", "assets")
PROMPTS_DIR = ROOT_DIR / "prompts"

# Ensure dirs exist
for d in [OUTPUT_DIR, LOGS_DIR, ASSETS_DIR,
          OUTPUT_DIR / "scripts", OUTPUT_DIR / "voiceovers",
          OUTPUT_DIR / "videos", OUTPUT_DIR / "metadata"]:
    d.mkdir(parents=True, exist_ok=True)

# ── LLM ──────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# ── TTS ──────────────────────────────────────────────────────────
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")  # "openai" | "elevenlabs"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "onyx")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# ── TikTok ───────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_AUTO_POST = os.getenv("TIKTOK_AUTO_POST", "false").lower() == "true"

# ── Video ────────────────────────────────────────────────────────
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_BG_COLOR = os.getenv("VIDEO_BG_COLOR", "#0a0a0a")
FONT_PATH = str(ROOT_DIR / os.getenv("FONT_PATH", "assets/fonts/Montserrat-Bold.ttf"))
FONT_SIZE = int(os.getenv("FONT_SIZE", "64"))
SUBTITLE_FONT_SIZE = int(os.getenv("SUBTITLE_FONT_SIZE", "48"))

# ── Safety ───────────────────────────────────────────────────────
HIGH_RISK_KEYWORDS = [
    kw.strip().lower()
    for kw in os.getenv(
        "HIGH_RISK_KEYWORDS",
        "cure,guaranteed,reverses,eliminates,permanent,miracle,clinical trial"
    ).split(",")
]
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
