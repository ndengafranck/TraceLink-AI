from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import AuditEvent, User
from app.schemas import AuditOut

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=list[AuditOut])
def my_activity(
    limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AuditEvent]:
    """The caller's own recent activity, newest first."""
    limit = max(1, min(limit, 200))
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.user_id == user.id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
    )
