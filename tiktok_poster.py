"""
TikTok Content Posting API integration.

Uses the official TikTok Content Posting API (v2).
Reference: https://developers.tiktok.com/doc/content-posting-api-get-started

Flow:
1. Upload video to TikTok (init → upload chunks → publish)
2. Track publish status
3. Log result

If TIKTOK_AUTO_POST is false, videos are queued as "ready" and
can be posted manually or via a separate trigger.
"""

import json
import time
import requests
from pathlib import Path
from config import (
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN,
    TIKTOK_AUTO_POST, MAX_RETRIES, RETRY_DELAY_SECONDS, OUTPUT_DIR
)
from modules.logger import get_logger, log_event

log = get_logger("tiktok_poster")

BASE_URL = "https://open.tiktokapis.com/v2"


def is_configured() -> bool:
    """Check if TikTok API credentials are set."""
    return bool(TIKTOK_ACCESS_TOKEN and TIKTOK_CLIENT_KEY)


def post_video(
    topic_id: str,
    video_path: Path,
    caption: str,
    hashtags: str = "",
    cover_text: str = "",
) -> dict:
    """
    Post a video to TikTok using the Content Posting API.

    Returns:
        {
            "success": bool,
            "post_id": str | None,
            "publish_id": str | None,
            "status": str,
            "error": str | None,
        }
    """
    if not is_configured():
        log.warning("TikTok API not configured — video queued as 'ready'")
        return {
            "success": False,
            "post_id": None,
            "publish_id": None,
            "status": "queued_no_credentials",
            "error": "TikTok API credentials not configured",
        }

    if not TIKTOK_AUTO_POST:
        log.info(f"Auto-post disabled — {topic_id} queued as 'ready'")
        return {
            "success": False,
            "post_id": None,
            "publish_id": None,
            "status": "queued_auto_post_off",
            "error": None,
        }

    full_caption = f"{caption} {hashtags}".strip()[:2200]  # TikTok caption limit

    try:
        # Step 1: Initialize video upload
        init_result = _init_upload(video_path, full_caption)
        if not init_result.get("publish_id"):
            return {
                "success": False,
                "post_id": None,
                "publish_id": None,
                "status": "init_failed",
                "error": init_result.get("error", "Upload init failed"),
            }

        publish_id = init_result["publish_id"]
        upload_url = init_result.get("upload_url")

        # Step 2: Upload the video file
        if upload_url:
            _upload_video_file(upload_url, video_path)

        # Step 3: Check publish status
        status = _check_publish_status(publish_id)

        log_event("tiktok_posted", topic_id, {
            "publish_id": publish_id,
            "status": status.get("status"),
        })

        return {
            "success": status.get("status") == "PUBLISH_COMPLETE",
            "post_id": status.get("post_id"),
            "publish_id": publish_id,
            "status": status.get("status", "unknown"),
            "error": status.get("error"),
        }

    except Exception as e:
        log.error(f"TikTok posting failed for {topic_id}: {e}")
        return {
            "success": False,
            "post_id": None,
            "publish_id": None,
            "status": "exception",
            "error": str(e),
        }


def _init_upload(video_path: Path, caption: str) -> dict:
    """Initialize a direct post upload with TikTok."""
    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    video_size = video_path.stat().st_size

    payload = {
        "post_info": {
            "title": caption[:150],
            "privacy_level": "SELF_ONLY",  # start as private, user can change
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,  # single chunk for MVP
            "total_chunk_count": 1,
        },
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                f"{BASE_URL}/post/publish/video/init/",
                headers=headers,
                json=payload,
                timeout=30,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("data"):
                return {
                    "publish_id": data["data"].get("publish_id"),
                    "upload_url": data["data"].get("upload_url"),
                }
            else:
                error_msg = data.get("error", {}).get("message", resp.text)
                log.warning(f"Upload init attempt {attempt+1} failed: {error_msg}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS)

        except Exception as e:
            log.warning(f"Upload init attempt {attempt+1} error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    return {"error": "All upload init attempts failed"}


def _upload_video_file(upload_url: str, video_path: Path):
    """Upload the video binary to TikTok's upload URL."""
    headers = {
        "Content-Type": "video/mp4",
        "Content-Range": f"bytes 0-{video_path.stat().st_size - 1}/{video_path.stat().st_size}",
    }

    with open(video_path, "rb") as f:
        resp = requests.put(upload_url, headers=headers, data=f, timeout=120)

    if resp.status_code not in [200, 201]:
        raise RuntimeError(f"Video upload failed: {resp.status_code} {resp.text}")

    log.info("Video file uploaded to TikTok")


def _check_publish_status(publish_id: str, max_checks: int = 10) -> dict:
    """Poll TikTok for publish status."""
    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    for i in range(max_checks):
        time.sleep(5)  # TikTok recommends polling every 5s
        try:
            resp = requests.post(
                f"{BASE_URL}/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
                timeout=15,
            )
            data = resp.json()

            if data.get("data"):
                status = data["data"].get("status")
                if status in ["PUBLISH_COMPLETE", "FAILED"]:
                    return {
                        "status": status,
                        "post_id": data["data"].get("publicaly_available_post_id"),
                        "error": data["data"].get("fail_reason"),
                    }
        except Exception as e:
            log.warning(f"Status check {i+1} failed: {e}")

    return {"status": "TIMEOUT", "error": "Publish status check timed out"}


def get_ready_queue() -> list[dict]:
    """
    List all videos in the 'ready' state that haven't been posted.
    Reads from the metadata output directory.
    """
    queue = []
    meta_dir = OUTPUT_DIR / "metadata"
    for f in sorted(meta_dir.glob("*.json")):
        with open(f) as fh:
            meta = json.load(fh)
        if meta.get("posted_status") in [None, "", "ready", "queued_no_credentials", "queued_auto_post_off"]:
            queue.append(meta)
    return queue
