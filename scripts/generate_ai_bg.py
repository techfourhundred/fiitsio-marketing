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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--style', default='modern_clean', choices=STYLE_VARIANTS.keys())
    parser.add_argument('--output', default='/tmp/test_bg.jpg')
    args = parser.parse_args()

    path = generate_gym_background(args.style, args.output)
    if path:
        print(f'✅ Generated: {path}')
    else:
        print('❌ Failed or no API key')
