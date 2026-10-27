import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Always stored lower-cased so "A@x.com" and "a@x.com" are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    nickname: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    imei_encrypted: Mapped[str] = mapped_column(String(255))
    # Keyed hash; unique so one IMEI can only be registered once.
    imei_hmac: Mapped[str] = mapped_column(String(64), unique=True)
    imei_last4: Mapped[str] = mapped_column(String(4))
    # "unverified" until the ownership-proof slice marks it "verified".
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OwnershipProof(Base):
    """One row per ownership challenge issued for a device."""

    __tablename__ = "ownership_proofs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    code_digest: Mapped[str] = mapped_column(String(64))
    # "demo" = code shown by the API (simulated); later "android_app".
    channel: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set when the challenge is used up or replaced by a newer one.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


_ACTIVE = "state IN ('open','evidence_received')"


class Case(Base):
    """A lost-device case. States: open, evidence_received, recovered, closed."""

    __tablename__ = "cases"
    # At most one active case per device, enforced by the database itself.
    __table_args__ = (
        Index(
            "uq_one_active_case_per_device",
            "device_id",
            unique=True,
            postgresql_where=text(_ACTIVE),
            sqlite_where=text(_ACTIVE),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    opened_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Observation(Base):
    """One stored sighting. Rejected sightings are never stored (data minimisation)."""

    __tablename__ = "observations"
    # Replay protection: the same report id cannot be stored twice for a case.
    __table_args__ = (UniqueConstraint("case_id", "nonce", name="uq_observation_case_nonce"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    # "simulated" now; "ble" once a real source exists. Never mislabel one as the other.
    source: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float] = mapped_column(Float)
    nonce: Mapped[str] = mapped_column(String(64))
    validation_status: Mapped[str] = mapped_column(String(20))
    flags: Mapped[list] = mapped_column(JSON, default=list)
