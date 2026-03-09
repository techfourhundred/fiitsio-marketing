#!/usr/bin/env python3
"""
TikTok OAuth — one-time setup.
Run this once to get your access + refresh tokens. Never need to run again
(refresh is automatic in tiktok_direct.py).

Usage:
  python3 tiktok_auth.py

Prerequisites:
  1. Register app at https://developers.tiktok.com
  2. Add product: Content Posting API
  3. Set redirect URI to: https://fiitsio.com/tiktok-callback
  4. Copy your Client Key + Client Secret
  5. Set env vars:
       export TIKTOK_CLIENT_KEY=your_client_key
       export TIKTOK_CLIENT_SECRET=your_client_secret
  6. Run this script — it opens a browser + starts a local listener

Scopes needed: video.publish (for photo + video posts)
"""

import os
import sys
import json
import webbrowser
import secrets
import urllib.parse
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone

TOKEN_FILE = Path(__file__).parent.parent / 'config' / 'tiktok_tokens.json'
CALLBACK_PORT = 8765
REDIRECT_URI = 'https://fiitsio.com/tiktok-callback'


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Local server to catch the OAuth callback."""
    code = None
    state = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if 'code' in params:
            OAuthCallbackHandler.code = params['code'][0]
            OAuthCallbackHandler.state = params.get('state', [''])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html><body style="font-family:sans-serif;text-align:center;padding:60px">
                <h2>&#10003; TikTok auth complete!</h2>
                <p>You can close this tab. The terminal will finish automatically.</p>
                </body></html>
            ''')
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass  # Suppress request logs


def get_auth_url(client_key: str, state: str) -> str:
    params = {
        'client_key': client_key,
        'scope': 'video.publish',
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'state': state,
    }
    return 'https://www.tiktok.com/v2/auth/authorize/?' + urllib.parse.urlencode(params)


def exchange_code_for_token(code: str, client_key: str, client_secret: str) -> dict:
    resp = requests.post(
        'https://open.tiktokapis.com/v2/oauth/token/',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
        },
    )
    return resp.json()


def save_tokens(token_data: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tokens = {
        'access_token': token_data['access_token'],
        'refresh_token': token_data['refresh_token'],
        'open_id': token_data['open_id'],
        'scope': token_data.get('scope', ''),
        'expires_in': token_data.get('expires_in', 86400),
        'refresh_expires_in': token_data.get('refresh_expires_in', 31536000),
        'obtained_at': datetime.now(timezone.utc).isoformat(),
    }
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    print(f'✅ Tokens saved to {TOKEN_FILE}')


def main():
    client_key = os.environ.get('TIKTOK_CLIENT_KEY')
    client_secret = os.environ.get('TIKTOK_CLIENT_SECRET')

    if not client_key or not client_secret:
        print('❌ Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET first')
        print()
        print('Steps:')
        print('  1. Go to https://developers.tiktok.com')
        print('  2. Create an app → add "Content Posting API" product')
        print('  3. Set redirect URI to: https://fiitsio.com/tiktok-callback')
        print('  4. Copy Client Key + Secret')
        print('  5. Run:')
        print('       export TIKTOK_CLIENT_KEY=xxxx')
        print('       export TIKTOK_CLIENT_SECRET=xxxx')
        print('       python3 tiktok_auth.py')
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    auth_url = get_auth_url(client_key, state)

    print(f'🌐 Opening TikTok auth in your browser...')
    print(f'URL: {auth_url}')
    print()
    print('Waiting for callback on https://fiitsio.com/tiktok-callback')
    print('(proxied to local port 8765)')

    # Start local server to catch callback
    server = HTTPServer(('0.0.0.0', CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 120  # 2 min to complete auth

    webbrowser.open(auth_url)

    # Wait for callback
    while OAuthCallbackHandler.code is None:
        server.handle_request()

    code = OAuthCallbackHandler.code
    print(f'✅ Got auth code. Exchanging for tokens...')

    token_data = exchange_code_for_token(code, client_key, client_secret)

    if 'access_token' not in token_data:
        print(f'❌ Token exchange failed: {token_data}')
        sys.exit(1)

    save_tokens(token_data)
    print()
    print('🎉 Setup complete! TikTok is connected.')
    print('   Run run_daily.py to start posting.')


if __name__ == '__main__':
    main()
