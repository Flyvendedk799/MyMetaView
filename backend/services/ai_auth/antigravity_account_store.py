"""Antigravity subscription credential management — mirrors ClaudeAccountStore for Gemini/AGY."""
import time
from dataclasses import dataclass
from typing import Optional

from backend.services.ai_auth.secret_box import SecretBox
from backend.services.ai_auth.credential_store import StoredRecord
from backend.services.ai_auth.antigravity_oauth import refresh_antigravity_token, AntigravityLoginError

EXPIRY_BUFFER_MS = 5 * 60 * 1000
SECRET_LABEL = 'ai-auth-antigravity-oauth'


@dataclass
class AntigravityAccountStatus:
    connected: bool
    email: Optional[str]
    expires_at: Optional[int]
    expired: bool
    project_id: Optional[str]


DISCONNECTED = AntigravityAccountStatus(
    connected=False, email=None, expires_at=None, expired=False, project_id=None
)


class AntigravityAccountStore:
    def __init__(self, store, secret: str, namespace: str = '', secret_label: str = SECRET_LABEL):
        self._box = SecretBox(secret, secret_label)
        self._store = store
        self._prefix = f'{namespace}:Antigravity:' if namespace else 'Antigravity:'

    def _key(self, account_id: str) -> str:
        return f'{self._prefix}{account_id}'

    async def save(self, account_id: str, identity, project_id: Optional[str] = None) -> None:
        existing = await self._store.read(self._key(account_id))
        kept_project = project_id if project_id is not None else (
            existing.meta.get('projectId') if existing else None
        )

        payload = self._box.seal_json({
            'accessToken': identity.access_token,
            'refreshToken': identity.refresh_token,
        })
        await self._store.write(self._key(account_id), StoredRecord(
            payload=payload,
            meta={
                'email': identity.email,
                'expiresAt': round(identity.expires_at),
                'projectId': kept_project,
            },
        ))

    async def set_project_id(self, account_id: str, project_id: Optional[str]) -> None:
        record = await self._store.read(self._key(account_id))
        if not record:
            return
        record.meta['projectId'] = project_id.strip() if project_id else None
        await self._store.write(self._key(account_id), record)

    async def forget(self, account_id: str) -> None:
        await self._store.delete(self._key(account_id))

    async def status(self, account_id: str) -> AntigravityAccountStatus:
        record = await self._store.read(self._key(account_id))
        if not record:
            return DISCONNECTED

        payload = self._box.open_json(record.payload)
        if not payload or not isinstance(payload.get('accessToken'), str):
            return DISCONNECTED

        expires_at = int(record.meta.get('expiresAt', 0))
        now_ms = int(time.time() * 1000)
        return AntigravityAccountStatus(
            connected=True,
            email=record.meta.get('email') if isinstance(record.meta.get('email'), str) else None,
            expires_at=expires_at,
            expired=expires_at - EXPIRY_BUFFER_MS <= now_ms,
            project_id=record.meta.get('projectId') if isinstance(record.meta.get('projectId'), str) else None,
        )

    async def token(self, account_id: str) -> str:
        """Get a usable access token, refreshing if expired."""
        record = await self._store.read(self._key(account_id))
        if not record:
            raise AntigravityLoginError('This account has no Antigravity/Gemini subscription connected.', restart=True)

        payload = self._box.open_json(record.payload)
        if not payload or not isinstance(payload.get('accessToken'), str):
            raise AntigravityLoginError(
                'The stored Antigravity credential could not be read. Connect the subscription again.',
                restart=True,
            )

        expires_at = int(record.meta.get('expiresAt', 0))
        now_ms = int(time.time() * 1000)
        if expires_at - EXPIRY_BUFFER_MS > now_ms:
            return payload['accessToken']

        refresh_tok = payload.get('refreshToken')
        if not refresh_tok:
            raise AntigravityLoginError(
                'The Antigravity subscription has expired and cannot be refreshed. Connect it again.',
                restart=True,
            )

        is_dogfood = record.meta.get('isDogfood', False)
        refreshed = await refresh_antigravity_token(
            refresh_tok, is_dogfood=bool(is_dogfood)
        )
        await self.save(account_id, refreshed)
        return refreshed.access_token
