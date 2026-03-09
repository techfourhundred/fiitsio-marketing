#!/usr/bin/env python3
"""
Fiitsio Daily Content Runner
The main orchestration script — runs once/day to generate and schedule posts.

Usage:
  python3 run_daily.py              # Generate + schedule today's posts
  python3 run_daily.py --dry-run   # Preview without posting
  python3 run_daily.py --topic member_churn_signs  # Force specific topic
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from content_brain import (
    pick_next_topic,
    get_slide_content_for_topic,
    log_post,
    TOPICS_POOL,
)
from generate_slide import generate_slideshow
from postiz_poster import (
    post_tiktok_slideshow,
    post_instagram_carousel,
    post_x_with_image,
)

BASE_DIR   = Path(__file__).parent.parent
LOG_FILE   = BASE_DIR / 'logs' / 'post_history.json'
OUTPUT_DIR = BASE_DIR / 'output'


def build_caption(topic_data: dict, platform: str) -> str:
    """Build a platform-optimised caption."""
    hook    = topic_data['caption_hook']
    tags    = topic_data['hashtags'][0]
    cta_map = {
        'tiktok':    '\n\n👇 Free trial: fiitsio.com',
        'instagram': '\n\n🔗 Book a free demo — link in bio\n\n',
        'x':         '\n\nfiitsio.com',
    }
    cta = cta_map.get(platform, '')

    if platform == 'tiktok':
        return f"{hook}{cta}\n\n{tags}"
    elif platform == 'instagram':
        return f"{hook}{cta}{tags}"
    else:
        return f"{hook}{cta}\n\n{tags}"


def run(dry_run: bool = False, force_topic: str | None = None) -> None:
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    print(f'\n{"="*60}')
    print(f'🏋️  FIITSIO CONTENT ENGINE — {timestamp}')
    print(f'Mode: {"DRY RUN" if dry_run else "LIVE POSTING"}')
    print('='*60)

    # 1. Pick today's topic
    if force_topic:
        topic = next((t for t in TOPICS_POOL if t['topic'] == force_topic), None)
        if not topic:
            print(f'❌ Unknown topic: {force_topic}')
            sys.exit(1)
    else:
        topic = pick_next_topic(str(LOG_FILE))

    print(f'\n📌 Topic: {topic["title"]}')
    print(f'📝 Template: {topic["template"]}')

    # 2. Generate slide content
    slides_data = get_slide_content_for_topic(topic)
    print(f'\n📊 Generating {len(slides_data)} slides...')

    # 3. Render slides to images
    session_id = f'{topic["topic"]}_{timestamp}'
    image_paths = generate_slideshow(slides_data, session_id)
    print(f'✅ Rendered {len(image_paths)} slide images')

    # 4. Build captions per platform
    results = {}

    # 4a. TikTok
    if os.environ.get('POSTIZ_TIKTOK_ID'):
        print('\n📱 Posting to TikTok...')
        caption = build_caption(topic, 'tiktok')
        result = post_tiktok_slideshow(image_paths, caption, dry_run=dry_run)
        results['tiktok'] = result
    else:
        print('\n⚠️  TikTok: POSTIZ_TIKTOK_ID not set — skipping')

    # 4b. Instagram
    if os.environ.get('POSTIZ_INSTAGRAM_ID'):
        print('\n📸 Posting to Instagram...')
        caption = build_caption(topic, 'instagram')
        result = post_instagram_carousel(image_paths, caption, dry_run=dry_run)
        results['instagram'] = result
    else:
        print('\n⚠️  Instagram: POSTIZ_INSTAGRAM_ID not set — skipping')

    # 4c. X (first slide only + text)
    if os.environ.get('POSTIZ_X_ID'):
        print('\n𝕏 Posting to X...')
        caption = build_caption(topic, 'x')
        result = post_x_with_image(caption, image_paths[0] if image_paths else None, dry_run=dry_run)
        results['x'] = result
    else:
        print('\n⚠️  X: POSTIZ_X_ID not set — skipping')

    # 5. Log
    log_post(topic, str(LOG_FILE), results)

    # 6. Summary
    print(f'\n{"="*60}')
    print('📊 SUMMARY')
    print(f'  Topic: {topic["title"]}')
    print(f'  Slides generated: {len(image_paths)}')
    print(f'  Posts scheduled: {len([r for r in results.values() if r])}')
    print(f'  Session: {session_id}')
    if not dry_run:
        print('\n  🚀 Content live on schedule!')
    else:
        print('\n  🔍 DRY RUN complete — nothing posted')
    print('='*60)

    # 7. Notify Kevin via Telegram with caption (he needs to paste it into TikTok drafts + add music)
    tiktok_caption = build_caption(topic, 'tiktok')
    try:
        status = 'dry run ✋' if dry_run else '✅ in your TikTok drafts'
        msg = (
            f'📱 *New Fiitsio TikTok — {status}*\n\n'
            f'*Topic:* {topic["title"]}\n\n'
            f'*Caption to paste:*\n```\n{tiktok_caption}\n```\n\n'
            f'Steps:\n'
            f'1. Open TikTok → Me → Drafts\n'
            f'2. Pick a trending sound 🎵\n'
            f'3. Paste the caption above\n'
            f'4. Hit publish 🚀\n\n'
            f'_(~60 seconds your side — I did the rest)_'
        )
        subprocess.run(
            ['openclaw', 'message', '--channel', 'telegram', '--to', '2134261247', '--text', msg],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass  # Non-critical — caption also logged below

    print(f'\n📋 CAPTION FOR TIKTOK:\n{tiktok_caption}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=False)
    parser.add_argument('--topic', type=str, help='Force a specific topic')
    args = parser.parse_args()

    run(dry_run=args.dry_run, force_topic=args.topic)
