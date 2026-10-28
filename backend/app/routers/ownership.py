"""Ownership proof: the owner shows control of the device with a one-time code.

Limits (all tested):
- the code is 6 digits, valid for 10 minutes, usable once;
- 5 wrong guesses lock that code;
- at most 3 codes per device per hour (otherwise an attacker could keep
  requesting fresh codes and guessing without end);
- a newer code cancels any older open one;
- the code is stored only as a keyed hash bound to the device.

Two channels, always labelled on the proof:
- "companion_app": the TraceLink Android app on the phone requests the code
  (routers/companion.py) and shows it on the phone's screen; the owner types it
  into the website.
- "demo": DEMO_MODE only; the API returns the code itself.
Limitation: the app signs in with the same account, so this proves "someone with
the account and the phone screen", not hardware attestation.
"""

import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import proof_digest
from app.db import get_db
from app.deps import get_current_user
from app.models import Device, OwnershipProof, User
from app.routers.devices import get_owned, to_out
from app.schemas import ChallengeOut, DeviceOut, VerifyIn

router = APIRouter(prefix="/devices/{device_id}/ownership", tags=["ownership"])

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
MAX_CHALLENGES_PER_HOUR = 3


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; treat them as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def issue_challenge(db: Session, device: Device, channel: str) -> tuple[OwnershipProof, str]:
    """Create a one-time code for a device and return (proof row, plain code).

    The caller decides where the code is shown. Limits (3 per hour, older codes
    cancelled) apply to every channel.
    """
    if device.status == "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "Device is already verified")
    now = datetime.now(timezone.utc)
    recent = db.scalar(
        select(func.count())
        .select_from(OwnershipProof)
        .where(
            OwnershipProof.device_id == device.id,
            OwnershipProof.created_at > now - timedelta(hours=1),
        )
    )
    if recent >= MAX_CHALLENGES_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested; try later")

    for old in db.scalars(
        select(OwnershipProof).where(
            OwnershipProof.device_id == device.id, OwnershipProof.consumed_at.is_(None)
        )
    ):
        old.consumed_at = now

    code = f"{secrets.randbelow(10**6):06d}"
    proof = OwnershipProof(
        device_id=device.id,
        code_digest=proof_digest(device.id, code),
        channel=channel,
        expires_at=now + CODE_TTL,
    )
    db.add(proof)
    db.commit()
    return proof, code


@router.post("/challenge", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
def create_challenge(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ChallengeOut:
    """Demo channel: the API returns the code itself. Off unless DEMO_MODE=true."""
    device = get_owned(db, user, device_id)
    if device.status == "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "Device is already verified")
    if not get_settings().demo_mode:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Demo codes are off. Request the code from the TraceLink app on the phone.",
        )
    proof, code = issue_challenge(db, device, "demo")
    return ChallengeOut(channel=proof.channel, expires_at=proof.expires_at, code=code)


@router.post("/verify", response_model=DeviceOut)
def verify(
    device_id: str,
    body: VerifyIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceOut:
    device = get_owned(db, user, device_id)
    if device.status == "verified":
        proof = db.scalar(
            select(OwnershipProof).where(
                OwnershipProof.device_id == device.id, OwnershipProof.verified_at.is_not(None)
            )
        )
        return to_out(device, proof.channel if proof else None)

    # One message for every failure, so a caller cannot tell "expired" from "wrong".
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    now = datetime.now(timezone.utc)
    proof = db.scalar(
        select(OwnershipProof)
        .where(OwnershipProof.device_id == device.id, OwnershipProof.consumed_at.is_(None))
        .order_by(OwnershipProof.created_at.desc())
    )
    if proof is None or now >= _aware(proof.expires_at) or proof.attempts >= MAX_ATTEMPTS:
        raise invalid

    proof.attempts += 1
    if not hmac.compare_digest(proof.code_digest, proof_digest(device.id, body.code)):
        db.commit()  # keep the attempt count
        raise invalid

    proof.consumed_at = now
    proof.verified_at = now
    device.status = "verified"
    db.commit()
    return to_out(device, proof.channel)
