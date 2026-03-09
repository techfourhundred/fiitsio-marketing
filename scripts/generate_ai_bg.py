#!/usr/bin/env python3
"""
Fiitsio AI Background Generator
Uses OpenAI gpt-image-1 to generate gym background images for slides.
Requires: OPENAI_API_KEY env var

KEY LESSON (from Oliver Henry / Larry):
- Be OBSESSIVELY specific about architecture. Lock it across all slides.
- Only vary the style/scenario between slides. 
- "iPhone photo" + "realistic lighting" = photos that look real, not AI art.
- Signs of life matter: gym bag on bench, towel on equipment, water bottle.
  Without these, it looks like an empty showroom and nobody relates.
- Early failure: "a modern gym" → completely different rooms every slide.
  Fix: lock every architectural detail, only change the style/mood.
"""

import os
import sys
import requests
import base64
from pathlib import Path

# Locked architecture prompt — same base for every Fiitsio gym slide
# Only the STYLE section (bold part) changes between slides
GYM_ARCHITECTURE_BASE = """
iPhone photo of a mid-sized urban gym in Portugal. Shot from the entrance looking straight down 
the main floor. The gym is roughly 15m x 8m. Weight rack along the right wall with barbells and 
dumbbells neatly arranged from 5kg to 50kg. Four squat racks in a row on the left side, evenly 
spaced. Rubber flooring throughout, black with grey lane markings. High ceiling, approximately 
4m, exposed industrial beams painted black. One large window on the far wall, floor-to-ceiling, 
natural light coming in from the left. A reception desk in the near-right corner — small, modern, 
a Mac on the desk, a plant, business cards. Signs of life: a gym bag on one of the benches, a 
towel on a squat rack, a water bottle on the floor near the weights. A member's headphones are 
on the bench. The gym has customers — two people training in the background but not the focus. 
Natural phone camera quality, realistic lighting, portrait orientation, slight wide-angle lens.
"""

STYLE_VARIANTS = {
    "modern_clean": "Modern, clean, minimalist aesthetic. White walls, bright LED lighting. Everything in order. Aspirational but attainable.",
    "morning_light": "Early morning. Golden hour sunlight streaming through the far window. Long shadows across the floor. Quiet, before the rush.",
    "busy_evening": "Evening peak hours. Warm, slightly amber lighting. Energy in the room. Two more people visible in background.",
    "professional_dark": "Moody, professional look. Dark walls, dramatic spotlights on equipment. High contrast. Premium feel.",
    "before_state": "The gym looks slightly tired. Equipment is older, some rust on the barbell collars. Fluorescent lighting, a bit harsh. Nothing broken, but needs modernising.",
    "after_fiitsio": "Same gym, visibly upgraded. New equipment, fresh paint, brighter lights. A Fiitsio QR code check-in stand visible at the entrance. More people, more energy.",
}


def generate_gym_background(
    style_key: str,
    output_path: str,
    size: str = "1024x1792",  # Closest to 9:16 available
) -> str | None:
    """Generate a gym background image using OpenAI."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print('⚠️  OPENAI_API_KEY not set — using gradient fallback')
        return None

    style_desc = STYLE_VARIANTS.get(style_key, STYLE_VARIANTS['modern_clean'])

    # Architecture locked + only style changes
    full_prompt = f"{GYM_ARCHITECTURE_BASE.strip()}\n\nSTYLE: {style_desc}"

    print(f'🎨 Generating AI background: {style_key}...')

    try:
        response = requests.post(
            'https://api.openai.com/v1/images/generations',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'gpt-image-1',
                'prompt': full_prompt,
                'n': 1,
                'size': size,
                'quality': 'standard',
                'response_format': 'b64_json',
            },
            timeout=60,
        )

        if response.status_code != 200:
            print(f'❌ OpenAI error: {response.status_code} {response.text[:200]}')
            return None

        data = response.json()
        img_b64 = data['data'][0]['b64_json']
        img_bytes = base64.b64decode(img_b64)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(img_bytes)

        print(f'  ✅ Saved: {output_path}')
        return output_path

    except Exception as e:
        print(f'❌ Generation failed: {e}')
        return None


def generate_slide_backgrounds(session_dir: str, num_slides: int = 6) -> list[str | None]:
    """
    Generate background images for all 6 slides in a post.
    Uses consistent gym architecture, varies mood/lighting per slide.
    Falls back to None (triggers gradient renderer) if no API key.
    """
    style_sequence = [
        'morning_light',
        'modern_clean',
        'professional_dark',
        'busy_evening',
        'modern_clean',
        'after_fiitsio',
    ]

    backgrounds = []
    for i in range(num_slides):
        style = style_sequence[i % len(style_sequence)]
        bg_path = os.path.join(session_dir, f'bg_{i+1:02d}.jpg')

        # Don't regenerate if already exists
        if os.path.exists(bg_path):
            backgrounds.append(bg_path)
            continue

        result = generate_gym_background(style, bg_path)
        backgrounds.append(result)  # None = use gradient

    return backgrounds


## ── BATCH API (50% cheaper, for overnight pre-generation) ──────────────────
## Use batch API when generating ahead of schedule (not same-day urgent posts).
## Real-time: ~$0.50/post | Batch API: ~$0.25/post (50% discount, results in ~24h)

def submit_batch_generation(sessions: list[dict]) -> str | None:
    """
    Submit a batch of image generation requests to OpenAI's Batch API.
    50% cheaper than real-time. Results available within 24h.

    sessions: list of {"session_id": str, "style_sequence": list[str]}
    Returns: batch_id to poll later
    """
    import json
    import tempfile

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print('⚠️  OPENAI_API_KEY not set')
        return None

    # Build JSONL batch file
    requests_list = []
    for session in sessions:
        styles = session.get('style_sequence', list(STYLE_VARIANTS.keys())[:6])
        for i, style in enumerate(styles[:6]):
            style_desc = STYLE_VARIANTS.get(style, STYLE_VARIANTS['modern_clean'])
            prompt = f"{GYM_ARCHITECTURE_BASE.strip()}\n\nSTYLE: {style_desc}"
            requests_list.append({
                'custom_id': f"{session['session_id']}_slide_{i+1:02d}",
                'method': 'POST',
                'url': '/v1/images/generations',
                'body': {
                    'model': 'gpt-image-1',
                    'prompt': prompt,
                    'n': 1,
                    'size': '1024x1792',
                    'quality': 'standard',
                    'response_format': 'b64_json',
                },
            })

    # Write to temp JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for req in requests_list:
            f.write(json.dumps(req) + '\n')
        tmpfile = f.name

    print(f'📦 Submitting batch of {len(requests_list)} image requests...')

    try:
        # Upload file
        with open(tmpfile, 'rb') as f:
            upload_resp = requests.post(
                'https://api.openai.com/v1/files',
                headers={'Authorization': f'Bearer {api_key}'},
                files={'file': ('batch.jsonl', f, 'application/json-lines')},
                data={'purpose': 'batch'},
            )
        file_id = upload_resp.json().get('id')
        if not file_id:
            print(f'❌ File upload failed: {upload_resp.text}')
            return None

        # Create batch
        batch_resp = requests.post(
            'https://api.openai.com/v1/batches',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'input_file_id': file_id, 'endpoint': '/v1/images/generations', 'completion_window': '24h'},
        )
        batch_id = batch_resp.json().get('id')
        print(f'✅ Batch submitted: {batch_id} (~24h, 50% cheaper)')
        return batch_id

    except Exception as e:
        print(f'❌ Batch submission failed: {e}')
        return None
    finally:
        os.unlink(tmpfile)


def check_and_download_batch(batch_id: str, output_base_dir: str) -> dict:
    """
    Check batch status and download results if complete.
    Returns dict of {custom_id: file_path}
    """
    import json
    import base64

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return {}

    status_resp = requests.get(
        f'https://api.openai.com/v1/batches/{batch_id}',
        headers={'Authorization': f'Bearer {api_key}'},
    )
    batch = status_resp.json()
    status = batch.get('status')
    print(f'Batch {batch_id}: {status}')

    if status != 'completed':
        return {}

    # Download output file
    output_file_id = batch.get('output_file_id')
    output_resp = requests.get(
        f'https://api.openai.com/v1/files/{output_file_id}/content',
        headers={'Authorization': f'Bearer {api_key}'},
    )

    results = {}
    for line in output_resp.text.strip().split('\n'):
        item = json.loads(line)
        custom_id = item['custom_id']
        # Parse: sessionid_slide_01
        parts = custom_id.rsplit('_slide_', 1)
        if len(parts) == 2:
            session_id, slide_num = parts
            session_dir = os.path.join(output_base_dir, session_id)
            os.makedirs(session_dir, exist_ok=True)
            out_path = os.path.join(session_dir, f'bg_{slide_num}.jpg')

            b64 = item['response']['body']['data'][0]['b64_json']
            with open(out_path, 'wb') as f:
                f.write(base64.b64decode(b64))
            results[custom_id] = out_path

    print(f'✅ Downloaded {len(results)} batch images')
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--style', default='modern_clean', choices=STYLE_VARIANTS.keys())
    parser.add_argument('--output', default='/tmp/test_bg.jpg')
    parser.add_argument('--batch-tomorrow', action='store_true', help='Pre-generate tomorrow\'s posts via batch API (50% cheaper)')
    args = parser.parse_args()

    if args.batch_tomorrow:
        from content_brain import TOPICS_POOL
        # Queue the first 3 topics not recently posted
        sessions = [
            {'session_id': t['topic'], 'style_sequence': list(STYLE_VARIANTS.keys())[:6]}
            for t in TOPICS_POOL[:3]
        ]
        batch_id = submit_batch_generation(sessions)
        if batch_id:
            # Save batch ID for tomorrow's run
            batch_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'pending_batches.json')
            os.makedirs(os.path.dirname(batch_log), exist_ok=True)
            pending = []
            if os.path.exists(batch_log):
                with open(batch_log) as f:
                    pending = json.load(f)
            pending.append({'batch_id': batch_id, 'submitted_at': __import__('datetime').datetime.now().isoformat()})
            with open(batch_log, 'w') as f:
                json.dump(pending, f, indent=2)
    else:
        path = generate_gym_background(args.style, args.output)
        if path:
            print(f'✅ Generated: {path}')
        else:
            print('❌ Failed or no API key')
