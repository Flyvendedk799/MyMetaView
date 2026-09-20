"""Encrypted API key management — Python port of ai-auth's ApiKeyStore."""
import os
from dataclasses import dataclass
from typing import Optional, Dict

from backend.services.ai_auth.secret_box import SecretBox, mask_secret
from backend.services.ai_auth.credential_store import StoredRecord

SECRET_LABEL = 'ai-auth-api-keys'

DEFAULT_ENV_NAMES = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'gemini': 'GEMINI_API_KEY',
}


@dataclass
class ResolvedKey:
    key: Optional[str]
    source: str  # 'stored', 'environment', 'none'
    ready: bool
    hint: Optional[str] = None


class ApiKeyStore:
    def __init__(self, store, secret: str, namespace: str = '', secret_label: str = SECRET_LABEL):
        self._box = SecretBox(secret, secret_label)
        self._store = store
        self._prefix = f'{namespace}:key:' if namespace else 'key:'

    def _store_key(self, wire: str) -> str:
        return f'{self._prefix}{wire}'

    async def set(self, wire: str, key: Optional[str]) -> None:
        """Store a key, or clear it by passing None or empty string."""
        trimmed = (key or '').strip()
        if not trimmed:
            await self._store.delete(self._store_key(wire))
            return
        await self._store.write(self._store_key(wire), StoredRecord(
            payload=self._box.seal(trimmed),
            meta={'hint': mask_secret(trimmed)},
        ))

    async def stored(self, wire: str) -> Optional[str]:
        """The stored key in the clear. For code about to make a call only."""
        record = await self._store.read(self._store_key(wire))
        if not record:
            return None
        return self._box.open(record.payload)

    async def hint(self, wire: str) -> Optional[str]:
        """Masked hint, safe to send to browser."""
        record = await self._store.read(self._store_key(wire))
        if record and isinstance(record.meta.get('hint'), str):
            return record.meta['hint']
        env_name = DEFAULT_ENV_NAMES.get(wire)
        if env_name:
            from_env = os.environ.get(env_name)
            if from_env:
                return mask_secret(from_env)
        return None

    async def resolve(self, wire: str) -> ResolvedKey:
        """Resolve key with fallback to environment."""
        from_store = await self.stored(wire)
        if from_store:
            return ResolvedKey(key=from_store, source='stored', ready=True, hint=mask_secret(from_store))

        env_name = DEFAULT_ENV_NAMES.get(wire)
        if env_name:
            from_env = (os.environ.get(env_name) or '').strip()
            if from_env:
                return ResolvedKey(key=from_env, source='environment', ready=True, hint=mask_secret(from_env))

        return ResolvedKey(key=None, source='none', ready=False)

    async def list_hints(self) -> Dict[str, Optional[str]]:
        """Get masked hints for all providers."""
        result = {}
        for wire in DEFAULT_ENV_NAMES:
            result[wire] = await self.hint(wire)
        return result
