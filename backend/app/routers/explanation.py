from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.ai.client import ModelClient, build_client
from app.ai.schemas import ExplanationResponse
from app.ai.service import explain
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Observation, User
from app.ratelimit import explain_limiter
from app.routers.cases import get_owned_case

router = APIRouter(prefix="/cases/{case_id}/explanation", tags=["ai"])


def get_model_client() -> ModelClient | None:
    """Overridable in tests. None means the AI is not configured."""
    return build_client(get_settings())


@router.post("", response_model=ExplanationResponse)
def explain_case(
    case_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: ModelClient | None = Depends(get_model_client),
) -> ExplanationResponse:
    """Explain this case's validated sightings. POST because it may call a paid API."""
    case = get_owned_case(db, user, case_id)
    settings = get_settings()
    if not explain_limiter.allow(user.id, settings.explain_per_hour):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many explanation requests")
    observations = list(db.scalars(select(Observation).where(Observation.case_id == case.id)))
    result = explain(settings, client, observations, datetime.now(timezone.utc))
    audit.record(db, user.id, "explanation_requested", "case", case.id, result.source)
    return result
