import uuid
import json
import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models.entities import IdempotencyRecord

logger = logging.getLogger("payrecover.idempotency")


class IdempotencyService:
    """
    Manages Idempotency-Key guarantees for state-changing recovery operations.
    Prevents duplicate payment links, double executions, duplicate messages.
    """

    @classmethod
    def get(cls, db: Session, key: str) -> Optional[IdempotencyRecord]:
        """Fetch previously recorded execution by idempotency key."""
        if not key or not key.strip():
            return None
        return db.query(IdempotencyRecord).filter(IdempotencyRecord.key == key.strip()).first()

    @classmethod
    def save(
        cls,
        db: Session,
        key: str,
        recovery_case_id: Optional[str],
        action_type: str,
        status_code: int,
        result: Any
    ) -> IdempotencyRecord:
        """Store execution output mapped to idempotency key."""
        if not key or not key.strip():
            return None

        result_str = json.dumps(result, default=str) if not isinstance(result, str) else result
        record = IdempotencyRecord(
            id=f"idem_{uuid.uuid4().hex[:12]}",
            key=key.strip(),
            recovery_case_id=recovery_case_id,
            action_type=action_type,
            status_code=status_code,
            result_json=result_str
        )
        db.add(record)
        try:
            db.commit()
            db.refresh(record)
            logger.info(f"Recorded idempotency key: '{key}' for action '{action_type}'")
            return record
        except Exception as e:
            db.rollback()
            logger.warning(f"Could not persist idempotency record for key '{key}': {e}")
            return None
