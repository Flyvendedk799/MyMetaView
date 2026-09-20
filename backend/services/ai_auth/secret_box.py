"""AES-256-GCM encryption at rest — Python port of ai-auth's SecretBox.

Key derivation: sha256(label + ':' + secret).
Format: iv:tag:ciphertext, all in hex.
Returns None on decryption failure rather than throwing.
"""
import hashlib
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Any, Optional


class SecretBox:
    """AES-256-GCM sealing, keyed from a host secret and a label."""

    def __init__(self, secret: str, label: str):
        if not secret:
            raise ValueError('SecretBox needs a non-empty secret')
        if not label:
            raise ValueError('SecretBox needs a label, so two stores cannot share a key')
        self._key = hashlib.sha256(f'{label}:{secret}'.encode()).digest()

    def seal(self, plaintext: str) -> str:
        """Encrypt plaintext → 'iv_hex:tag_hex:ciphertext_hex'."""
        iv = os.urandom(12)
        aesgcm = AESGCM(self._key)
        # AESGCM.encrypt returns ciphertext + tag (last 16 bytes)
        ct_with_tag = aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)
        # Split: ciphertext is everything except last 16 bytes, tag is last 16
        ciphertext = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        return f'{iv.hex()}:{tag.hex()}:{ciphertext.hex()}'

    def open(self, sealed: str) -> Optional[str]:
        """Decrypt sealed string → plaintext, or None on any failure."""
        parts = sealed.split(':')
        if len(parts) != 3:
            return None
        try:
            iv = bytes.fromhex(parts[0])
            tag = bytes.fromhex(parts[1])
            ciphertext = bytes.fromhex(parts[2])
            aesgcm = AESGCM(self._key)
            # AESGCM.decrypt expects ciphertext + tag concatenated
            plaintext = aesgcm.decrypt(iv, ciphertext + tag, None)
            return plaintext.decode('utf-8')
        except Exception:
            return None

    def seal_json(self, value: Any) -> str:
        return self.seal(json.dumps(value))

    def open_json(self, sealed: str) -> Any:
        plain = self.open(sealed)
        if plain is None:
            return None
        try:
            return json.loads(plain)
        except Exception:
            return None


def mask_secret(secret: str) -> str:
    """Enough of a secret to recognise, never enough to use."""
    trimmed = secret.strip()
    if len(trimmed) <= 12:
        return '••••'
    return f'{trimmed[:7]}…{trimmed[-4:]}'
