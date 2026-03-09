#!/usr/bin/env python3
"""
Overnight batch pre-generator.
Run this at ~11 PM to generate tomorrow's images at 50% cost.
Results ready by morning when run_daily.py picks them up.

Usage:
  python3 batch_overnight.py         # Queue tomorrow's content
  python3 batch_overnight.py --check # Check pending batch results
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from content_brain import pick_next_topic, TOPICS_POOL
from generate_ai_bg import submit_batch_generation, check_and_download_batch, STYLE_VARIANTS

BASE_DIR    = Path(__file__).parent.parent
BATCH_LOG   = BASE_DIR / 'logs' / 'pending_batches.json'
OUTPUT_DIR  = BASE_DIR / 'output'
LOG_FILE    = BASE_DIR / 'logs' / 'post_history.json'


def load_batch_log() -> list:
    if not BATCH_LOG.exists():
        return []
    with open(BATCH_LOG) as f:
        return json.load(f)


def save_batch_log(log: list) -> None:
    os.makedirs(BATCH_LOG.parent, exist_ok=True)
    with open(BATCH_LOG, 'w') as f:
        json.dump(log, f, indent=2)


def queue_tomorrow() -> None:
    """Pick next 2 topics and submit their images to batch API."""
    if not os.environ.get('OPENAI_API_KEY'):
        print('⚠️  OPENAI_API_KEY not set — batch generation skipped')
        return

    # Pick next 2 topics (tomorrow + day after)
    used_topics = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            history = json.load(f)
        used_topics = [h['topic'] for h in history[-3:]]

    sessions = []
    count = 0
    for topic in TOPICS_POOL:
        if topic['topic'] not in used_topics and count < 2:
            sessions.append({
                'session_id': topic['topic'],
                'style_sequence': list(STYLE_VARIANTS.keys())[:6],
            })
            count += 1

    if not sessions:
        print('⚠️  No topics available for batch')
        return

    print(f'🌙 Queueing batch for topics: {[s["session_id"] for s in sessions]}')
    batch_id = submit_batch_generation(sessions)

    if batch_id:
        log = load_batch_log()
        log.append({
            'batch_id': batch_id,
            'sessions': [s['session_id'] for s in sessions],
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'status': 'pending',
        })
        save_batch_log(log)
        print(f'✅ Batch {batch_id} queued — results ready in ~24h at 50% cost')


def check_pending() -> None:
    """Check all pending batches and download completed results."""
    log = load_batch_log()
    updated = False

    for entry in log:
        if entry.get('status') == 'completed':
            continue

        batch_id = entry['batch_id']
        print(f'Checking batch {batch_id}...')
        results = check_and_download_batch(batch_id, str(OUTPUT_DIR))

        if results:
            entry['status'] = 'completed'
            entry['completed_at'] = datetime.now(timezone.utc).isoformat()
            entry['files'] = list(results.values())
            updated = True
            print(f'✅ {len(results)} images ready for: {entry["sessions"]}')

    if updated:
        save_batch_log(log)

    pending = [e for e in log if e.get('status') != 'completed']
    if pending:
        print(f'⏳ {len(pending)} batch(es) still pending')
    else:
        print('✅ All batches completed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Check + download completed batches')
    args = parser.parse_args()

    if args.check:
        check_pending()
    else:
        queue_tomorrow()
