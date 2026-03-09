#!/usr/bin/env python3
"""
Fiitsio Slide Generator
Generates TikTok/Instagram slideshow images with text overlays.
No DALL-E required for first version — uses gradient backgrounds + bold text.
Can be upgraded to use OpenAI image generation.
"""

import sys
import json
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import colorsys

# ── Config ──────────────────────────────────────────────────────────────────
SLIDE_W = 1080
SLIDE_H = 1920
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')

# Fiitsio brand colours
COLORS = {
    'navy':    (10,  15,  30),
    'blue':    (79,  158, 255),
    'green':   (0,   229, 160),
    'amber':   (255, 180, 0),
    'red':     (255, 59,  48),
    'white':   (255, 255, 255),
    'offwhite':(248, 249, 252),
    'grey':    (120, 130, 145),
}

SLIDE_THEMES = [
    {'bg': COLORS['navy'],   'accent': COLORS['green'],  'text': COLORS['white']},
    {'bg': COLORS['navy'],   'accent': COLORS['blue'],   'text': COLORS['white']},
    {'bg': COLORS['white'],  'accent': COLORS['navy'],   'text': COLORS['navy']},
    {'bg': COLORS['green'],  'accent': COLORS['navy'],   'text': COLORS['navy']},
    {'bg': COLORS['blue'],   'accent': COLORS['white'],  'text': COLORS['white']},
    {'bg': (20, 20, 35),     'accent': COLORS['amber'],  'text': COLORS['white']},
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a system font, fall back to default."""
    font_paths = [
        f'/usr/share/fonts/truetype/liberation/LiberationSans-{"Bold" if bold else "Regular"}.ttf',
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf',
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf' if bold else '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf',
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_gradient_bg(draw: ImageDraw.Draw, color1: tuple, color2: tuple) -> None:
    """Draw a vertical gradient background."""
    for y in range(SLIDE_H):
        ratio = y / SLIDE_H
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (SLIDE_W, y)], fill=(r, g, b))


def draw_accent_bar(draw: ImageDraw.Draw, color: tuple, y_pos: int = 120) -> None:
    """Draw a horizontal accent bar."""
    draw.rectangle([(80, y_pos), (200, y_pos + 8)], fill=color)


def wrap_text(text: str, max_chars: int = 22) -> list[str]:
    """Wrap text to fit slide width."""
    return textwrap.wrap(text, width=max_chars)


def generate_slide(
    slide_num: int,
    total_slides: int,
    headline: str,
    body: str | None,
    theme_idx: int,
    stat: str | None = None,
    output_path: str | None = None,
) -> str:
    """Generate a single slide image."""
    theme = SLIDE_THEMES[theme_idx % len(SLIDE_THEMES)]

    img = Image.new('RGB', (SLIDE_W, SLIDE_H), theme['bg'])
    draw = ImageDraw.Draw(img)

    # Gradient bg (subtle)
    bg_dark = tuple(max(0, c - 20) for c in theme['bg'])
    draw_gradient_bg(draw, theme['bg'], bg_dark)

    # Accent bar
    draw_accent_bar(draw, theme['accent'], y_pos=140)

    # Slide counter
    counter_font = load_font(36)
    counter_text = f'{slide_num}/{total_slides}'
    draw.text((80, 80), counter_text, font=counter_font, fill=theme['grey'] if 'grey' in dir() else (150, 150, 150))

    # Big stat (if provided) — center of slide
    if stat:
        stat_font = load_font(180, bold=True)
        stat_bbox = draw.textbbox((0, 0), stat, font=stat_font)
        stat_w = stat_bbox[2] - stat_bbox[0]
        stat_x = (SLIDE_W - stat_w) // 2
        draw.text((stat_x, 600), stat, font=stat_font, fill=theme['accent'])

    # Headline
    headline_font = load_font(88, bold=True)
    wrapped_headline = wrap_text(headline, max_chars=18)
    y = 300 if not stat else 950
    for line in wrapped_headline:
        bbox = draw.textbbox((0, 0), line, font=headline_font)
        line_w = bbox[2] - bbox[0]
        x = (SLIDE_W - line_w) // 2
        draw.text((x, y), line, font=headline_font, fill=theme['text'])
        y += 110

    # Body text
    if body:
        body_font = load_font(54)
        wrapped_body = wrap_text(body, max_chars=28)
        y += 60
        for line in wrapped_body:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            line_w = bbox[2] - bbox[0]
            x = (SLIDE_W - line_w) // 2
            r, g, b = theme['text']
            draw.text((x, y), line, font=body_font, fill=(r, g, b, 200))
            y += 72

    # Fiitsio watermark (bottom)
    brand_font = load_font(42, bold=True)
    draw.text((80, SLIDE_H - 100), 'fiitsio.com', font=brand_font, fill=theme['accent'])

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, f'slide_{slide_num:02d}.jpg')
    img.save(output_path, 'JPEG', quality=95)
    return output_path


def generate_slide_over_bg(
    slide_num: int,
    total_slides: int,
    headline: str,
    body: str | None,
    stat: str | None,
    bg_image_path: str,
    output_path: str,
) -> str:
    """Composite text + overlay over an AI-generated background image."""
    bg = Image.open(bg_image_path).convert('RGB')
    # Resize/crop to exact 1080x1920
    bg = bg.resize((SLIDE_W, SLIDE_H), Image.LANCZOS)

    # Dark overlay so text is always readable
    overlay = Image.new('RGBA', (SLIDE_W, SLIDE_H), (0, 0, 0, 160))
    composite = Image.alpha_composite(bg.convert('RGBA'), overlay).convert('RGB')

    draw = ImageDraw.Draw(composite)

    # Use white text on dark overlay
    theme = {'text': COLORS['white'], 'accent': COLORS['green']}

    # Accent bar
    draw_accent_bar(draw, theme['accent'], y_pos=140)

    # Slide counter
    counter_font = load_font(36)
    draw.text((80, 80), f'{slide_num}/{total_slides}', font=counter_font, fill=(200, 200, 200))

    # Big stat
    if stat:
        stat_font = load_font(180, bold=True)
        stat_bbox = draw.textbbox((0, 0), stat, font=stat_font)
        stat_w = stat_bbox[2] - stat_bbox[0]
        draw.text(((SLIDE_W - stat_w) // 2, 600), stat, font=stat_font, fill=theme['accent'])

    # Headline
    headline_font = load_font(88, bold=True)
    wrapped = wrap_text(headline, max_chars=18)
    y = 300 if not stat else 950
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=headline_font)
        x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=headline_font, fill=theme['text'])
        y += 110

    # Body
    if body:
        body_font = load_font(54)
        y += 60
        for line in wrap_text(body, max_chars=28):
            bbox = draw.textbbox((0, 0), line, font=body_font)
            x = (SLIDE_W - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, font=body_font, fill=(220, 220, 220))
            y += 72

    # Watermark
    brand_font = load_font(42, bold=True)
    draw.text((80, SLIDE_H - 100), 'fiitsio.com', font=brand_font, fill=theme['accent'])

    composite.save(output_path, 'JPEG', quality=95)
    return output_path


def generate_slideshow(slides_data: list[dict], session_id: str, backgrounds: list = None) -> list[str]:
    """
    Generate all slides for a post and return file paths.
    If backgrounds is provided (list of paths or None), composite text over them.
    Falls back to gradient renderer if background path is None.
    Exactly 6 slides — always.
    """
    # Enforce exactly 6 slides
    if len(slides_data) != 6:
        raise ValueError(f'Expected exactly 6 slides, got {len(slides_data)}. TikTok sweet spot is 6.')

    total = len(slides_data)
    paths = []
    session_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    for i, slide in enumerate(slides_data, 1):
        path = os.path.join(session_dir, f'slide_{i:02d}.jpg')

        # Use AI background if provided and exists
        bg = backgrounds[i - 1] if backgrounds and i - 1 < len(backgrounds) else None

        if bg and os.path.exists(bg):
            generate_slide_over_bg(
                slide_num=i,
                total_slides=total,
                headline=slide['headline'],
                body=slide.get('body'),
                stat=slide.get('stat'),
                bg_image_path=bg,
                output_path=path,
            )
        else:
            generate_slide(
                slide_num=i,
                total_slides=total,
                headline=slide['headline'],
                body=slide.get('body'),
                stat=slide.get('stat'),
                theme_idx=i - 1,
                output_path=path,
            )

        paths.append(path)
        print(f'✅ Slide {i}/{total}: {path}')

    return paths


if __name__ == '__main__':
    # Test run
    test_slides = [
        {
            'headline': 'Your gym has a churn problem',
            'body': 'You just can\'t see it yet.',
            'stat': None,
        },
        {
            'headline': 'The #1 sign',
            'body': 'Member goes from 4x/week to 2x/week for 14 days.',
            'stat': '⚠️',
        },
        {
            'headline': '30% of members',
            'body': 'cancel in the first 90 days',
            'stat': '30%',
        },
        {
            'headline': 'Most gyms find out',
            'body': 'after they\'ve already cancelled.',
            'stat': None,
        },
        {
            'headline': 'Fiitsio alerts you',
            'body': 'automatically when a member is at risk.',
            'stat': None,
        },
    ]

    paths = generate_slideshow(test_slides, 'test_churn')
    print(f'\n🎨 Generated {len(paths)} slides:')
    for p in paths:
        print(f'  {p}')
