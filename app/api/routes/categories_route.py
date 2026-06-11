"""
Category API endpoints.

Handles product category management (CRUD for admins, retrieval for users).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentAdmin, SessionDep
from app.core.websocket_manager import ws_manager
from app.crud import crud_category
from app.models import (
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["categories"])


# ============================================================================
# Get All Categories (Public)
# ============================================================================

@router.get(
    "/",
    response_model=CategoriesPublic,
    summary="List all categories",
    description="Get all product categories with pagination."
)
async def list_categories(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100
) -> CategoriesPublic:
    """
    List all categories with pagination.

    **Query parameters:**
    - skip: Number of categories to skip (default: 0)
    - limit: Maximum categories to return (default: 100)

    **Response:**
    - List of categories and total count
    """
    categories = await crud_category.get_all_categories(session, skip=skip, limit=limit)
    count = await crud_category.get_categories_count(session)

    return CategoriesPublic(data=[CategoryPublic.model_validate(c) for c in categories], count=count)


# ============================================================================
# Get Flat Categories (Compatibility Alias)
# ============================================================================

@router.get(
    "/roots",
    response_model=list[CategoryPublic],
    summary="Get flat categories",
    description="Compatibility endpoint. Returns flat categories without hierarchy."
)
async def get_root_categories(session: SessionDep) -> list[CategoryPublic]:
    """
    Get categories using a flat structure.

    **Response:**
    - List of categories
    """
    categories = await crud_category.get_all_categories(session, skip=0, limit=1000)
    return [CategoryPublic.model_validate(c) for c in categories]


# ============================================================================
# Get Category by Slug (Public)
# ============================================================================

@router.get(
    "/{slug}",
    response_model=CategoryPublic,
    summary="Get category by slug",
    description="Get category details by slug."
)
async def get_category_by_slug(slug: str, session: SessionDep) -> CategoryPublic:
    """
    Get category by slug.

    **Path parameters:**
    - slug: URL-friendly category identifier

    **Response:**
    - Category details

    **Errors:**
    - 404: Category not found
    """
    category = await crud_category.get_category_by_slug(session, slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    return CategoryPublic.model_validate(category)


# ============================================================================
# Get Category by ID (Public)
# ============================================================================

@router.get(
    "/id/{category_id:uuid}",
    response_model=CategoryPublic,
    summary="Get category by ID",
    description="Get category details by UUID."
)
async def get_category_by_id(
    category_id: uuid.UUID,
    session: SessionDep
) -> CategoryPublic:
    """
    Get category by UUID.

    **Path parameters:**
    - category_id: Category UUID

    **Response:**
    - Category details

    **Errors:**
    - 404: Category not found
    """
    category = await crud_category.get_category_by_id(session, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    return CategoryPublic.model_validate(category)


# ============================================================================
# Admin: Create Category
# ============================================================================

@router.post(
    "/",
    response_model=CategoryPublic,
    status_code=201,
    summary="Create category",
    description="Create a new product category (admin only)."
)
async def create_category(
    data: CategoryCreate,
    session: SessionDep,
    current_admin: CurrentAdmin
) -> CategoryPublic:
    """
    Create a new category (admin only).

    **Request body:**
    - name: Category name
    - slug: URL-friendly identifier (must be unique)
    - icon_url: (optional) URL to category icon

    **Response:**
    - Created category

    **Errors:**
    - 401: Unauthorized
    - 403: Not admin
    - 409: Slug already exists
    """
    # Check if slug already exists
    existing = await crud_category.get_category_by_slug(session, data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category slug already exists"
        )

    # Create category
    category = await crud_category.create_category(session, data)
    await ws_manager.broadcast_to_all({"type": "category_changed"})
    return CategoryPublic.model_validate(category)


# ============================================================================
# Admin: Update Category
# ============================================================================

@router.put(
    "/{category_id}",
    response_model=CategoryPublic,
    summary="Update category",
    description="Update category details (admin only)."
)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    session: SessionDep,
    current_admin: CurrentAdmin
) -> CategoryPublic:
    """
    Update category (admin only).

    **Path parameters:**
    - category_id: Category UUID

    **Request body:**
    - name: (optional) Category name
    - slug: (optional) URL-friendly identifier
    - icon_url: (optional) Icon URL

    **Response:**
    - Updated category

    **Errors:**
    - 401: Unauthorized
    - 403: Not admin
    - 404: Category not found
    """
    category = await crud_category.get_category_by_id(session, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    updated = await crud_category.update_category(session, category_id, data)
    await ws_manager.broadcast_to_all({"type": "category_changed"})
    return CategoryPublic.model_validate(updated)


# ============================================================================
# Admin: Delete Category
# ============================================================================

@router.delete(
    "/{category_id}",
    status_code=204,
    summary="Delete category",
    description="Delete a category (admin only)."
)
async def delete_category(
    category_id: uuid.UUID,
    session: SessionDep,
    current_admin: CurrentAdmin
) -> None:
    """
    Delete category (admin only).

    **Path parameters:**
    - category_id: Category UUID

    **Response:**
    - 204 No Content on success

    **Errors:**
    - 401: Unauthorized
    - 403: Not admin
    - 404: Category not found
    """
    deleted = await crud_category.delete_category(session, category_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    await ws_manager.broadcast_to_all({"type": "category_changed"})
