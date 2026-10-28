"""Endpoints used by the TraceLink Android app on the phone itself."""

import base64
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import audit
from app.beacon import ID_BYTES, WINDOW_SECONDS
from app.crypto import decrypt_secret, encrypt_secret
from app.db import get_db
from app.deps import get_current_user
from app.models import BeaconKey, User
from app.routers.devices import get_owned
from app.routers.ownership import issue_challenge
from app.schemas import ChallengeOut, EnrollOut

router = APIRouter(prefix="/companion/devices/{device_id}", tags=["companion"])


@router.post("/challenge", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
def phone_challenge(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ChallengeOut:
    """The phone asks for an ownership code and shows it on its own screen."""
    device = get_owned(db, user, device_id)
    proof, code = issue_challenge(db, device, "companion_app")
    return ChallengeOut(channel=proof.channel, expires_at=proof.expires_at, code=code)


@router.post("/enroll", response_model=EnrollOut)
def enroll(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> EnrollOut:
    """Give the verified phone its beacon secret (the same one again if asked twice)."""
    device = get_owned(db, user, device_id)
    if device.status != "verified":
        raise HTTPException(status.HTTP_409_CONFLICT, "Verify ownership of this device first")
    key = db.get(BeaconKey, device.id)
    if key is None:
        key = BeaconKey(device_id=device.id, secret_encrypted=encrypt_secret(secrets.token_bytes(32)))
        db.add(key)
        db.commit()
        audit.record(db, user.id, "beacon_enrolled", "device", device.id)
    secret = decrypt_secret(key.secret_encrypted)
    return EnrollOut(
        beacon_secret=base64.urlsafe_b64encode(secret).decode(),
        window_seconds=WINDOW_SECONDS,
        id_bytes=ID_BYTES,
    )
