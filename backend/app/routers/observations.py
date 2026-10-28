"""Sightings (observations) for a case.

In this version the only source is "simulated", so these endpoints work only
when DEMO_MODE=true. A real source (the BLE prototype) will need signed reports
from finder devices; that is not built, and nothing here pretends otherwise.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.evidence import Point, Verdict, evaluate
from app.models import Case, Observation, User
from app.routers.cases import ACTIVE_STATES, get_owned_case
from app.schemas import (
    ObservationIn,
    ObservationOut,
    SimulatedItemOut,
    SimulateIn,
    SimulationOut,
)
from app.simulator import scenario
from app.timeutil import aware

router = APIRouter(prefix="/cases/{case_id}/observations", tags=["observations"])

MAX_OBSERVATIONS_PER_CASE = 200


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "No observation source is configured"
        )


def _require_accepting(case: Case) -> None:
    if case.state not in ACTIVE_STATES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Case is not accepting evidence")


def _to_out(o: Observation, now: datetime) -> ObservationOut:
    return ObservationOut(
        id=o.id,
        source=o.source,
        observed_at=aware(o.observed_at),
        received_at=aware(o.received_at),
        lat=o.lat,
        lon=o.lon,
        accuracy_m=o.accuracy_m,
        validation_status=o.validation_status,
        flags=list(o.flags or []),
        age_seconds=max(0, int((now - aware(o.observed_at)).total_seconds())),
    )


def ingest(
    db: Session,
    case: Case,
    *,
    source: str,
    observed_at: datetime,
    lat: float,
    lon: float,
    accuracy_m: float,
    nonce: str,
    now: datetime,
) -> tuple[Observation | None, Verdict]:
    """Validate one sighting and store it unless it is rejected."""
    stored = list(db.scalars(select(Observation).where(Observation.case_id == case.id)))
    if len(stored) >= MAX_OBSERVATIONS_PER_CASE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Observation limit reached")
    if any(o.nonce == nonce for o in stored):  # replay of an already received report
        raise HTTPException(status.HTTP_409_CONFLICT, "Observation already received")

    verdict = evaluate(
        observed_at=observed_at,
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        existing=[Point(aware(o.observed_at), o.lat, o.lon) for o in stored],
        now=now,
    )
    if verdict.status == "rejected":
        return None, verdict

    obs = Observation(
        case_id=case.id,
        source=source,
        observed_at=observed_at,
        received_at=now,
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        nonce=nonce,
        validation_status=verdict.status,
        flags=list(verdict.flags),
    )
    db.add(obs)
    if case.state == "open":
        case.state = "evidence_received"
    try:
        db.commit()
    except IntegrityError:  # same nonce arrived twice at once; the unique constraint caught it
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Observation already received")
    return obs, verdict


@router.post("", response_model=ObservationOut, status_code=status.HTTP_201_CREATED)
def add_observation(
    case_id: str,
    body: ObservationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObservationOut:
    case = get_owned_case(db, user, case_id)
    _require_demo()
    _require_accepting(case)
    now = datetime.now(timezone.utc)
    obs, verdict = ingest(
        db,
        case,
        source=body.source,
        observed_at=body.observed_at.astimezone(timezone.utc),
        lat=body.lat,
        lon=body.lon,
        accuracy_m=body.accuracy_m,
        nonce=body.nonce,
        now=now,
    )
    if obs is None:
        raise HTTPException(
            422,
            {"message": "Observation rejected", "reason": verdict.reason},
        )
    return _to_out(obs, now)


@router.get("", response_model=list[ObservationOut])
def list_observations(
    case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ObservationOut]:
    case = get_owned_case(db, user, case_id)
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Observation)
        .where(Observation.case_id == case.id)
        .order_by(Observation.observed_at.desc())
    )
    return [_to_out(o, now) for o in rows]


@router.post("/simulate", response_model=SimulationOut)
def simulate(
    case_id: str,
    body: SimulateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationOut:
    """Feed a prepared synthetic scenario through the same validation as real input."""
    case = get_owned_case(db, user, case_id)
    _require_demo()
    _require_accepting(case)
    now = datetime.now(timezone.utc)
    results = []
    for item in scenario(body.scenario, now):
        _, verdict = ingest(db, case, source="simulated", now=now, **item)
        results.append(
            SimulatedItemOut(
                observed_at=item["observed_at"],
                status=verdict.status,
                flags=list(verdict.flags),
                reason=verdict.reason,
            )
        )
    audit.record(db, user.id, "demo_sightings_added", "case", case.id, body.scenario)
    return SimulationOut(scenario=body.scenario, results=results)
