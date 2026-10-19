"""
Script generation — uses Claude API to turn a topic into a full TikTok script.
Returns structured content: hook, script lines, on-screen text, CTA.
"""

import json
import time
from pathlib import Path
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, PROMPTS_DIR,
    MAX_RETRIES, RETRY_DELAY_SECONDS
)
from modules.logger import get_logger, log_event
from modules.content_guidelines import get_guidelines_block, AUDIENCE_DESCRIPTION

log = get_logger("script_gen")
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text()


def generate_script(topic: str, angle: str = "", audience: str = "") -> dict:
    """
    Generate a complete TikTok script for a given topic.

    Returns:
        {
            "hook": str,
            "script": str,           # full voiceover script
            "on_screen_text": list,   # list of text overlay lines
            "cta": str,
            "duration_estimate": int  # seconds
        }
    """
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY not set — cannot generate scripts")

    prompt_template = _load_prompt("script_writing.txt")
    user_prompt = prompt_template.format(
        topic=topic,
        angle=angle or "educational, myth-busting",
        audience=audience or AUDIENCE_DESCRIPTION,
        guidelines=get_guidelines_block(),
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text

            # Parse the structured JSON from Claude's response
            result = _parse_script_response(raw)
            log.info(f"Script generated for topic: {topic[:50]}...")
            return result

        except Exception as e:
            log.warning(f"Script generation attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                log.error(f"Script generation failed after {MAX_RETRIES} attempts")
                raise


def _parse_script_response(raw: str) -> dict:
    """Parse Claude's response into structured script data."""
    # Try to extract JSON block
    if "```json" in raw:
        json_str = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        json_str = raw.split("```")[1].split("```")[0].strip()
    else:
        json_str = raw.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: treat entire response as the script
        log.warning("Could not parse JSON from script response, using raw text")
        data = {
            "hook": "",
            "script": raw.strip(),
            "on_screen_text": [],
            "cta": "Follow for more tips",
            "duration_estimate": 30,
        }

    # Ensure required fields
    data.setdefault("hook", "")
    data.setdefault("script", "")
    data.setdefault("on_screen_text", [])
    data.setdefault("cta", "Follow for more tips")
    data.setdefault("duration_estimate", 30)

    return data


def generate_captions(topic: str, script: str, hook: str) -> dict:
    """
    Generate TikTok caption, hashtags, and cover text.

    Returns:
        {"caption": str, "hashtags": str, "cover_text": str}
    """
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    prompt_template = _load_prompt("caption_generation.txt")
    user_prompt = prompt_template.format(
        topic=topic,
        script=script,
        hook=hook,
        guidelines=get_guidelines_block(),
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text
            return _parse_caption_response(raw)
        except Exception as e:
            log.warning(f"Caption generation attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                raise


def _parse_caption_response(raw: str) -> dict:
    """Parse caption generation response."""
    if "```json" in raw:
        json_str = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        json_str = raw.split("```")[1].split("```")[0].strip()
    else:
        json_str = raw.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        data = {
            "caption": raw.strip()[:300],
            "hashtags": "#hairrestoration #antiaging #hairloss #skincare",
            "cover_text": "",
        }

    data.setdefault("caption", "")
    data.setdefault("hashtags", "")
    data.setdefault("cover_text", "")
    return data
