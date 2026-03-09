# TikTok Direct API Setup (Free — No Postiz)

One-time setup. Takes ~10 minutes. Never pay for a scheduler again.

---

## How it works

Your server (fiitsio.com) serves the slides publicly.
TikTok's API pulls them directly.
Posts land in your TikTok drafts.
You add a trending sound and publish (~60 seconds).

```
[Server generates slides]
         ↓
[nginx serves at https://fiitsio.com/tiktok-slides/SESSION/slide_01.jpg]
         ↓
[TikTok API pulls all 6 images]
         ↓
[Draft created in your TikTok app]
         ↓
[You add music → publish]
```

Cost: $0/month forever.

---

## Step 1: Register a TikTok Developer App (free)

1. Go to https://developers.tiktok.com
2. Log in with your TikTok account
3. Click **"Create app"**
4. Fill in:
   - App name: `Fiitsio Content`
   - App description: `Personal content posting automation`
   - Category: `Entertainment`
5. After creation, click **"Add products"** → add **Content Posting API**
6. Enable **"Direct Post"** in the Content Posting API settings
7. Under **Login Kit**, add redirect URI:
   ```
   https://fiitsio.com/tiktok-callback
   ```
8. Copy your **Client Key** and **Client Secret** from the app settings

---

## Step 2: Save credentials on the server

```bash
mkdir -p /home/kevin/fiitsio-marketing/config
cat > /home/kevin/fiitsio-marketing/config/tiktok_client.json << 'EOF'
{
  "client_key": "YOUR_CLIENT_KEY_HERE",
  "client_secret": "YOUR_CLIENT_SECRET_HERE"
}
EOF
chmod 600 /home/kevin/fiitsio-marketing/config/tiktok_client.json
```

---

## Step 3: Run the auth (one-time)

```bash
cd /home/kevin/fiitsio-marketing
python3 scripts/tiktok_auth.py
```

This will:
- Open TikTok in your browser
- Ask you to approve the `video.publish` scope
- Redirect to `https://fiitsio.com/tiktok-callback`
- Save tokens to `config/tiktok_tokens.json`

Tokens are refreshed automatically. You'll never need to re-auth unless
you revoke the app in TikTok's settings.

---

## Step 4: Test the connection

```bash
cd /home/kevin/fiitsio-marketing
python3 scripts/tiktok_direct.py --test
```

Expected output:
```
✅ Token valid. Open ID: 7xxxxxxxxxx
✅ Creator: @kvnramos
   Privacy options: ['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY']
```

---

## Step 5: Run your first post (dry run first)

```bash
python3 scripts/run_daily.py --dry-run
```

Then live:
```bash
python3 scripts/run_daily.py
```

---

## Step 6: Activate daily automation

Tell FiitsioBot:
> "Activate the daily TikTok cron at 07:00 UTC"

I'll schedule it automatically and message you on Telegram after each post.

---

## Note on TikTok app audit

Unaudited apps can only post to **private accounts** or as **SELF_ONLY** drafts.
Since we use `SELF_ONLY` (drafts) anyway, this is fine for our workflow.

When you want to test public posting, submit for audit at:
https://developers.tiktok.com/application/content-posting-api

Audit is free and takes ~1-2 weeks. Not required for the draft workflow.

---

## Troubleshooting

**"No TikTok tokens found"**
→ Run `python3 scripts/tiktok_auth.py` first

**"Token refresh failed"**
→ Check `config/tiktok_client.json` has correct credentials
→ Or re-run `python3 scripts/tiktok_auth.py`

**Images not loading in TikTok**
→ Test: `curl -I https://fiitsio.com/tiktok-slides/TEST/`
→ Make sure nginx is running: `systemctl status nginx`

**"unaudited_client_can_only_post_to_private_accounts"**
→ This is fine — we post as SELF_ONLY (drafts) anyway
→ Submit for audit if you want public posting
