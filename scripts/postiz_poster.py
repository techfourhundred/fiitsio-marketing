#!/usr/bin/env python3
"""
Fiitsio Postiz Poster
Uploads slides and schedules posts via Postiz API.
Supports TikTok (slideshow), Instagram (carousel), X (thread-with-images).
"""

import os
import json
import sys
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
POSTIZ_API_KEY = os.environ.get('POSTIZ_API_KEY', '')
POSTIZ_BASE = 'https://api.postiz.com/public/v1'

# Integration IDs — set these from Postiz after connecting accounts
# Get them by running: python3 postiz_poster.py --list-integrations
INTEGRATION_IDS = {
    'tiktok':    os.environ.get('POSTIZ_TIKTOK_ID', ''),
    'instagram': os.environ.get('POSTIZ_INSTAGRAM_ID', ''),
    'x':         os.environ.get('POSTIZ_X_ID', ''),
}

OPTIMAL_POST_TIMES = {
    # (hour, minute) in UTC — gym owners active windows
    'tiktok':    [(6, 0), (11, 0), (18, 0)],
    'instagram': [(7, 0), (12, 0), (19, 0)],
    'x':         [(8, 0), (13, 0), (20, 0)],
}


def headers() -> dict:
    return {'Authorization': POSTIZ_API_KEY, 'Content-Type': 'application/json'}


def upload_image(image_path: str) -> dict | None:
    """Upload an image to Postiz and return the media object."""
    if not POSTIZ_API_KEY:
        print('⚠️  No POSTIZ_API_KEY set — skipping upload (dry run)')
        return {'id': 'dry_run', 'path': image_path}

    with open(image_path, 'rb') as f:
        response = requests.post(
            f'{POSTIZ_BASE}/upload',
            headers={'Authorization': POSTIZ_API_KEY},
            files={'file': (Path(image_path).name, f, 'image/jpeg')},
        )

    if response.status_code != 201:
        print(f'❌ Upload failed: {response.status_code} {response.text}')
        return None

    return response.json()


def list_integrations() -> list:
    """List all connected social media accounts."""
    response = requests.get(
        f'{POSTIZ_BASE}/integrations',
        headers=headers(),
    )
    if response.status_code != 200:
        print(f'❌ Error: {response.status_code} {response.text}')
        return []
    return response.json()


def next_post_time(platform: str, days_ahead: int = 0) -> str:
    """Get the next optimal posting time for a platform."""
    now = datetime.now(timezone.utc)
    times = OPTIMAL_POST_TIMES.get(platform, [(9, 0)])

    target = now + timedelta(days=days_ahead)
    for hour, minute in times:
        candidate = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate.isoformat().replace('+00:00', 'Z')

    # Default: tomorrow 9am
    tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return tomorrow.isoformat().replace('+00:00', 'Z')


def post_tiktok_slideshow(
    image_paths: list[str],
    caption: str,
    schedule_time: str | None = None,
    dry_run: bool = False,
) -> dict | None:
    """Post a TikTok slideshow (carousel of images)."""
    integration_id = INTEGRATION_IDS['tiktok']
    if not integration_id:
        print('⚠️  POSTIZ_TIKTOK_ID not set')
        return None

    # Upload images
    print(f'📤 Uploading {len(image_paths)} images to Postiz...')
    images = []
    for path in image_paths:
        media = upload_image(path)
        if media:
            images.append(media)
            print(f'  ✅ {Path(path).name} → {media.get("id")}')

    if not images:
        print('❌ No images uploaded successfully')
        return None

    post_time = schedule_time or next_post_time('tiktok')
    post_type = 'now' if not schedule_time else 'schedule'

    payload = {
        'type': post_type,
        'date': post_time,
        'shortLink': False,
        'tags': [],
        'posts': [{
            'integration': {'id': integration_id},
            'value': [{
                'content': caption,
                'image': images,
            }],
            'settings': {
                '__type': 'tiktok',
                'privacy_level': 'SELF_ONLY',   # → lands in TikTok drafts; Kevin adds music + publishes
                'comment': True,
                'duet': False,
                'stitch': False,
                'autoAddMusic': False,           # don't randomise; Kevin picks trending sound manually
                'content_posting_method': 'UPLOAD_TO_QUEUE',
            },
        }],
    }

    if dry_run:
        print('🔍 DRY RUN — payload:')
        print(json.dumps(payload, indent=2))
        return {'status': 'dry_run', 'payload': payload}

    print(f'📅 Scheduling TikTok post for {post_time}...')
    response = requests.post(
        f'{POSTIZ_BASE}/posts',
        headers=headers(),
        json=payload,
    )

    if response.status_code not in (200, 201):
        print(f'❌ Post failed: {response.status_code} {response.text}')
        return None

    result = response.json()
    print(f'✅ TikTok post scheduled: {result}')
    return result


def post_instagram_carousel(
    image_paths: list[str],
    caption: str,
    schedule_time: str | None = None,
    dry_run: bool = False,
) -> dict | None:
    """Post an Instagram carousel."""
    integration_id = INTEGRATION_IDS['instagram']
    if not integration_id:
        print('⚠️  POSTIZ_INSTAGRAM_ID not set')
        return None

    images = []
    for path in image_paths:
        media = upload_image(path)
        if media:
            images.append(media)

    post_time = schedule_time or next_post_time('instagram')
    post_type = 'now' if not schedule_time else 'schedule'

    payload = {
        'type': post_type,
        'date': post_time,
        'shortLink': False,
        'tags': [],
        'posts': [{
            'integration': {'id': integration_id},
            'value': [{'content': caption, 'image': images}],
            'settings': {
                '__type': 'instagram',
                'post_type': 'carousel',
            },
        }],
    }

    if dry_run:
        print('🔍 DRY RUN — Instagram payload ready')
        return {'status': 'dry_run', 'payload': payload}

    response = requests.post(f'{POSTIZ_BASE}/posts', headers=headers(), json=payload)
    if response.status_code not in (200, 201):
        print(f'❌ Instagram post failed: {response.status_code} {response.text}')
        return None
    return response.json()


def post_x_with_image(
    text: str,
    image_path: str | None = None,
    schedule_time: str | None = None,
    dry_run: bool = False,
) -> dict | None:
    """Post to X (Twitter) with optional image."""
    integration_id = INTEGRATION_IDS['x']
    if not integration_id:
        print('⚠️  POSTIZ_X_ID not set')
        return None

    images = []
    if image_path:
        media = upload_image(image_path)
        if media:
            images.append(media)

    post_time = schedule_time or next_post_time('x')
    post_type = 'now' if not schedule_time else 'schedule'

    payload = {
        'type': post_type,
        'date': post_time,
        'shortLink': False,
        'tags': [],
        'posts': [{
            'integration': {'id': integration_id},
            'value': [{'content': text, 'image': images}],
            'settings': {
                '__type': 'x',
                'who_can_reply_post': 'everyone',
            },
        }],
    }

    if dry_run:
        print('🔍 DRY RUN — X payload ready')
        return {'status': 'dry_run', 'payload': payload}

    response = requests.post(f'{POSTIZ_BASE}/posts', headers=headers(), json=payload)
    if response.status_code not in (200, 201):
        print(f'❌ X post failed: {response.status_code} {response.text}')
        return None
    return response.json()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Fiitsio Postiz Poster')
    parser.add_argument('--list-integrations', action='store_true')
    parser.add_argument('--dry-run', action='store_true', default=True)
    args = parser.parse_args()

    if args.list_integrations:
        integrations = list_integrations()
        print('Connected accounts:')
        for i in integrations:
            print(f"  {i.get('providerIdentifier', '?'):12} | {i.get('name', '?'):30} | id: {i.get('id')}")
    else:
        print('Run with --list-integrations to see connected accounts')
        print('Set POSTIZ_API_KEY, POSTIZ_TIKTOK_ID, etc. in environment to activate')
