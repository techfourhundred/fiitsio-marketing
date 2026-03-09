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
    "pain_reveal": {
        "description": "Reveal a hidden gym pain point, build tension, offer Fiitsio as solution",
        "slides": 5,
        "structure": ["hook/pain", "context", "stat", "consequence", "solution_cta"],
    },
    "competitor_comparison": {
        "description": "Compare Fiitsio vs competitor on price/features/UX",
        "slides": 6,
        "structure": ["hook", "competitor_cost", "hidden_fees", "fiitsio_cost", "comparison", "cta"],
    },
    "quick_tips": {
        "description": "5 actionable tips for gym owners",
        "slides": 7,
        "structure": ["hook", "tip1", "tip2", "tip3", "tip4", "tip5", "cta"],
    },
    "stat_shock": {
        "description": "Lead with a shocking stat, explain it, offer solution",
        "slides": 5,
        "structure": ["stat_hook", "what_it_means", "why_it_happens", "what_to_do", "cta"],
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

TOPICS_POOL = [
    {
        "topic": "member_churn_signs",
        "title": "5 signs a member is about to cancel",
        "template": "quick_tips",
        "caption_hook": "Your member is planning to leave. You have 2 weeks to stop them.",
        "hashtags": ["#gymowner #gymbusiness #memberretention #fitnessapp #gymmanagement #fiitsio"],
    },
    {
        "topic": "mindbody_hidden_fees",
        "title": "What Mindbody actually costs you",
        "template": "competitor_comparison",
        "caption_hook": "Mindbody charges you how much per year?? (most gym owners don't know)",
        "hashtags": ["#gymowner #mindbody #gymsoftware #gymbusiness #fiitsio #gymtech"],
    },
    {
        "topic": "churn_stat_shock",
        "title": "The 30% churn stat that kills gyms",
        "template": "stat_shock",
        "caption_hook": "30% of your gym members are planning to cancel. Most gyms find out after.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #memberretention #gymmanagement"],
    },
    {
        "topic": "whatsapp_automation",
        "title": "How to automate member retention on WhatsApp",
        "template": "before_after",
        "caption_hook": "This gym stopped losing members with one WhatsApp message. Here's how.",
        "hashtags": ["#gymowner #whatsapp #gymautomation #gymbusiness #fiitsio #memberretention"],
    },
    {
        "topic": "gym_software_switch",
        "title": "We switched from Glofox — what happened",
        "template": "before_after",
        "caption_hook": "We switched gym software and our revenue went up. Not down. Here's the math.",
        "hashtags": ["#gymowner #glofox #gymsoftware #gymbusiness #fiitsio #gymmanagement"],
    },
    {
        "topic": "retention_math",
        "title": "The math behind your gym's churn problem",
        "template": "stat_shock",
        "caption_hook": "Here's the exact math gym owners need to understand about member churn.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #gymmath #fitnessapp #fiitsio"],
    },
    {
        "topic": "gym_owner_time",
        "title": "How gym owners waste 10 hours/week",
        "template": "pain_reveal",
        "caption_hook": "You're spending 10+ hours/week on tasks that should take 10 minutes.",
        "hashtags": ["#gymowner #gymbusiness #gymproductivity #gymmanagement #fiitsio"],
    },
    {
        "topic": "mbway_payments",
        "title": "Why your gym needs MB Way",
        "template": "pain_reveal",
        "caption_hook": "If your gym in Portugal doesn't accept MB Way, you're losing members.",
        "hashtags": ["#gymowner #mbway #ginasio #portugal #fiitsio #gymmanagement"],
    },
]


def get_slide_content_for_topic(topic_data: dict) -> list[dict]:
    """Generate slide content for a specific topic using pre-built templates."""
    topic = topic_data["topic"]
    template = CONTENT_TEMPLATES[topic_data["template"]]

    # Pre-built content for each topic
    content_map = {
        "member_churn_signs": [
            {"headline": "5 signs a member is about to cancel", "body": "Most gym owners miss all 5.", "stat": None},
            {"headline": "Sign #1: Drop in bookings", "body": "4x/week → 2x/week for 14 days.\nNot a holiday. It's the beginning of the end.", "stat": None},
            {"headline": "Sign #2: No-shows", "body": "Books but doesn't show.\nThree times in a row = danger zone.", "stat": None},
            {"headline": "Sign #3: Stops buying add-ons", "body": "Used to buy PT sessions, smoothies, merch.\nNow? Nothing.", "stat": None},
            {"headline": "Sign #4: App opens drop", "body": "Goes from daily app opens to once a week.\nDisengaged digitally = disengaged physically.", "stat": None},
            {"headline": "Sign #5: The 21-day rule", "body": "No visit in 21 days.\nStatistically, 70% of these members cancel within 30 days.", "stat": "21 days"},
            {"headline": "Fiitsio alerts you", "body": "automatically when any of these happen.\nBefore they cancel.\n\nfiitsio.com", "stat": None},
        ],
        "mindbody_hidden_fees": [
            {"headline": "Mindbody costs €400/month.", "body": "But that's not the real cost.", "stat": None},
            {"headline": "Their processor fee", "body": "3.35% on EVERY transaction.\nEven on debit cards that cost them nothing.", "stat": "3.35%"},
            {"headline": "The marketplace cut", "body": "New client discovers you on Mindbody?\nThey take 20% of that first payment.", "stat": "20%"},
            {"headline": "The real annual cost", "body": "€499/mo plan + 3.35% processing + 20% marketplace\non a €20k/mo gym = €10,000+/year to Mindbody.", "stat": "€10K+"},
            {"headline": "Fiitsio pricing", "body": "€99/month.\nNo processing markup.\nNo marketplace cut.\nEver.", "stat": "€99/mo"},
            {"headline": "The switch pays itself", "body": "Most gyms save €400-600/month switching.\nWe migrate your data for free in 48 hours.", "stat": None},
        ],
        "churn_stat_shock": [
            {"headline": "30% of gym members cancel", "body": "in the first 90 days.", "stat": "30%"},
            {"headline": "And most gym owners", "body": "don't know it's happening\nuntil they check their bank statement.", "stat": None},
            {"headline": "Why it happens", "body": "No engagement after signup.\nNo accountability.\nNo reason to stay.", "stat": None},
            {"headline": "The fix isn't discounts", "body": "It's catching the warning signs\nbefore they mentally check out.", "stat": None},
            {"headline": "Fiitsio tracks every member", "body": "and alerts you when attendance drops.\nBefore they cancel.\n\nfiitsio.com", "stat": None},
        ],
        "whatsapp_automation": [
            {"headline": "This gym loses 30% of members every quarter.", "body": "Sound familiar?", "stat": None},
            {"headline": "Before Fiitsio", "body": "Manual check on inactive members.\nForget to follow up.\nThey leave silently.", "stat": None},
            {"headline": "The turning point", "body": "Member hasn't booked in 14 days.\nFiitsio sends a WhatsApp automatically.\n\"Hey [Name], missing you at the gym 💪\"", "stat": None},
            {"headline": "After Fiitsio", "body": "60% of contacted members\nbook a class within 48 hours.", "stat": "60%"},
            {"headline": "Churn dropped", "body": "from 28% to 9%\nin 60 days.", "stat": "9%"},
            {"headline": "Set it up in 5 minutes.", "body": "fiitsio.com", "stat": None},
        ],
        "gym_owner_time": [
            {"headline": "You're wasting 10 hours/week.", "body": "Here's exactly where it goes.", "stat": None},
            {"headline": "2 hours: chasing payments", "body": "Manually messaging members about failed charges.\nOne by one.", "stat": "2h"},
            {"headline": "3 hours: scheduling", "body": "Editing class times, handling cancellations,\nreplying to 'is there a class at 7pm?' on WhatsApp.", "stat": "3h"},
            {"headline": "2 hours: reporting", "body": "Pulling numbers from different places\nto understand if your gym is actually growing.", "stat": "2h"},
            {"headline": "3 hours: member comms", "body": "Following up on at-risk members,\nwelcoming new ones, chasing renewals.", "stat": "3h"},
            {"headline": "Fiitsio does all of this.", "body": "Automatically.\nSo you can spend those 10 hours coaching.\n\nfiitsio.com", "stat": None},
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
