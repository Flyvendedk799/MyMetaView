"""Claude subscription credential management — Python port of ai-auth's ClaudeAccountStore."""
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from backend.services.ai_auth.secret_box import SecretBox
from backend.services.ai_auth.credential_store import StoredRecord
from backend.services.ai_auth.claude_oauth import refresh_claude_token, ClaudeLoginError

EXPIRY_BUFFER_MS = 5 * 60 * 1000
SECRET_LABEL = 'ai-auth-claude-oauth'


@dataclass
class ClaudeAccountStatus:
    connected: bool
    plan: Optional[str]
    expires_at: Optional[int]  # Unix ms
    expired: bool
    scopes: List[str]


@dataclass
class ClaudeIdentityInput:
    access_token: str
    refresh_token: Optional[str]
    expires_at: int
    scopes: List[str]
    subscription_type: Optional[str]


DISCONNECTED = ClaudeAccountStatus(
    connected=False, plan=None, expires_at=None, expired=False, scopes=[]
)


class ClaudeAccountStore:
    def __init__(self, store, secret: str, namespace: str = '', secret_label: str = SECRET_LABEL):
        self._box = SecretBox(secret, secret_label)
        self._store = store
        self._prefix = f'{namespace}:claude:' if namespace else 'claude:'

    def _key(self, account_id: str) -> str:
        return f'{self._prefix}{account_id}'

    async def save(self, account_id: str, identity: ClaudeIdentityInput) -> None:
        payload = self._box.seal_json({
            'accessToken': identity.access_token,
            'refreshToken': identity.refresh_token,
            'scopes': identity.scopes,
        })
        await self._store.write(self._key(account_id), StoredRecord(
            payload=payload,
            meta={
                'plan': identity.subscription_type,
                'expiresAt': round(identity.expires_at),
            },
        ))

    async def forget(self, account_id: str) -> None:
        await self._store.delete(self._key(account_id))

    async def status(self, account_id: str) -> ClaudeAccountStatus:
        record = await self._store.read(self._key(account_id))
        if not record:
            return DISCONNECTED

        payload = self._box.open_json(record.payload)
        if not payload or not isinstance(payload.get('accessToken'), str):
            return DISCONNECTED

        expires_at = int(record.meta.get('expiresAt', 0))
        now_ms = int(time.time() * 1000)
        return ClaudeAccountStatus(
            connected=True,
            plan=record.meta.get('plan') if isinstance(record.meta.get('plan'), str) else None,
            expires_at=expires_at,
            expired=expires_at - EXPIRY_BUFFER_MS <= now_ms,
            scopes=payload.get('scopes', []) if isinstance(payload.get('scopes'), list) else [],
        )

    async def token(self, account_id: str) -> str:
        """Get a usable access token, refreshing if expired."""
        record = await self._store.read(self._key(account_id))
        if not record:
            raise ClaudeLoginError('This account has no Claude subscription connected.', restart=True)

        payload = self._box.open_json(record.payload)
        if not payload or not isinstance(payload.get('accessToken'), str):
            raise ClaudeLoginError(
                'The stored Claude credential could not be read. Connect the subscription again.',
                restart=True,
            )

        expires_at = int(record.meta.get('expiresAt', 0))
        now_ms = int(time.time() * 1000)
        if expires_at - EXPIRY_BUFFER_MS > now_ms:
            return payload['accessToken']

        # Refresh needed
        refresh_tok = payload.get('refreshToken')
        if not refresh_tok:
            raise ClaudeLoginError(
                'The Claude subscription has expired and cannot be refreshed. Connect it again.',
                restart=True,
            )

        refreshed = await refresh_claude_token(refresh_tok)
        await self.save(account_id, ClaudeIdentityInput(
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token,
            expires_at=refreshed.expires_at,
            scopes=refreshed.scopes,
            subscription_type=refreshed.subscription_type,
        ))
        return refreshed.access_token
