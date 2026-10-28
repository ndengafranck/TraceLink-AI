from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=400)
    # Every claim must point at stored sightings; the guard checks the ids exist.
    observation_ids: list[str] = Field(min_length=1, max_length=50)


class Explanation(BaseModel):
    """The only shape the model may return. Anything else is rejected."""

    model_config = ConfigDict(extra="forbid")
    headline: str = Field(min_length=1, max_length=200)
    findings: list[Finding] = Field(max_length=10)
    guidance: list[str] = Field(min_length=1, max_length=6)
    uncertainty: list[str] = Field(min_length=1, max_length=6)


class Facts(BaseModel):
    """Counted by plain code, never by the model."""

    total: int
    accepted: int
    flagged: int
    flag_counts: dict[str, int]
    latest_observed_at: str | None
    all_simulated: bool


class ExplanationResponse(BaseModel):
    source: Literal["ai", "fallback"]
    model: str | None
    fallback_reason: str | None
    explanation: Explanation
    facts: Facts
    notice: str
