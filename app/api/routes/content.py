from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.crud.crud_content import get_content_by_key, get_contents_by_keys

router = APIRouter(prefix="/content", tags=["Content"])


class StaticContentRead(BaseModel):
    id: str
    key: str
    title: str
    body: str
    locale: str
    version: int
    created_at: datetime
    updated_at: datetime


class StaticContentCollection(BaseModel):
    items: list[StaticContentRead]


HELP_KEYS = [
    "help_home",
    "help_buying",
    "help_selling",
    "help_payment",
    "help_shipping",
    "help_dispute",
    "faq",
    "contact",
]

LEGAL_KEYS = [
    "terms",
    "privacy",
    "cookies",
    "community_guidelines",
    "refund_policy",
]


def _to_content_read(content) -> StaticContentRead:
    return StaticContentRead.model_validate(content)


@router.get("/help", response_model=StaticContentCollection)
async def get_help_pages(
    db: SessionDep,
    locale: str = Query("vi", max_length=10),
):
    items = await get_contents_by_keys(db, HELP_KEYS, locale=locale)
    return StaticContentCollection(items=[_to_content_read(item) for item in items])


@router.get("/legal", response_model=StaticContentCollection)
async def get_legal_pages(
    db: SessionDep,
    locale: str = Query("vi", max_length=10),
):
    items = await get_contents_by_keys(db, LEGAL_KEYS, locale=locale)
    return StaticContentCollection(items=[_to_content_read(item) for item in items])


@router.get("/{key}")
async def get_content(key: str, db: SessionDep):
    content = await get_content_by_key(db, key)
    if not content:
        raise HTTPException(status_code=404, detail="Nội dung không tìm thấy")
    return content
