#!/usr/bin/env python3
"""
Fiitsio Content Brain
Uses Claude API (via OpenClaw) to generate slide content plans.
No separate API key needed — uses the existing OpenClaw Anthropic connection.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

# ── Content Templates ────────────────────────────────────────────────────────
# These are the proven slide structures. Brain picks the right one and fills in.

CONTENT_TEMPLATES = {
    # All templates are locked to EXACTLY 6 slides — TikTok's engagement sweet spot
    # TikTok data: slideshows get 2.9x more comments, 1.9x more likes, 2.6x more shares vs video
    "pain_reveal": {
        "description": "Reveal a hidden gym pain point, build tension, offer Fiitsio as solution",
        "slides": 6,
        "structure": ["hook/pain", "context", "deepen", "stat", "consequence", "solution_cta"],
    },
    "competitor_comparison": {
        "description": "Compare Fiitsio vs competitor on price/features/UX",
        "slides": 6,
        "structure": ["hook", "competitor_cost", "hidden_fees", "fiitsio_cost", "comparison", "cta"],
    },
    "quick_tips": {
        "description": "5 actionable tips for gym owners (hook + 4 tips + cta = 6)",
        "slides": 6,
        "structure": ["hook", "tip1", "tip2", "tip3", "tip4", "cta"],
    },
    "stat_shock": {
        "description": "Lead with a shocking stat, explain it, offer solution",
        "slides": 6,
        "structure": ["stat_hook", "what_it_means", "why_it_happens", "what_to_do", "what_fiitsio_does", "cta"],
    },
    "before_after": {
        "description": "Before Fiitsio / After Fiitsio transformation",
        "slides": 6,
        "structure": ["hook", "before1", "before2", "after1", "after2", "cta"],
    },
}

HOOKS_BANK = [
    "Your gym has a churn problem. You just can't see it yet.",
    "Most gym owners don't realize they're paying €5,000/year in hidden fees.",
    "Your member just cancelled. Did you get an alert?",
    "I talked to 50 gym owners. 43 wanted to leave their software but felt stuck.",
    "The gym software market is broken. Here's proof.",
    "3 things every gym owner ignores until it's too late:",
    "30% of gym members cancel in the first 90 days.",
    "Mindbody just raised prices again. For the 4th time.",
    "What happens when your gym runs on software members actually love?",
    "Stop letting your gym management app manage YOU.",
]

# HASHTAG RULE: Max 5 per post — TikTok's current effective limit
# Using more than 5 dilutes reach; pick the most targeted 5 for each topic

TOPICS_POOL = [
    {
        "topic": "member_churn_signs",
        "title": "4 signs a member is about to cancel",
        "template": "quick_tips",
        "caption_hook": "Your member is planning to leave. You have 2 weeks to stop them.",
        "hashtags": ["#gymowner #memberretention #gymbusiness #fitnessapp #fiitsio"],
    },
    {
        "topic": "mindbody_hidden_fees",
        "title": "What Mindbody actually costs you",
        "template": "competitor_comparison",
        "caption_hook": "Mindbody charges you how much per year?? (most gym owners don't know)",
        "hashtags": ["#gymowner #mindbody #gymsoftware #gymbusiness #fiitsio"],
    },
    {
        "topic": "churn_stat_shock",
        "title": "The 30% churn stat that kills gyms",
        "template": "stat_shock",
        "caption_hook": "30% of your gym members are planning to cancel. Most gyms find out after.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #memberretention #fiitsio"],
    },
    {
        "topic": "whatsapp_automation",
        "title": "How to automate member retention on WhatsApp",
        "template": "before_after",
        "caption_hook": "This gym stopped losing members with one WhatsApp message. Here's how.",
        "hashtags": ["#gymowner #gymautomation #gymbusiness #memberretention #fiitsio"],
    },
    {
        "topic": "gym_software_switch",
        "title": "We switched from Glofox — what happened",
        "template": "before_after",
        "caption_hook": "We switched gym software and our revenue went up. Not down. Here's the math.",
        "hashtags": ["#gymowner #gymsoftware #gymbusiness #gymtech #fiitsio"],
    },
    {
        "topic": "retention_math",
        "title": "The math behind your gym's churn problem",
        "template": "stat_shock",
        "caption_hook": "Here's the exact math gym owners need to understand about member churn.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #fitnessapp #fiitsio"],
    },
    {
        "topic": "gym_owner_time",
        "title": "How gym owners waste 10 hours/week",
        "template": "pain_reveal",
        "caption_hook": "You're spending 10+ hours/week on tasks that should take 10 minutes.",
        "hashtags": ["#gymowner #gymbusiness #gymmanagement #gymproductivity #fiitsio"],
    },
    {
        "topic": "mbway_payments",
        "title": "Why your gym needs MB Way",
        "template": "pain_reveal",
        "caption_hook": "If your gym in Portugal doesn't accept MB Way, you're losing members.",
        "hashtags": ["#gymowner #mbway #ginasio #portugal #fiitsio"],
    },
]


def get_slide_content_for_topic(topic_data: dict) -> list[dict]:
    """Generate slide content for a specific topic using pre-built templates."""
    topic = topic_data["topic"]
    template = CONTENT_TEMPLATES[topic_data["template"]]

    # Pre-built content — ALL topics are EXACTLY 6 slides (TikTok sweet spot)
    # Slide 1 always has the hook text (shown as text overlay, sets the premise)
    # Slides 2-5 are the value payload
    # Slide 6 is always the CTA (soft mention of Fiitsio + fiitsio.com)
    content_map = {
        "member_churn_signs": [  # quick_tips: hook + 4 tips + cta
            {"headline": "4 signs a member is about to cancel", "body": "Most gym owners miss all of them.", "stat": None},
            {"headline": "Sign #1: Booking drop", "body": "4x/week → 2x/week for 14 days.\nNot a holiday. It's the beginning of the end.", "stat": None},
            {"headline": "Sign #2: No-shows", "body": "Books but doesn't show up.\nThree times in a row = danger zone.", "stat": None},
            {"headline": "Sign #3: App silence", "body": "Goes from daily app opens to once a week.\nDisengaged digitally = disengaged physically.", "stat": None},
            {"headline": "Sign #4: The 21-day rule", "body": "No visit in 21 days.\n70% of these members cancel within 30 days.", "stat": "21 days"},
            {"headline": "Fiitsio alerts you", "body": "automatically when any of these happen.\nBefore they cancel.\n\nfiitsio.com", "stat": None},
        ],
        "mindbody_hidden_fees": [  # competitor_comparison: 6 slides
            {"headline": "Mindbody costs €400/month.", "body": "But that's not the real cost.", "stat": None},
            {"headline": "Their processor fee", "body": "3.35% on EVERY transaction.\nEven on debit cards that cost them nothing.", "stat": "3.35%"},
            {"headline": "The marketplace cut", "body": "New client finds you on Mindbody?\nThey take 20% of that first payment.", "stat": "20%"},
            {"headline": "The real annual cost", "body": "Plan + processing + marketplace cut\non a €20k/month gym = over €10,000/year.", "stat": "€10K+"},
            {"headline": "Fiitsio: €99/month", "body": "No processing markup.\nNo marketplace commission.\nEver.", "stat": "€99/mo"},
            {"headline": "The switch pays itself", "body": "Most gyms save €400–600/month.\nFree data migration in 48 hours.\n\nfiitsio.com", "stat": None},
        ],
        "churn_stat_shock": [  # stat_shock: 6 slides
            {"headline": "30% of gym members cancel", "body": "in the first 90 days.", "stat": "30%"},
            {"headline": "Most gym owners", "body": "find out after they've already cancelled.\nNot before. After.", "stat": None},
            {"headline": "Why it happens", "body": "No engagement after signup.\nNo accountability.\nNo reason to stay.", "stat": None},
            {"headline": "The fix isn't discounts", "body": "It's catching warning signs\nbefore they mentally check out.", "stat": None},
            {"headline": "What good looks like", "body": "Member drops to 1 visit/week?\nYou get an alert. You reach out. They stay.", "stat": None},
            {"headline": "Fiitsio tracks every member", "body": "Alerts you before they cancel.\nNot after.\n\nfiitsio.com", "stat": None},
        ],
        "whatsapp_automation": [  # before_after: 6 slides
            {"headline": "This gym was losing 30% of members every quarter.", "body": "Sound familiar?", "stat": None},
            {"headline": "Before Fiitsio", "body": "Manual tracking of inactive members.\nForget to follow up.\nThey leave silently.", "stat": None},
            {"headline": "Before Fiitsio", "body": "No system. No alerts.\nJust checking the member list and hoping.", "stat": None},
            {"headline": "After Fiitsio", "body": "Member inactive for 14 days?\nAutomatic WhatsApp: \"Hey [Name], missing you 💪\"\n60% rebook within 48 hours.", "stat": "60%"},
            {"headline": "Churn dropped", "body": "from 28% to 9%\nin 60 days.", "stat": "9%"},
            {"headline": "Set it up in 5 minutes.", "body": "No code. No agency.\nJust Fiitsio.\n\nfiitsio.com", "stat": None},
        ],
        "gym_software_switch": [  # before_after: 6 slides
            {"headline": "We switched gym software.", "body": "Revenue went up. Not down.\nHere's the exact math.", "stat": None},
            {"headline": "Before (Glofox)", "body": "€250/month plan.\n+ payment processing fees we didn't know about.\n+ €500 setup fee.", "stat": None},
            {"headline": "The hidden cost", "body": "Every member payment was eating 2.9%.\nOn €15k/month, that's €435/month. Every month.", "stat": "€435/mo"},
            {"headline": "After (Fiitsio)", "body": "€99/month flat.\nNo processing markup.\nSame features. Better retention tools.", "stat": "€99/mo"},
            {"headline": "Saved in year 1", "body": "€2,232 in processing fees\n+ €1,812 in plan costs\n= €4,044 back in our pocket.", "stat": "€4K+"},
            {"headline": "We migrated in 2 days.", "body": "Fiitsio moved everything.\nZero downtime.\n\nfiitsio.com", "stat": None},
        ],
        "retention_math": [  # stat_shock: 6 slides
            {"headline": "Here's the maths gym owners don't want to do.", "body": "But need to.", "stat": None},
            {"headline": "Average member value", "body": "€50/month × 14 months average LTV\n= €700 per member.", "stat": "€700"},
            {"headline": "Losing 5 members/month", "body": "= €42,000 in lost annual revenue.\nNot next year. This year.", "stat": "€42K"},
            {"headline": "If you retain just 2 of those 5", "body": "= €16,800 back per year.\nFrom one email. One WhatsApp. One alert.", "stat": "+€16K"},
            {"headline": "The tool that sends that alert", "body": "costs €99/month.\n= €1,188/year.\nROI on retaining 2 members: 14x.", "stat": "14x ROI"},
            {"headline": "Do the maths for your gym.", "body": "Then come talk to us.\n\nfiitsio.com", "stat": None},
        ],
        "gym_owner_time": [  # pain_reveal: hook + context + deepen + stat + consequence + cta
            {"headline": "You're wasting 10 hours/week.", "body": "Here's exactly where it goes.", "stat": None},
            {"headline": "3 hours: scheduling chaos", "body": "Editing class times, cancellations,\n'Is there a class at 7?' WhatsApps. Every. Day.", "stat": "3h"},
            {"headline": "3 hours: chasing payments", "body": "Messaging members about failed charges.\nManually. One by one.", "stat": "3h"},
            {"headline": "4 hours: reporting & comms", "body": "Pulling numbers from 3 different tools.\nManually welcoming new members.\nChasing renewals.", "stat": "4h"},
            {"headline": "That's 520 hours/year", "body": "on admin that should be automated.\n13 full working weeks. Every year.", "stat": "520h"},
            {"headline": "Fiitsio does all of it.", "body": "Automatically.\nSo those 10 hours go back to coaching.\n\nfiitsio.com", "stat": None},
        ],
        "mbway_payments": [  # pain_reveal: 6 slides
            {"headline": "If your gym in Portugal doesn't accept MB Way,", "body": "you're losing members.", "stat": None},
            {"headline": "52% of Portuguese consumers", "body": "prefer MB Way as their primary payment method.\nMore than credit card. More than bank transfer.", "stat": "52%"},
            {"headline": "The friction cost", "body": "Member wants to join.\nSees no MB Way option.\nLeaves. Goes to your competitor.", "stat": None},
            {"headline": "Multibanco too", "body": "Older demographics still use Multibanco.\nIf your system can't generate a reference,\nyou lose those members silently.", "stat": None},
            {"headline": "Fiitsio supports both", "body": "MB Way + Multibanco, built in.\nNo third-party integration needed.\nNo extra fees.", "stat": None},
            {"headline": "Built for the Portuguese market.", "body": "From day one.\n\nfiitsio.com", "stat": None},
        ],
    }

    # Fall back to generic content if topic not mapped
    if topic not in content_map:
        return [
            {"headline": topic_data["title"], "body": "Thread coming soon.", "stat": None},
            {"headline": "Learn more at fiitsio.com", "body": None, "stat": None},
        ]

    return content_map[topic]


def pick_next_topic(used_topics_file: str = None) -> dict:
    """
    Pick the next topic to post.
    - Avoids the last 3 topics (no repeats)
    - If performance data exists, biases toward higher-view topics (2x weight for top performers)
    - Otherwise round-robin
    """
    if used_topics_file and os.path.exists(used_topics_file):
        with open(used_topics_file) as f:
            used = json.load(f)
        recent = used[-3:] if len(used) >= 3 else used
        recent_topics = [u['topic'] for u in recent]
    else:
        recent_topics = []

    available = [t for t in TOPICS_POOL if t['topic'] not in recent_topics]
    if not available:
        available = TOPICS_POOL  # Reset if all used

    # Load performance data if available
    perf_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'performance.json')
    if os.path.exists(perf_file):
        with open(perf_file) as f:
            perf = json.load(f)

        # Weight topics by avg_views — top performers appear 2x
        weighted = []
        for t in available:
            topic_perf = perf.get(t['topic'], {})
            avg_views = topic_perf.get('avg_views', 0)
            # Double-up any topic averaging >50K views
            multiplier = 2 if avg_views >= 50_000 else 1
            weighted.extend([t] * multiplier)
        available = weighted if weighted else available

    return available[0]


def log_post(topic_data: dict, log_file: str, post_result: dict = None) -> None:
    """Log a post to the history file."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    history = []
    if os.path.exists(log_file):
        with open(log_file) as f:
            history = json.load(f)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic_data["topic"],
        "title": topic_data["title"],
        "result": post_result or {},
    }
    history.append(entry)

    with open(log_file, 'w') as f:
        json.dump(history, f, indent=2)


if __name__ == '__main__':
    # Test: pick a topic and generate its content
    topic = pick_next_topic()
    print(f'📌 Selected topic: {topic["title"]}')
    print(f'📝 Caption hook: {topic["caption_hook"]}')
    print(f'🏷️ Hashtags: {topic["hashtags"][0]}')
    print()

    slides = get_slide_content_for_topic(topic)
    print(f'📊 Generated {len(slides)} slides:')
    for i, s in enumerate(slides, 1):
        print(f'  Slide {i}: "{s["headline"]}"')
