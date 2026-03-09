#!/usr/bin/env python3
"""
Fiitsio Performance Tracker
Kevin tells me the view/like/follow counts for each post.
I log them and use them to rank hooks and topics for future content.

Usage:
  python3 track_performance.py --update
  python3 track_performance.py --report
  python3 track_performance.py --top-hooks
"""

import json
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR  = Path(__file__).parent.parent
LOG_FILE  = BASE_DIR / 'logs' / 'post_history.json'
PERF_FILE = BASE_DIR / 'logs' / 'performance.json'


def load_history() -> list:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE) as f:
        return json.load(f)


def load_perf() -> dict:
    if not PERF_FILE.exists():
        return {}
    with open(PERF_FILE) as f:
        return json.load(f)


def save_perf(data: dict) -> None:
    os.makedirs(PERF_FILE.parent, exist_ok=True)
    with open(PERF_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def update_performance(topic: str, views: int, likes: int, follows: int, notes: str = '') -> None:
    """Log performance data for a post."""
    perf = load_perf()

    if topic not in perf:
        perf[topic] = {'runs': [], 'avg_views': 0, 'avg_likes': 0, 'best_views': 0}

    run = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'views': views,
        'likes': likes,
        'follows': follows,
        'engagement_rate': round(likes / views * 100, 2) if views else 0,
        'notes': notes,
    }
    perf[topic]['runs'].append(run)

    # Recalculate averages
    all_views = [r['views'] for r in perf[topic]['runs']]
    all_likes = [r['likes'] for r in perf[topic]['runs']]
    perf[topic]['avg_views']  = int(sum(all_views) / len(all_views))
    perf[topic]['avg_likes']  = int(sum(all_likes) / len(all_likes))
    perf[topic]['best_views'] = max(all_views)
    perf[topic]['runs_count'] = len(perf[topic]['runs'])

    save_perf(perf)
    print(f'✅ Logged: {topic} — {views:,} views, {likes:,} likes, {follows:+} follows')


def rank_topics() -> list:
    """Rank topics by average views (descending)."""
    perf = load_perf()
    ranked = sorted(
        [{'topic': k, **v} for k, v in perf.items()],
        key=lambda x: x.get('avg_views', 0),
        reverse=True,
    )
    return ranked


def print_report() -> None:
    """Print a performance report."""
    perf = load_perf()
    history = load_history()

    print('\n' + '='*60)
    print('📊 FIITSIO CONTENT PERFORMANCE REPORT')
    print('='*60)

    if not perf:
        print('No performance data yet. Run --update to add stats.')
        return

    total_posts = sum(v.get('runs_count', 0) for v in perf.values())
    total_views = sum(
        sum(r['views'] for r in v['runs'])
        for v in perf.values()
    )

    print(f'\nTotal posts tracked: {total_posts}')
    print(f'Total views: {total_views:,}')
    print(f'\n{"Topic":<30} {"Avg Views":>10} {"Best":>8} {"Runs":>5}')
    print('-'*60)

    for topic, data in sorted(perf.items(), key=lambda x: x[1].get('avg_views', 0), reverse=True):
        print(f'{topic:<30} {data.get("avg_views", 0):>10,} {data.get("best_views", 0):>8,} {data.get("runs_count", 0):>5}')

    print('\n🏆 TOP 3 topics by avg views:')
    ranked = rank_topics()
    for i, t in enumerate(ranked[:3], 1):
        print(f'  {i}. {t["topic"]} — {t["avg_views"]:,} avg views')

    print('\n💀 WEAKEST topic:')
    if ranked:
        worst = ranked[-1]
        print(f'  {worst["topic"]} — {worst["avg_views"]:,} avg views → consider retiring or reworking')

    print('\n📈 RECOMMENDATION:')
    if ranked:
        best = ranked[0]
        print(f'  Post more of: {best["topic"]} (double down on winner)')
    print('='*60)


def top_hooks_from_data() -> list:
    """Identify which hooks/topics are killing it based on views."""
    ranked = rank_topics()
    return [(t['topic'], t.get('avg_views', 0)) for t in ranked if t.get('avg_views', 0) > 0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true', help='Log new performance data')
    parser.add_argument('--report', action='store_true', help='Print performance report')
    parser.add_argument('--top-hooks', action='store_true', help='List top hooks by performance')
    parser.add_argument('--topic', type=str)
    parser.add_argument('--views', type=int, default=0)
    parser.add_argument('--likes', type=int, default=0)
    parser.add_argument('--follows', type=int, default=0)
    parser.add_argument('--notes', type=str, default='')
    args = parser.parse_args()

    if args.update:
        if not args.topic:
            print('--topic required with --update')
        else:
            update_performance(args.topic, args.views, args.likes, args.follows, args.notes)
    elif args.report:
        print_report()
    elif args.top_hooks:
        hooks = top_hooks_from_data()
        if hooks:
            print('\n🎣 Top hooks by performance:')
            for topic, views in hooks:
                print(f'  {topic}: {views:,} avg views')
        else:
            print('No data yet.')
    else:
        parser.print_help()
