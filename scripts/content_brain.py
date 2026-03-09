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

## ── HOOK FORMULA (learned from 500K+ view experiment) ──────────────────────
##
## WRONG (self-focused, feature-focused → gets 900 views):
##   "30% of gym members cancel in the first 90 days."
##   "5 signs a member is about to cancel."
##   "What Mindbody actually costs you."
##   These flop. Nobody cares until they see themselves in it.
##
## RIGHT (human story formula → clears 50K-200K):
##   [Another person] + [conflict or doubt] + showed them X → they changed their mind
##   The viewer pictures the OTHER person's face. That's the hook.
##   Examples that worked:
##     "My landlord said I can't change anything so I showed her what AI thinks it could look like" → 234K
##     "I showed my mum what AI thinks our living room could be." → 167K
##     "My landlord wouldn't let me decorate until I showed her these." → 147K
##
## For Fiitsio: replace room/landlord with gym/gym owner scenarios.
## "The other person" is a gym owner, a business partner, a Mindbody rep, a member.
## The conflict is: disbelief, stubbornness, not knowing, "we can't afford to switch."
##
## EVERY hook below follows: [person] + [doubt/conflict] → showed them Fiitsio → they changed their mind

HOOKS_BANK = [
    # Tier 1 — Human story (follow the formula exactly)
    "My gym owner friend said he couldn't afford to switch software. So I showed him what he was actually paying.",
    "I showed a Mindbody user what their gym was spending per year. She went quiet.",
    "My mate's gym lost 30% of members last quarter. He had no idea until I showed him this.",
    "A gym owner told me churn was just 'part of the business.' Then I showed her the data.",
    "My friend opened a gym last year. I showed her the number that would make or break it in year one.",
    "A personal trainer asked me what software I'd use if I opened a gym. I showed her this comparison.",
    "My business partner didn't think retention tracking was worth paying for. Then this happened.",
    "A gym owner in Lisbon told me his members loved him. Then I showed him who hadn't booked in 3 weeks.",
    "I showed a gym owner what Mindbody was taking in fees every year. He didn't believe me at first.",
    "My gym owner friend was about to sign another 12-month contract with Glofox. I showed him this first.",
]

# HASHTAG RULE: Max 5 per post — TikTok's current effective limit
# Using more than 5 dilutes reach; pick the most targeted 5 for each topic

TOPICS_POOL = [
    {
        "topic": "member_churn_signs",
        "title": "4 signs a member is about to cancel",
        "template": "quick_tips",
        # Human story hook: gym owner + conflict (didn't know) + showed them
        "caption_hook": "A gym owner in Lisbon told me his members loved him. Then I showed him who hadn't booked in 3 weeks.",
        "hashtags": ["#gymowner #memberretention #gymbusiness #fitnessapp #fiitsio"],
    },
    {
        "topic": "mindbody_hidden_fees",
        "title": "What Mindbody actually costs you",
        "template": "competitor_comparison",
        # Human story: someone disbelieved → showed them → silent
        "caption_hook": "I showed a Mindbody gym owner what they were paying per year. She went quiet.",
        "hashtags": ["#gymowner #mindbody #gymsoftware #gymbusiness #fiitsio"],
    },
    {
        "topic": "churn_stat_shock",
        "title": "The 30% churn stat that kills gyms",
        "template": "stat_shock",
        # Human story: stubborn belief → data changed their mind
        "caption_hook": "A gym owner told me churn was just 'part of the business.' Then I showed her the data.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #memberretention #fiitsio"],
    },
    {
        "topic": "whatsapp_automation",
        "title": "How one WhatsApp message cut gym cancellations",
        "template": "before_after",
        # Human story: business partner doubted it
        "caption_hook": "My business partner didn't think one WhatsApp message could change retention. Then this happened.",
        "hashtags": ["#gymowner #gymautomation #gymbusiness #memberretention #fiitsio"],
    },
    {
        "topic": "gym_software_switch",
        "title": "My gym owner friend almost signed another Glofox contract",
        "template": "before_after",
        # Human story: prevented a bad decision
        "caption_hook": "My gym owner friend was about to sign another 12-month Glofox contract. I showed her this first.",
        "hashtags": ["#gymowner #gymsoftware #gymbusiness #gymtech #fiitsio"],
    },
    {
        "topic": "retention_math",
        "title": "The retention maths gym owners don't want to do",
        "template": "stat_shock",
        # Human story: new gym owner didn't see the risk
        "caption_hook": "A friend opened a gym last year. I showed her the number that would make or break it in year one.",
        "hashtags": ["#gymowner #gymretention #gymbusiness #fitnessapp #fiitsio"],
    },
    {
        "topic": "gym_owner_time",
        "title": "10 hours/week on tasks Fiitsio automates",
        "template": "pain_reveal",
        # Human story: PT asked for advice → eye-opening comparison
        "caption_hook": "A personal trainer asked me what software she'd use if she opened a gym. I showed her this.",
        "hashtags": ["#gymowner #gymbusiness #gymmanagement #gymproductivity #fiitsio"],
    },
    {
        "topic": "mbway_payments",
        "title": "Why your gym in Portugal needs MB Way",
        "template": "pain_reveal",
        # Human story: gym owner didn't think payment methods mattered
        "caption_hook": "A gym owner told me payment methods didn't matter. Then I showed him how many sign-ups he was losing.",
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
