"""
Category API endpoints.

Handles product category management (CRUD for admins, retrieval for users).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentAdmin, SessionDep
from app.crud import crud_category
from app.models import (
    Category,
    CategoriesPublic,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CategoryWithChildren,
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

    return CategoriesPublic(data=categories, count=count)


# ============================================================================
# Get Root Categories (Public)
# ============================================================================

@router.get(
    "/roots",
    response_model=list[CategoryWithChildren],
    summary="Get root categories with children",
    description="Get all root categories and their subcategories (tree structure)."
)
async def get_root_categories(session: SessionDep) -> list[CategoryWithChildren]:
    """
    Get root categories (parent_id is None) with their children.

    Returns a tree structure suitable for UI category selectors.

    **Response:**
    - List of root categories with nested children
    """
    root_categories = await crud_category.get_categories_root(session)

    result = []
    for category in root_categories:
        children = await crud_category.get_categories_by_parent(session, category.id)
        result.append(
            CategoryWithChildren(
                id=category.id,
                name=category.name,
                slug=category.slug,
                icon_url=category.icon_url,
                parent_id=category.parent_id,
                created_at=category.created_at,
                children=[
                    CategoryWithChildren(
                        id=child.id,
                        name=child.name,
                        slug=child.slug,
                        icon_url=child.icon_url,
                        parent_id=child.parent_id,
                        created_at=child.created_at,
                        children=[]
                    )
                    for child in children
                ]
            )
        )

    return result


# ============================================================================
# Get Category by Slug (Public)
# ============================================================================

@router.get(
    "/{slug}",
    response_model=CategoryWithChildren,
    summary="Get category by slug",
    description="Get category details and its subcategories."
)
async def get_category_by_slug(slug: str, session: SessionDep) -> CategoryWithChildren:
    """
    Get category by slug with its children.

    **Path parameters:**
    - slug: URL-friendly category identifier

    **Response:**
    - Category details with nested children

    **Errors:**
    - 404: Category not found
    """
    category = await crud_category.get_category_by_slug(session, slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    children = await crud_category.get_categories_by_parent(session, category.id)

    return CategoryWithChildren(
        id=category.id,
        name=category.name,
        slug=category.slug,
        icon_url=category.icon_url,
        parent_id=category.parent_id,
        created_at=category.created_at,
        children=[
            CategoryWithChildren(
                id=child.id,
                name=child.name,
                slug=child.slug,
                icon_url=child.icon_url,
                parent_id=child.parent_id,
                created_at=child.created_at,
                children=[]
            )
            for child in children
        ]
    )


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
    current_admin=Depends(CurrentAdmin)
) -> CategoryPublic:
    """
    Create a new category (admin only).

    **Request body:**
    - name: Category name
    - slug: URL-friendly identifier (must be unique)
    - icon_url: (optional) URL to category icon
    - parent_id: (optional) Parent category ID for subcategories

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
    return category


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
    current_admin=Depends(CurrentAdmin)
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

    updated = await crud_category.update_category(session, category, data)
    return updated


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
    current_admin=Depends(CurrentAdmin)
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
