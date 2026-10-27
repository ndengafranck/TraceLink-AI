from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto import encrypt_imei, imei_fingerprint, mask_imei
from app.db import get_db
from app.deps import get_current_user
from app.models import Case, Device, Observation, OwnershipProof, User
from app.schemas import DeviceIn, DeviceOut

router = APIRouter(prefix="/devices", tags=["devices"])


def verified_channels(db: Session, device_ids: list[str]) -> dict[str, str]:
    """Map device id -> channel of its successful ownership proof."""
    if not device_ids:
        return {}
    rows = db.execute(
        select(OwnershipProof.device_id, OwnershipProof.channel).where(
            OwnershipProof.device_id.in_(device_ids),
            OwnershipProof.verified_at.is_not(None),
        )
    )
    return {device_id: channel for device_id, channel in rows}


def to_out(d: Device, verified_via: str | None = None) -> DeviceOut:
    return DeviceOut(
        id=d.id,
        nickname=d.nickname,
        model=d.model,
        imei_masked=mask_imei(d.imei_last4),
        status=d.status,
        verified_via=verified_via,
        created_at=d.created_at,
    )


def get_owned(db: Session, user: User, device_id: str) -> Device:
    """Fetch a device only if it belongs to the caller.

    Someone else's device and a device that does not exist both give 404, so
    the API never confirms that another user's device id exists.
    """
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
    )
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return device


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    body: DeviceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DeviceOut:
    fingerprint = imei_fingerprint(body.imei)
    if db.scalar(select(Device.id).where(Device.imei_hmac == fingerprint)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This device is already registered")
    device = Device(
        owner_id=user.id,
        nickname=body.nickname.strip(),
        model=body.model.strip(),
        imei_encrypted=encrypt_imei(body.imei),
        imei_hmac=fingerprint,
        imei_last4=body.imei[-4:],
    )
    db.add(device)
    try:
        db.commit()
    except IntegrityError:  # simultaneous registration of the same IMEI
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This device is already registered")
    return to_out(device)


@router.get("", response_model=list[DeviceOut])
def list_my_devices(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[DeviceOut]:
    rows = list(
        db.scalars(
            select(Device).where(Device.owner_id == user.id).order_by(Device.created_at.desc())
        )
    )
    channels = verified_channels(db, [d.id for d in rows])
    return [to_out(d, channels.get(d.id)) for d in rows]


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DeviceOut:
    device = get_owned(db, user, device_id)
    return to_out(device, verified_channels(db, [device.id]).get(device.id))


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    device = get_owned(db, user, device_id)
    case_ids = select(Case.id).where(Case.device_id == device.id)
    db.execute(delete(Observation).where(Observation.case_id.in_(case_ids)))
    db.execute(delete(Case).where(Case.device_id == device.id))
    db.execute(delete(OwnershipProof).where(OwnershipProof.device_id == device.id))
    db.delete(device)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
