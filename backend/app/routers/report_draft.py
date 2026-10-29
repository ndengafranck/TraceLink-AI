from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ai.client import ModelClient
from app.ai.report import build_body, fallback_narrative
from app.ai.schemas import ReportDraftIn, ReportDraftResponse
from app.ai.service import notice, write_narrative
from app.ai.tools import summarize
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Device, Observation, User
from app.ratelimit import explain_limiter
from app.routers.cases import get_owned_case
from app.routers.devices import verified_channels
from app.routers.explanation import get_model_client

router = APIRouter(prefix="/cases/{case_id}/report-draft", tags=["ai"])


@router.post("", response_model=ReportDraftResponse)
def report_draft(
    case_id: str,
    body: ReportDraftIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: ModelClient | None = Depends(get_model_client),
) -> ReportDraftResponse:
    """A message the owner can send to the police or the mobile operator. Editable text."""
    body = body or ReportDraftIn()
    case = get_owned_case(db, user, case_id)
    settings = get_settings()
    if not explain_limiter.allow(user.id, settings.explain_per_hour):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many AI requests")
    device = db.get(Device, case.device_id)
    observations = list(db.scalars(select(Observation).where(Observation.case_id == case.id)))
    now = datetime.now(timezone.utc)

    narrative, reason = write_narrative(settings, client, observations, now, body.language, body.audience)
    source = "ai"
    if narrative is None:
        source = "fallback"
        narrative = fallback_narrative(observations, body.language, body.audience)
    title, text = build_body(
        language=body.language, audience=body.audience, device=device, case=case,
        ownership_channel=verified_channels(db, [device.id]).get(device.id),
        observations=observations, narrative=narrative, prepared_at=now)
    audit.record(db, user.id, "report_draft_requested", "case", case.id, f"{body.audience}/{source}")
    return ReportDraftResponse(
        source=source, model=client.name if source == "ai" and client else None,
        fallback_reason=reason if source == "fallback" else None, language=body.language,
        audience=body.audience, title=title, body=text,
        notice=notice(summarize(observations), body.language))
