"""CRUD helpers for admin audit logs."""
from typing import Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit import AdminAuditLog


async def create_admin_audit_log(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    note: Optional[str] = None,
) -> AdminAuditLog:
    log = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        note=note,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_admin_audit_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
) -> tuple[list[AdminAuditLog], int]:
    conditions = []
    if action:
        conditions.append(AdminAuditLog.action == action)
    if target_type:
        conditions.append(AdminAuditLog.target_type == target_type)

    count_query = select(func.count()).select_from(AdminAuditLog)
    query = select(AdminAuditLog)

    if conditions:
        count_query = count_query.where(*conditions)
        query = query.where(*conditions)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(AdminAuditLog.created_at.desc()
                       ).offset(skip).limit(limit)
    )
    return list(result.scalars().all()), int(total)
