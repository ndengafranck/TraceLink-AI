from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, EmailStr, Field, field_validator

from app.crypto import is_valid_imei


class Credentials(BaseModel):
    email: EmailStr
    # 10 minimum follows current guidance favouring length over complexity rules.
    password: str = Field(min_length=10, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime


class DeviceIn(BaseModel):
    nickname: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    imei: str = Field(min_length=15, max_length=15)

    @field_validator("imei")
    @classmethod
    def _imei_must_be_valid(cls, v: str) -> str:
        if not is_valid_imei(v):
            # Deliberately does not echo the value back.
            raise ValueError("Invalid IMEI")
        return v


class DeviceOut(BaseModel):
    id: str
    nickname: str
    model: str
    imei_masked: str
    status: str
    # How ownership was proven; "demo" means simulated, not a real on-device check.
    verified_via: str | None = None
    created_at: datetime


class ChallengeOut(BaseModel):
    channel: str
    expires_at: datetime
    # Present only in demo mode.
    code: str | None = None


class VerifyIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class CaseOut(BaseModel):
    id: str
    device_id: str
    state: str
    opened_at: datetime
    closed_at: datetime | None = None


class ObservationIn(BaseModel):
    source: Literal["simulated"]
    # AwareDatetime rejects timestamps without a time zone: they are ambiguous.
    observed_at: AwareDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0, le=100000)
    nonce: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")


class ObservationOut(BaseModel):
    id: str
    source: str
    observed_at: datetime
    received_at: datetime
    lat: float
    lon: float
    accuracy_m: float
    validation_status: str
    flags: list[str]
    age_seconds: int


class SimulateIn(BaseModel):
    scenario: Literal["fresh_cluster", "stale", "conflicting", "low_accuracy"]


class SimulatedItemOut(BaseModel):
    observed_at: datetime
    status: str
    flags: list[str]
    reason: str | None = None


class SimulationOut(BaseModel):
    scenario: str
    results: list[SimulatedItemOut]
