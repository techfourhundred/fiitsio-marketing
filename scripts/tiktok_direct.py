#!/usr/bin/env python3
"""
TikTok Direct Posting — no Postiz, no fees, 100% free.
Uses TikTok's Content Posting API directly.

Photo posts (slideshows):
  - Images served from https://fiitsio.com/tiktok-slides/{session}/
  - TikTok pulls them via PULL_FROM_URL
  - privacy_level=SELF_ONLY → lands in TikTok drafts
  - Kevin adds music + publishes (~60 seconds)

Token management:
  - Access tokens expire in 24h, auto-refreshed from refresh_token
  - Refresh tokens last 365 days

Scopes required: video.publish
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

TOKEN_FILE      = Path(__file__).parent.parent / 'config' / 'tiktok_tokens.json'
CLIENT_KEY_FILE = Path(__file__).parent.parent / 'config' / 'tiktok_client.json'
SERVE_DIR       = Path('/var/www/tiktok-slides')  # nginx serves this publicly

BASE_URL   = 'https://open.tiktokapis.com/v2'
SLIDES_URL = 'https://fiitsio.com/tiktok-slides'


# ── Token management ─────────────────────────────────────────────────────────

def load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f'No TikTok tokens found. Run: python3 tiktok_auth.py'
        )
    return json.loads(TOKEN_FILE.read_text())


def load_client_creds() -> tuple[str, str]:
    """Load client_key + client_secret from env or config file."""
    key = os.environ.get('TIKTOK_CLIENT_KEY')
    secret = os.environ.get('TIKTOK_CLIENT_SECRET')
    if key and secret:
        return key, secret

    if CLIENT_KEY_FILE.exists():
        creds = json.loads(CLIENT_KEY_FILE.read_text())
        return creds['client_key'], creds['client_secret']

    raise EnvironmentError(
        'Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET, or run tiktok_auth.py first'
    )


def save_tokens(tokens: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def is_token_expired(tokens: dict) -> bool:
    obtained = datetime.fromisoformat(tokens['obtained_at'])
    expires_in = tokens.get('expires_in', 86400)
    expires_at = obtained + timedelta(seconds=expires_in - 300)  # 5 min buffer
    return datetime.now(timezone.utc) > expires_at


def refresh_access_token(tokens: dict) -> dict:
    """Refresh the access token using the refresh_token."""
    client_key, client_secret = load_client_creds()

    print('🔄 Refreshing TikTok access token...')
    resp = requests.post(
        f'{BASE_URL}/oauth/token/',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_key': client_key,
            'client_secret': client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token'],
        },
    )
    data = resp.json()
    if 'access_token' not in data:
        raise ValueError(f'Token refresh failed: {data}')

    updated = {
        **tokens,
        'access_token': data['access_token'],
        'refresh_token': data.get('refresh_token', tokens['refresh_token']),
        'expires_in': data.get('expires_in', 86400),
        'obtained_at': datetime.now(timezone.utc).isoformat(),
    }
    save_tokens(updated)
    print('✅ Token refreshed')
    return updated


def get_valid_token() -> tuple[str, str]:
    """Return (access_token, open_id), refreshing if needed."""
    tokens = load_tokens()
    if is_token_expired(tokens):
        tokens = refresh_access_token(tokens)
    return tokens['access_token'], tokens['open_id']


# ── API calls ────────────────────────────────────────────────────────────────

def auth_headers(access_token: str) -> dict:
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json; charset=UTF-8',
    }


def query_creator_info(access_token: str) -> dict:
    """Required by TikTok before posting — get creator's privacy options."""
    resp = requests.post(
        f'{BASE_URL}/post/publish/creator_info/query/',
        headers=auth_headers(access_token),
    )
    data = resp.json()
    if data.get('error', {}).get('code') != 'ok':
        raise ValueError(f'Creator info query failed: {data}')
    return data['data']


def post_photo_slideshow(
    session_id: str,
    image_filenames: list[str],
    caption: str,
    access_token: str,
    dry_run: bool = False,
) -> dict | None:
    """
    Post a photo slideshow to TikTok drafts.
    Images are served from https://fiitsio.com/tiktok-slides/{session_id}/{filename}
    TikTok pulls them via PULL_FROM_URL — no file upload needed.

    privacy_level=SELF_ONLY → lands in drafts → Kevin adds music + publishes.
    """
    # Build public URLs for each slide
    photo_urls = [
        f'{SLIDES_URL}/{session_id}/{fname}'
        for fname in image_filenames
    ]

    print(f'📸 Photo URLs:')
    for url in photo_urls:
        print(f'   {url}')

    payload = {
        'post_info': {
            'title': caption,           # TikTok uses 'title' for photo post caption
            'privacy_level': 'SELF_ONLY',  # → drafts; Kevin adds music + publishes
            'disable_comment': False,
            'disable_duet': False,
            'disable_stitch': False,
            'auto_add_music': False,    # Kevin picks trending sound manually
        },
        'source_info': {
            'source': 'PULL_FROM_URL',
            'photo_cover_index': 1,     # First slide as cover
            'photo_images': photo_urls,
        },
        'post_mode': 'DIRECT_POST',
        'media_type': 'PHOTO',
    }

    if dry_run:
        print('🔍 DRY RUN — payload:')
        print(json.dumps(payload, indent=2))
        return {'status': 'dry_run', 'payload': payload}

    print(f'📤 Posting slideshow to TikTok ({len(photo_urls)} slides)...')
    resp = requests.post(
        f'{BASE_URL}/post/publish/content/init/',
        headers=auth_headers(access_token),
        json=payload,
    )
    data = resp.json()

    if data.get('error', {}).get('code') != 'ok':
        print(f'❌ Post failed: {data}')
        return None

    publish_id = data['data']['publish_id']
    print(f'✅ Slideshow posted to TikTok drafts — publish_id: {publish_id}')

    # Schedule cleanup of served slides after 1h (TikTok will have pulled them by then)
    # Find session_id from the photo URLs
    session_from_url = photo_urls[0].split('/')[-2] if photo_urls else None
    if session_from_url:
        cleanup_served_slides(session_from_url, delay_seconds=3600)
        print('   🕐 Slides auto-cleanup scheduled in 1h')

    return {'publish_id': publish_id, 'status': 'draft'}


def cleanup_served_slides(session_id: str, delay_seconds: int = 3600) -> None:
    """
    Remove slides from the public serve directory after TikTok has processed them.
    TikTok pulls images within ~5 min of posting; we wait 1h to be safe.
    Call this in a background thread or cron.
    """
    import shutil
    import threading

    def _cleanup():
        time.sleep(delay_seconds)
        serve_dir = SERVE_DIR / session_id
        if serve_dir.exists():
            shutil.rmtree(serve_dir)
            print(f'🧹 Cleaned up served slides: {serve_dir}')

    t = threading.Thread(target=_cleanup, daemon=True)
    t.start()


def check_post_status(publish_id: str, access_token: str) -> dict:
    """Check publish status — useful to confirm TikTok processed the images."""
    resp = requests.post(
        f'{BASE_URL}/post/publish/status/fetch/',
        headers=auth_headers(access_token),
        json={'publish_id': publish_id},
    )
    return resp.json()


def post_slideshow(
    session_id: str,
    image_paths: list[str],
    caption: str,
    dry_run: bool = False,
) -> dict | None:
    """
    Main entry point. Given local image paths + caption, post to TikTok drafts.
    Images must already be in /home/kevin/fiitsio-marketing/output/{session_id}/
    (served by nginx at https://fiitsio.com/tiktok-slides/{session_id}/)
    """
    try:
        access_token, open_id = get_valid_token()
    except FileNotFoundError as e:
        print(f'⚠️  {e}')
        return None

    if not dry_run:
        # Required by TikTok API — query creator before posting
        try:
            creator = query_creator_info(access_token)
            print(f'👤 Creator: @{creator.get("creator_username")}')
        except Exception as e:
            print(f'⚠️  Creator info query failed: {e}')
            # Continue — might still work

    # Copy slides to nginx serve dir so TikTok can pull them
    import shutil
    serve_session_dir = SERVE_DIR / session_id
    serve_session_dir.mkdir(parents=True, exist_ok=True)
    filenames = []
    for p in image_paths:
        fname = Path(p).name
        dest = serve_session_dir / fname
        shutil.copy2(p, dest)
        dest.chmod(0o644)
        filenames.append(fname)
    print(f'📂 Slides copied to {serve_session_dir} (publicly served)')

    return post_photo_slideshow(
        session_id=session_id,
        image_filenames=filenames,
        caption=caption,
        access_token=access_token,
        dry_run=dry_run,
    )


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-status', type=str, metavar='PUBLISH_ID')
    parser.add_argument('--test', action='store_true', help='Test token + creator info only')
    args = parser.parse_args()

    if args.check_status:
        token, _ = get_valid_token()
        status = check_post_status(args.check_status, token)
        print(json.dumps(status, indent=2))

    elif args.test:
        print('🧪 Testing TikTok connection...')
        token, open_id = get_valid_token()
        print(f'✅ Token valid. Open ID: {open_id}')
        creator = query_creator_info(token)
        print(f'✅ Creator: @{creator.get("creator_username")}')
        print(f'   Privacy options: {creator.get("privacy_level_options")}')

    else:
        print('Run with --test to verify connection')
        print('Run with --check-status PUBLISH_ID to check a post status')
        print('Or import post_slideshow() from run_daily.py')
