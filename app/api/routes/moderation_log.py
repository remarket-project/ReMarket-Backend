"""Admin AI moderation log endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentAdmin, SessionDep
from app.crud import crud_moderation_log

router = APIRouter(prefix="/admin", tags=["Admin Moderation Log"])


class ModerationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    listing_title: str
    decision: str
    reason: str | None = None
    model_used: str | None = None
    image_count: int = 0
    created_at: datetime


class ModerationLogResponse(BaseModel):
    items: list[ModerationLogRead]
    total: int
    skip: int
    limit: int


@router.get("/moderation-logs", response_model=ModerationLogResponse)
async def list_moderation_logs(
    current_admin: CurrentAdmin,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    decision: str | None = Query(None, description="Filter: approve|flag|reject|error"),
):
    logs, total = await crud_moderation_log.get_moderation_logs(
        db,
        skip=skip,
        limit=limit,
        decision=decision,
    )
    return ModerationLogResponse(
        items=[ModerationLogRead.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )
