"""
Pipeline orchestrator — runs each topic through every stage.

Stages:
  new → scripted → compliance_ok → voiced → rendered → captioned → ready → posted

Each stage is idempotent: if it fails, the topic stays at its current
status and can be retried. The pipeline picks up wherever it left off.
"""

import json
import traceback
from pathlib import Path
from config import OUTPUT_DIR
from modules.content_db import (
    init_db, get_next_batch, update_topic, save_db
)
from modules.script_generator import generate_script, generate_captions
from modules.compliance import check_compliance, rewrite_for_compliance
from modules.voiceover import generate_voiceover, get_audio_duration
from modules.video_renderer import render_video
from modules.tiktok_poster import post_video, is_configured as tiktok_configured
from modules.logger import get_logger, log_event

log = get_logger("pipeline")


def run_pipeline(batch_size: int = 5, stop_before_post: bool = False):
    """
    Run the full pipeline on all eligible topics.

    Args:
        batch_size: How many topics to process per stage per run
        stop_before_post: If True, stop at 'ready' (don't auto-post)
    """
    df = init_db()
    stages = [
        ("new", stage_generate_script),
        ("scripted", stage_compliance_check),
        ("compliance_ok", stage_generate_voiceover),
        ("voiced", stage_render_video),
        ("rendered", stage_generate_captions),
    ]

    if not stop_before_post:
        stages.append(("captioned", stage_post_to_tiktok))

    for status, stage_fn in stages:
        batch = get_next_batch(df, status, limit=batch_size)
        if batch.empty:
            continue

        log.info(f"Processing {len(batch)} topics at stage: {status}")

        for _, row in batch.iterrows():
            topic_id = row["topic_id"]
            try:
                df = stage_fn(df, row)
                log_event("stage_complete", topic_id, {"stage": status})
            except Exception as e:
                log.error(f"Stage '{status}' failed for {topic_id}: {e}")
                log.debug(traceback.format_exc())
                df = update_topic(df, topic_id, {
                    "error": str(e),
                    "status": f"failed_{status}",
                })
                log_event("stage_failed", topic_id, {
                    "stage": status, "error": str(e)
                })

    log.info("Pipeline run complete")
    _print_status_summary(df)
    return df


def run_single(topic_id: str, stop_before_post: bool = False):
    """Run the full pipeline for a single topic (useful for testing)."""
    df = init_db()
    mask = df["topic_id"] == topic_id
    if not mask.any():
        log.error(f"Topic {topic_id} not found")
        return

    row = df[mask].iloc[0]
    status = row["status"]

    stage_order = [
        "new", "scripted", "compliance_ok", "voiced", "rendered", "captioned"
    ]

    # Find where to start
    if status in stage_order:
        start_idx = stage_order.index(status)
    else:
        log.error(f"Topic {topic_id} has unexpected status: {status}")
        return

    stage_map = {
        "new": stage_generate_script,
        "scripted": stage_compliance_check,
        "compliance_ok": stage_generate_voiceover,
        "voiced": stage_render_video,
        "rendered": stage_generate_captions,
        "captioned": stage_post_to_tiktok,
    }

    for stage_name in stage_order[start_idx:]:
        if stop_before_post and stage_name == "captioned":
            log.info(f"Stopping before post for {topic_id}")
            break

        stage_fn = stage_map[stage_name]
        row = df[df["topic_id"] == topic_id].iloc[0]

        try:
            log.info(f"Running stage '{stage_name}' for {topic_id}")
            df = stage_fn(df, row)
            log_event("stage_complete", topic_id, {"stage": stage_name})
        except Exception as e:
            log.error(f"Stage '{stage_name}' failed for {topic_id}: {e}")
            df = update_topic(df, topic_id, {
                "error": str(e),
                "status": f"failed_{stage_name}",
            })
            break

    _print_status_summary(df)
    return df


# ── Stage functions ─────────────────────────────────────────────────


def stage_generate_script(df, row):
    """Generate script from topic."""
    topic_id = row["topic_id"]
    topic = row["topic"]
    angle = row.get("angle", "")
    audience = row.get("target_audience", "")

    log.info(f"Generating script for: {topic[:60]}")
    result = generate_script(topic, angle, audience)

    # Save script to file
    script_path = OUTPUT_DIR / "scripts" / f"{topic_id}.json"
    with open(script_path, "w") as f:
        json.dump(result, f, indent=2)

    return update_topic(df, topic_id, {
        "status": "scripted",
        "script": result["script"],
        "hook": result["hook"],
        "on_screen_text": json.dumps(result["on_screen_text"]),
        "cta": result["cta"],
        "error": "",
    })


def stage_compliance_check(df, row):
    """Run compliance check and rewrite if needed."""
    topic_id = row["topic_id"]
    script = row["script"]
    topic = row["topic"]

    log.info(f"Compliance check for: {topic_id}")

    # First check raw compliance
    check = check_compliance(script, topic)

    if check["is_compliant"] and not check["needs_review"]:
        return update_topic(df, topic_id, {
            "status": "compliance_ok",
            "compliance_status": "passed",
            "compliance_notes": "No issues found",
            "needs_review": "false",
            "error": "",
        })

    # Needs rewrite
    log.info(f"Script needs compliance rewrite ({check['risk_level']} risk)")
    result = rewrite_for_compliance(script, topic)

    needs_review = "true" if check["needs_review"] else "false"
    new_status = "compliance_ok" if not check["needs_review"] else "scripted"

    if check["needs_review"]:
        log.warning(f"Topic {topic_id} flagged for MANUAL REVIEW")
        new_status = "needs_review"

    return update_topic(df, topic_id, {
        "status": new_status,
        "script": result["rewritten_script"],
        "compliance_status": f"rewritten ({check['risk_level']})",
        "compliance_notes": "; ".join(result["changes_made"]),
        "needs_review": needs_review,
        "error": "",
    })


def stage_generate_voiceover(df, row):
    """Generate voiceover audio from script."""
    topic_id = row["topic_id"]
    script = row["script"]

    log.info(f"Generating voiceover for: {topic_id}")
    vo_path = generate_voiceover(script, topic_id)

    return update_topic(df, topic_id, {
        "status": "voiced",
        "voiceover_file": str(vo_path),
        "error": "",
    })


def stage_render_video(df, row):
    """Render the video from script + voiceover."""
    topic_id = row["topic_id"]
    script = row["script"]
    hook = row.get("hook", "")
    cta = row.get("cta", "Follow for more")

    on_screen_text = row.get("on_screen_text", "[]")
    if isinstance(on_screen_text, str):
        try:
            on_screen_text = json.loads(on_screen_text)
        except json.JSONDecodeError:
            on_screen_text = []

    vo_path = Path(row["voiceover_file"])
    if not vo_path.exists():
        raise FileNotFoundError(f"Voiceover file not found: {vo_path}")

    log.info(f"Rendering video for: {topic_id}")
    video_path = render_video(
        topic_id=topic_id,
        script=script,
        hook=hook,
        on_screen_text=on_screen_text,
        voiceover_path=vo_path,
        cta=cta,
    )

    return update_topic(df, topic_id, {
        "status": "rendered",
        "video_file": str(video_path),
        "error": "",
    })


def stage_generate_captions(df, row):
    """Generate caption, hashtags, and cover text."""
    topic_id = row["topic_id"]
    topic = row["topic"]
    script = row["script"]
    hook = row.get("hook", "")

    log.info(f"Generating captions for: {topic_id}")
    result = generate_captions(topic, script, hook)

    # Save full metadata
    meta = {
        "topic_id": topic_id,
        "topic": topic,
        "script": script,
        "hook": hook,
        "caption": result["caption"],
        "hashtags": result["hashtags"],
        "cover_text": result["cover_text"],
        "video_file": row.get("video_file", ""),
        "voiceover_file": row.get("voiceover_file", ""),
        "posted_status": "ready",
    }
    meta_path = OUTPUT_DIR / "metadata" / f"{topic_id}.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return update_topic(df, topic_id, {
        "status": "captioned",
        "caption": result["caption"],
        "hashtags": result["hashtags"],
        "cover_text": result["cover_text"],
        "error": "",
    })


def stage_post_to_tiktok(df, row):
    """Post to TikTok or queue for manual posting."""
    topic_id = row["topic_id"]
    video_path = Path(row.get("video_file", ""))
    caption = row.get("caption", "")
    hashtags = row.get("hashtags", "")

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    log.info(f"Posting to TikTok: {topic_id}")
    result = post_video(topic_id, video_path, caption, hashtags)

    posted_status = "posted" if result["success"] else result["status"]

    return update_topic(df, topic_id, {
        "status": "ready" if not result["success"] else "posted",
        "posted_status": posted_status,
        "post_url": result.get("post_id") or "",
        "tiktok_post_id": result.get("publish_id") or "",
        "error": result.get("error") or "",
    })


# ── Helpers ─────────────────────────────────────────────────────────


def _print_status_summary(df):
    """Print a summary of topic statuses."""
    if df.empty:
        log.info("No topics in database")
        return

    counts = df["status"].value_counts().to_dict()
    log.info("=== Status Summary ===")
    for status, count in sorted(counts.items()):
        log.info(f"  {status}: {count}")
    log.info(f"  TOTAL: {len(df)}")
