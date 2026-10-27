"""Lost-device cases and their state machine.

    open ──> evidence_received ──> recovered ──> closed
      │              │                              ^
      └──────────────┴──────────────────────────────┘   (closed is final)

`evidence_received` is set automatically when the first sighting is stored.
Everything is scoped to the device owner; someone else's case is a 404.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Case, Device, User
from app.routers.devices import get_owned
from app.schemas import CaseOut

router = APIRouter(tags=["cases"])

ACTIVE_STATES = ("open", "evidence_received")
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"recovered", "closed"},
    "evidence_received": {"recovered", "closed"},
    "recovered": {"closed"},
    "closed": set(),
}


def get_owned_case(db: Session, user: User, case_id: str) -> Case:
    """A case is visible only to the owner of its device (404 otherwise)."""
    case = db.scalar(
        select(Case)
        .join(Device, Device.id == Case.device_id)
        .where(Case.id == case_id, Device.owner_id == user.id)
    )
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def _transition(db: Session, case: Case, target: str) -> Case:
    if target not in ALLOWED_TRANSITIONS[case.state]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot move a case from {case.state} to {target}"
        )
    case.state = target
    if target == "closed":
        case.closed_at = datetime.now(timezone.utc)
    db.commit()
    return case


@router.post(
    "/devices/{device_id}/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED
)
def open_case(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Case:
    device = get_owned(db, user, device_id)
    if device.status != "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "Verify ownership before opening a case")
    if db.scalar(
        select(Case.id).where(Case.device_id == device.id, Case.state.in_(ACTIVE_STATES))
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "A case is already open for this device")
    case = Case(device_id=device.id, opened_by=user.id)
    db.add(case)
    try:
        db.commit()
    except IntegrityError:  # two simultaneous requests; the partial unique index caught it
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A case is already open for this device")
    return case


@router.get("/cases", response_model=list[CaseOut])
def list_my_cases(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Case]:
    return list(
        db.scalars(
            select(Case)
            .join(Device, Device.id == Case.device_id)
            .where(Device.owner_id == user.id)
            .order_by(Case.opened_at.desc())
        )
    )


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Case:
    return get_owned_case(db, user, case_id)


@router.post("/cases/{case_id}/recovered", response_model=CaseOut)
def mark_recovered(
    case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Case:
    return _transition(db, get_owned_case(db, user, case_id), "recovered")


@router.post("/cases/{case_id}/close", response_model=CaseOut)
def close_case(
    case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Case:
    return _transition(db, get_owned_case(db, user, case_id), "closed")
