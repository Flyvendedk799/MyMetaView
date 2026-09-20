"""Claude Code OAuth PKCE — Python port of ai-auth's claude/oauth.ts.

Constants read from Claude Code CLI binary. Public client, no secret.
"""
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import urlencode
import httpx


CLAUDE_OAUTH = {
    'authorize_url': 'https://platform.claude.com/oauth/authorize',
    'token_url': 'https://platform.claude.com/v1/oauth/token',
    'redirect_uri': 'https://platform.claude.com/oauth/code/callback',
    'client_id': '9d1c250a-e61b-44d9-88ed-5944d1962f5e',
    'scopes': [
        'user:file_upload',
        'user:inference',
        'user:mcp_servers',
        'user:profile',
        'user:sessions:claude_code',
    ],
}

# The identity block required for subscription tokens on Opus/Sonnet
CLAUDE_CODE_SYSTEM = "You are Claude Code, Anthropic's official CLI for Claude."

# Beta flags and version a real Claude Code session sends
CLAUDE_CODE_VERSION = '2.1.75'
CLAUDE_CODE_BETA = ','.join([
    'claude-code-20250219',
    'oauth-2025-04-20',
    'fine-grained-tool-streaming-2025-05-14',
    'interleaved-thinking-2025-05-14',
])


@dataclass
class LoginStart:
    url: str
    verifier: str
    state: str


@dataclass
class ExchangedIdentity:
    access_token: str
    refresh_token: Optional[str]
    expires_at: int  # Unix ms
    scopes: List[str]
    subscription_type: Optional[str]


class ClaudeLoginError(Exception):
    def __init__(self, message: str, restart: bool = False):
        super().__init__(message)
        self.restart = restart


def start_claude_login() -> LoginStart:
    """Start the Claude OAuth PKCE flow."""
    verifier = os.urandom(32).hex()  # base64url equivalent
    import base64
    verifier_b64 = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier_b64.encode()).digest()
    ).rstrip(b'=').decode()
    state = base64.urlsafe_b64encode(os.urandom(24)).rstrip(b'=').decode()

    params = {
        'code': 'true',
        'client_id': CLAUDE_OAUTH['client_id'],
        'response_type': 'code',
        'redirect_uri': CLAUDE_OAUTH['redirect_uri'],
        'scope': ' '.join(CLAUDE_OAUTH['scopes']),
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'state': state,
    }

    url = f"{CLAUDE_OAUTH['authorize_url']}?{urlencode(params)}"
    return LoginStart(url=url, verifier=verifier_b64, state=state)


def parse_pasted_code(raw: str):
    """Parse the code#state the user pastes back."""
    import re
    from urllib.parse import urlparse, parse_qs
    
    trimmed = re.sub(r'\s+', '', raw.strip())
    if not trimmed:
        return None

    if trimmed.startswith('http://') or trimmed.startswith('https://'):
        try:
            parsed = urlparse(trimmed)
            qs = parse_qs(parsed.query)
            code = qs.get('code', [None])[0]
            if not code:
                return None
            return {'code': code, 'state': qs.get('state', [None])[0]}
        except Exception:
            return None

    parts = trimmed.split('#', 1)
    code = parts[0]
    if not code:
        return None
    state = parts[1] if len(parts) > 1 and parts[1] else None
    return {'code': code, 'state': state}


def same_state(expected: str, actual: str) -> bool:
    """Constant-time state comparison."""
    return hmac.compare_digest(expected.encode(), actual.encode())


async def exchange_claude_code(
    code: str, state: str, verifier: str,
    now_ms: Optional[int] = None,
) -> ExchangedIdentity:
    """Trade the pasted code for tokens. Body is JSON, not form-encoded."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                CLAUDE_OAUTH['token_url'],
                json={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': CLAUDE_OAUTH['redirect_uri'],
                    'client_id': CLAUDE_OAUTH['client_id'],
                    'code_verifier': verifier,
                    'state': state,
                },
                headers={'content-type': 'application/json'},
                timeout=30.0,
            )
        except Exception as e:
            raise ClaudeLoginError(f'Could not reach Anthropic: {e}', restart=False)

    if response.status_code in (400, 401):
        raise ClaudeLoginError(
            'Anthropic rejected that code. It may have expired or already been used — start the login again.',
            restart=True,
        )
    if response.status_code >= 400:
        raise ClaudeLoginError(f'Anthropic returned HTTP {response.status_code}.', restart=False)

    try:
        body = response.json()
    except Exception:
        raise ClaudeLoginError('Anthropic returned no access token.', restart=True)

    access_token = body.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise ClaudeLoginError('Anthropic returned no access token.', restart=True)

    expires_in = body.get('expires_in', 3600)
    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        expires_in = 3600

    refresh_token = body.get('refresh_token')
    scope = body.get('scope', '')
    account = body.get('account', {})

    return ExchangedIdentity(
        access_token=access_token,
        refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else None,
        expires_at=now_ms + int(expires_in * 1000),
        scopes=scope.split() if isinstance(scope, str) else [],
        subscription_type=account.get('subscription_type') if isinstance(account, dict) else None,
    )


async def refresh_claude_token(
    refresh_token: str,
    now_ms: Optional[int] = None,
) -> ExchangedIdentity:
    """Refresh an expired Claude access token."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                CLAUDE_OAUTH['token_url'],
                json={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': CLAUDE_OAUTH['client_id'],
                },
                headers={'content-type': 'application/json'},
                timeout=30.0,
            )
        except Exception as e:
            raise ClaudeLoginError(f'Could not reach Anthropic: {e}', restart=False)

    if response.status_code >= 400:
        raise ClaudeLoginError(
            'Anthropic refused to refresh this token. Sign in again.',
            restart=True,
        )

    try:
        body = response.json()
    except Exception:
        raise ClaudeLoginError('Anthropic returned no access token on refresh.', restart=True)

    access_token = body.get('access_token')
    if not isinstance(access_token, str) or not access_token:
        raise ClaudeLoginError('Anthropic returned no access token on refresh.', restart=True)

    expires_in = body.get('expires_in', 3600)
    refresh_tok = body.get('refresh_token')
    scope = body.get('scope', '')
    account = body.get('account', {})

    return ExchangedIdentity(
        access_token=access_token,
        refresh_token=refresh_tok if isinstance(refresh_tok, str) and refresh_tok else refresh_token,
        expires_at=now_ms + int(expires_in * 1000),
        scopes=scope.split() if isinstance(scope, str) else [],
        subscription_type=account.get('subscription_type') if isinstance(account, dict) else None,
    )
