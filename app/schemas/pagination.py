from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class PaginatedResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
