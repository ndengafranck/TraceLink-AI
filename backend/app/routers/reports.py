"""Finder reports: a phone running the app says it heard a beacon.

The reporter is any signed-in account. The server checks the heard ID against
the beacon secrets of devices that have an ACTIVE case only, so devices that
are not reported lost are never matched or recorded.

The answer is always the same "received", whether or not the beacon matched,
the report was a replay, or the rules rejected it. A finder therefore cannot
use this endpoint to find out who owns a beacon or whether a case exists.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.beacon import matches
from app.config import get_settings
from app.crypto import decrypt_secret
from app.db import get_db
from app.deps import get_current_user
from app.models import BeaconKey, Case, FinderReport, User
from app.ratelimit import report_limiter
from app.routers.cases import ACTIVE_STATES
from app.routers.observations import ingest
from app.schemas import ReportIn, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])

# Hearing a beacon means the phone is within Bluetooth range of the finder
# (tens of metres), so the position error is the finder's GPS error plus this.
BLE_RANGE_M = 50.0


@router.post("", response_model=ReportOut, status_code=status.HTTP_202_ACCEPTED)
def submit_report(
    body: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReportOut:
    if not report_limiter.allow(user.id, get_settings().reports_per_hour):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many reports; slow down")

    observed_at = body.observed_at.astimezone(timezone.utc)
    rows = db.execute(
        select(Case, BeaconKey)
        .join(BeaconKey, BeaconKey.device_id == Case.device_id)
        .where(Case.state.in_(ACTIVE_STATES))
    ).all()

    for case, key in rows:
        if not matches(decrypt_secret(key.secret_encrypted), body.beacon_id, observed_at):
            continue
        try:
            obs, _ = ingest(
                db, case, source="ble", observed_at=observed_at, lat=body.lat, lon=body.lon,
                accuracy_m=min(100000.0, body.accuracy_m + BLE_RANGE_M),
                nonce=body.nonce, now=datetime.now(timezone.utc),
            )
        except HTTPException:  # replay or per-case cap: same answer as everything else
            break
        if obs is not None:
            db.add(FinderReport(observation_id=obs.id, reporter_id=user.id))
            db.commit()
        break
    return ReportOut()
