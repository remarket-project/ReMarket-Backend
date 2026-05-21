from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.crud.crud_content import get_content_by_key

router = APIRouter(prefix="/content", tags=["Content"])


@router.get("/{key}")
async def get_content(key: str, db: SessionDep):
    content = await get_content_by_key(db, key)
    if not content:
        raise HTTPException(status_code=404, detail="Nội dung không tìm thấy")
    return content
