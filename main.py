#!/usr/bin/env python3
"""
TikTok Content Engine — CLI entry point.

Usage:
    python main.py run                  # Run pipeline on all eligible topics
    python main.py run --no-post        # Run pipeline but stop before posting
    python main.py single <topic_id>    # Process one topic end-to-end
    python main.py add <csv_file>       # Import topics from CSV
    python main.py status               # Show status summary
    python main.py queue                # Show ready-to-post queue
    python main.py retry                # Retry all failed topics
    python main.py test                 # Generate one test topic and process it
"""

import sys
import json
import argparse
import pandas as pd
from pathlib import Path

from config import CONTENT_DB_PATH, OUTPUT_DIR
from modules.content_db import init_db, add_topics, save_db, update_topic
from modules.logger import get_logger
from pipeline import run_pipeline, run_single, _print_status_summary

log = get_logger("main")


def cmd_run(args):
    """Run the full pipeline."""
    log.info("Starting pipeline run...")
    run_pipeline(
        batch_size=args.batch_size,
        stop_before_post=args.no_post,
    )


def cmd_single(args):
    """Process a single topic."""
    log.info(f"Processing single topic: {args.topic_id}")
    run_single(args.topic_id, stop_before_post=args.no_post)


def cmd_add(args):
    """Import topics from a CSV file."""
    import_path = Path(args.csv_file)
    if not import_path.exists():
        log.error(f"File not found: {import_path}")
        sys.exit(1)

    imported = pd.read_csv(import_path)
    topics = imported.to_dict("records")

    df = init_db()
    df = add_topics(df, topics)
    log.info(f"Imported {len(topics)} topics from {import_path}")
    _print_status_summary(df)


def cmd_status(args):
    """Show current status of all topics."""
    df = init_db()
    if df.empty:
        print("\nNo topics in database. Add some with: python main.py add topics.csv\n")
        return

    _print_status_summary(df)

    # Show recent errors
    errors = df[df["error"].notna() & (df["error"] != "")]
    if not errors.empty:
        print("\n=== Recent Errors ===")
        for _, row in errors.iterrows():
            print(f"  {row['topic_id']}: {row['error'][:80]}")

    # Show items needing review
    review = df[df["needs_review"] == "true"]
    if not review.empty:
        print(f"\n=== Needs Manual Review ({len(review)}) ===")
        for _, row in review.iterrows():
            print(f"  {row['topic_id']}: {row['topic'][:60]}")


def cmd_queue(args):
    """Show ready-to-post videos."""
    df = init_db()
    ready = df[df["status"].isin(["captioned", "ready"])]

    if ready.empty:
        print("\nNo videos ready to post.")
        return

    print(f"\n=== Ready to Post ({len(ready)}) ===")
    for _, row in ready.iterrows():
        print(f"\n  ID: {row['topic_id']}")
        print(f"  Topic: {row['topic'][:60]}")
        print(f"  Video: {row.get('video_file', 'N/A')}")
        print(f"  Caption: {row.get('caption', 'N/A')[:80]}")
        print(f"  Hashtags: {row.get('hashtags', 'N/A')}")


def cmd_retry(args):
    """Reset all failed topics to their pre-failure status."""
    df = init_db()
    failed = df[df["status"].str.startswith("failed_", na=False)]

    if failed.empty:
        print("No failed topics to retry.")
        return

    for _, row in failed.iterrows():
        original_status = row["status"].replace("failed_", "")
        df = update_topic(df, row["topic_id"], {
            "status": original_status,
            "error": "",
        })
        log.info(f"Reset {row['topic_id']} from {row['status']} → {original_status}")

    print(f"Reset {len(failed)} failed topics for retry.")


def cmd_test(args):
    """Create a test topic and run it through the pipeline."""
    df = init_db()

    test_topics = [{
        "topic": "3 vitamins that may support hair thickness",
        "angle": "educational, myth-busting",
        "target_audience": "adults 25-55 concerned about thinning hair",
        "scheduled_date": "2026-03-25",
    }]

    df = add_topics(df, test_topics)
    topic_id = df.iloc[-1]["topic_id"]

    log.info(f"Created test topic: {topic_id}")
    log.info("Running pipeline for test topic...")

    run_single(topic_id, stop_before_post=True)


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Content Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = subparsers.add_parser("run", help="Run the full pipeline")
    p_run.add_argument("--no-post", action="store_true", help="Stop before posting")
    p_run.add_argument("--batch-size", type=int, default=5, help="Topics per stage")
    p_run.set_defaults(func=cmd_run)

    # single
    p_single = subparsers.add_parser("single", help="Process one topic")
    p_single.add_argument("topic_id", help="Topic ID to process")
    p_single.add_argument("--no-post", action="store_true")
    p_single.set_defaults(func=cmd_single)

    # add
    p_add = subparsers.add_parser("add", help="Import topics from CSV")
    p_add.add_argument("csv_file", help="Path to CSV with topics")
    p_add.set_defaults(func=cmd_add)

    # status
    p_status = subparsers.add_parser("status", help="Show status summary")
    p_status.set_defaults(func=cmd_status)

    # queue
    p_queue = subparsers.add_parser("queue", help="Show ready-to-post queue")
    p_queue.set_defaults(func=cmd_queue)

    # retry
    p_retry = subparsers.add_parser("retry", help="Retry failed topics")
    p_retry.set_defaults(func=cmd_retry)

    # test
    p_test = subparsers.add_parser("test", help="Run a test topic through pipeline")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
