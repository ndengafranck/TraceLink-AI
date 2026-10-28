"""Audit trail: a short record of security-relevant actions.

Stores ids and labels only. It never stores passwords, ownership codes, IMEIs,
beacon secrets or coordinates, so the log cannot leak what the rest of the
system protects. Each call commits on its own, so a failed action (for example
a wrong password) is still recorded.
"""

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(
    db: Session,
    user_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(AuditEvent(user_id=user_id, action=action, target_type=target_type,
                      target_id=target_id, detail=detail))
    db.commit()
