"""Admin audit trail endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentAdmin, SessionDep
from app.crud import crud_admin_audit

router = APIRouter(prefix="/admin", tags=["Admin Audit"])


class AdminAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admin_id: uuid.UUID
    action: str
    target_type: str | None = None
    target_id: str | None = None
    note: str | None = None
    created_at: datetime


class AdminAuditTrailResponse(BaseModel):
    items: list[AdminAuditLogRead]
    total: int
    skip: int
    limit: int


@router.get("/audit-trail", response_model=AdminAuditTrailResponse)
async def list_audit_trail(
    current_admin: CurrentAdmin,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: str | None = None,
    target_type: str | None = None,
):
    logs, total = await crud_admin_audit.get_admin_audit_logs(
        db,
        skip=skip,
        limit=limit,
        action=action,
        target_type=target_type,
    )
    return AdminAuditTrailResponse(
        items=[AdminAuditLogRead.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
    )
