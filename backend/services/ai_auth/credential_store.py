"""SQLAlchemy-backed credential store — Python port of ai-auth's CredentialStore interface."""
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from backend.models.ai_credential import AiCredential


@dataclass
class StoredRecord:
    payload: str
    meta: Dict[str, Any]


class SqlAlchemyCredentialStore:
    """CredentialStore backed by the ai_credentials table.
    
    Scoped to an (organization_id, user_id) pair. When user_id is None,
    credentials are organization-level. When both are set, it's a user
    override within that org.
    """

    def __init__(self, db: Session, *, organization_id: Optional[int] = None, user_id: Optional[int] = None):
        self._db = db
        self._org_id = organization_id
        self._user_id = user_id

    def _query(self, key: str):
        q = self._db.query(AiCredential).filter(AiCredential.credential_key == key)
        if self._org_id is not None:
            q = q.filter(AiCredential.organization_id == self._org_id)
        else:
            q = q.filter(AiCredential.organization_id.is_(None))
        if self._user_id is not None:
            q = q.filter(AiCredential.user_id == self._user_id)
        else:
            q = q.filter(AiCredential.user_id.is_(None))
        return q

    async def read(self, key: str) -> Optional[StoredRecord]:
        row = self._query(key).first()
        if not row:
            return None
        try:
            meta = json.loads(row.meta_json) if row.meta_json else {}
        except Exception:
            meta = {}
        return StoredRecord(payload=row.encrypted_payload, meta=meta)

    async def write(self, key: str, record: StoredRecord) -> None:
        row = self._query(key).first()
        meta_str = json.dumps(record.meta)
        if row:
            row.encrypted_payload = record.payload
            row.meta_json = meta_str
        else:
            row = AiCredential(
                organization_id=self._org_id,
                user_id=self._user_id,
                credential_key=key,
                encrypted_payload=record.payload,
                meta_json=meta_str,
            )
            self._db.add(row)
        self._db.commit()

    async def delete(self, key: str) -> None:
        self._query(key).delete()
        self._db.commit()
