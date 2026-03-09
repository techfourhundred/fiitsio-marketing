# 🚀 Setup Guide — Activate the Content Engine

The engine is built and tested. You need 3 things to go live:

## Step 1: OpenAI API Key (for image generation upgrade)
Currently slides use gradient + text (no API needed).
For AI-generated gym backgrounds later: add OPENAI_API_KEY to OpenClaw config.

## Step 2: Postiz Account
1. Sign up at **postiz.com** (the affiliate link in the article)
2. Connect your accounts: TikTok, Instagram, X
3. Go to Settings → Developers → Public API → copy your API key

## Step 3: Add secrets to OpenClaw

Tell me (FiitsioBot) the following and I'll add them to the config:

```
POSTIZ_API_KEY = your-postiz-api-key
POSTIZ_TIKTOK_ID = (run: python3 scripts/postiz_poster.py --list-integrations)
POSTIZ_INSTAGRAM_ID = (from the same list)
POSTIZ_X_ID = (from the same list)
```

## Step 4: Test a real post (dry run first)

```bash
cd /home/kevin/fiitsio-marketing
POSTIZ_API_KEY=xxx POSTIZ_TIKTOK_ID=yyy python3 scripts/run_daily.py --dry-run
```

## Step 5: Schedule daily automation

Once confirmed working, I'll add a daily cron job:
- Posts at 7:00 AM UTC (8:00 AM Portugal time)
- Cycles through 8 pre-built content topics
- Logs every post to `/home/kevin/fiitsio-marketing/logs/post_history.json`
- Notifies you on Telegram when content goes out

## What runs automatically (once activated)

| Time | Action |
|------|--------|
| 07:00 UTC daily | Generate slides → upload → schedule TikTok + IG + X |
| After posting | Log entry + Telegram notification to Kevin |
| Weekly | Review performance from Postiz analytics |

## What Kevin still does (approves/customizes)

- Pick music for TikToks (Postiz handles this via autoAddMusic)
- Approve new topic additions to the pool
- Record occasional "talking head" videos (pure authenticity, can't be automated)
- Respond to comments (relationship building)

---

The system handles the grind. Kevin handles the soul.
