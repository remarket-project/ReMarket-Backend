import os
import uuid
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.crud import crud_category, crud_listing
from app.models.enums import ListingStatus, OfferStatus
from app.models.offer import Offer
from app.models.user import UserRole
from app.schemas.listing import (
    ListingCreate,
    ListingImageRead,
    ListingPaginated,
    ListingRead,
    ListingUpdate,
    ListingWithImages,
)
from app.services.minio_service import get_minio_service

router = APIRouter(prefix="/listings", tags=["Listings"])
limiter = Limiter(key_func=get_remote_address)

UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "listings")
ABS_UPLOAD_DIR = os.path.abspath(UPLOAD_DIR)
os.makedirs(ABS_UPLOAD_DIR, exist_ok=True)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class PriceBandRead(BaseModel):
    label: str
    min_price: int | None
    max_price: int | None
    count: int


def _listing_with_images_payload(listing, images):
    listing_dict = listing.model_dump()
    listing_dict["images"] = images
    if getattr(listing, "seller", None):
        listing_dict["seller_name"] = listing.seller.full_name
        listing_dict["seller_avatar_url"] = listing.seller.avatar_url
    return ListingWithImages(**listing_dict)


async def _fetch_listing_with_images(db: SessionDep, listing_id: uuid.UUID) -> ListingWithImages:
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")
    images = await crud_listing.get_listing_images(db, str(listing.id))
    return _listing_with_images_payload(listing, images)


@router.get("", response_model=ListingPaginated, include_in_schema=False)
@router.get("/", response_model=ListingPaginated)
async def list_listings(
    db: SessionDep,
    keyword: str | None = None,
    category_id: uuid.UUID | None = None,
    seller_id: uuid.UUID | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort_by: Literal["newest", "oldest", "price_asc",
                     "price_desc", "popular", "featured"] = "newest",
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Danh sách các bài đăng hoạt động (công khai)"""
    cat_id_str = str(category_id) if category_id else None
    items, total = await crud_listing.search_listings(
        db,
        keyword=keyword,
        category_id=cat_id_str,
        seller_id=str(seller_id) if seller_id else None,
        min_price=min_price,
        max_price=max_price,
        status=ListingStatus.ACTIVE,
        sort_by=sort_by,
        skip=skip,
        limit=limit
    )

    listing_ids = [item.id for item in items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)

    listings_with_images = []
    for item in items:
        listings_with_images.append(
            _listing_with_images_payload(
                item, images_by_listing.get(item.id, []))
        )

    return ListingPaginated(
        items=listings_with_images,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/featured", response_model=ListingPaginated)
async def get_featured_listings(
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items, total = await crud_listing.get_featured_listings(db, skip=skip, limit=limit)
    listing_ids = [item.id for item in items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)
    return ListingPaginated(
        items=[_listing_with_images_payload(
            item, images_by_listing.get(item.id, [])) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/trending", response_model=ListingPaginated)
async def get_trending_listings(
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items, total = await crud_listing.search_listings(
        db,
        status=ListingStatus.ACTIVE,
        sort_by="popular",
        skip=skip,
        limit=limit,
    )
    listing_ids = [item.id for item in items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)
    return ListingPaginated(
        items=[_listing_with_images_payload(
            item, images_by_listing.get(item.id, [])) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/search-suggestions", response_model=list[str])
async def get_search_suggestions(
    db: SessionDep,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=20),
):
    return await crud_listing.get_listing_suggestions(db, q, limit=limit)


@router.get("/price-bands", response_model=list[PriceBandRead])
async def get_price_band_summary(
    db: SessionDep,
    category_id: uuid.UUID | None = None,
):
    summary = await crud_listing.get_price_band_summary(db, category_id=str(category_id) if category_id else None)
    return [PriceBandRead.model_validate(item) for item in summary]


@router.get("/me", response_model=ListingPaginated)
async def get_my_listings(
    current_user: CurrentUser,
    db: SessionDep,
    keyword: str | None = None,
    status: ListingStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Danh sách bài đăng của tôi (tất cả trạng thái)"""
    items, total = await crud_listing.search_listings(
        db,
        keyword=keyword,
        seller_id=str(current_user.id),
        status=status,
        skip=skip,
        limit=limit
    )

    listing_ids = [item.id for item in items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)

    listings_with_images = []
    for item in items:
        listings_with_images.append(
            _listing_with_images_payload(
                item, images_by_listing.get(item.id, []))
        )

    return ListingPaginated(
        items=listings_with_images,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{listing_id}/related", response_model=ListingPaginated)
async def get_related_listings(
    listing_id: uuid.UUID,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(8, ge=1, le=20),
):
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    items, total = await crud_listing.get_related_listings(db, listing, skip=skip, limit=limit)
    listing_ids = [item.id for item in items]
    images_by_listing = await crud_listing.get_images_for_listings(db, listing_ids)
    return ListingPaginated(
        items=[_listing_with_images_payload(
            item, images_by_listing.get(item.id, [])) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing_image_route(
    current_user: CurrentUser,
    db: SessionDep,
    image_id: uuid.UUID,
):
    """Xóa ảnh từ bài đăng"""
    image = await crud_listing.get_listing_image(db, str(image_id))
    if not image:
        raise HTTPException(status_code=404, detail="Ảnh không tìm thấy")

    listing = await crud_listing.get_listing(db, str(image.listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if str(listing.seller_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Không có quyền xóa ảnh này")

    if listing.status == ListingStatus.ACTIVE:
        images = await crud_listing.get_listing_images(db, str(listing.id))
        if len(images) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Không thể xóa ảnh cuối cùng của bài đăng hoạt động"
            )

    await crud_listing.delete_listing_image(db, str(image_id))
    return None


@router.get("/{listing_id}", response_model=ListingWithImages)
async def get_listing(
    listing_id: uuid.UUID,
    db: SessionDep
):
    """Lấy chi tiết bài đăng"""
    return await _fetch_listing_with_images(db, listing_id)


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create_listing(
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
    data: ListingCreate,
):
    """Tạo bài đăng mới (trạng thái = PENDING)"""
    category = await crud_category.get_category_by_id(db, data.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Danh mục không tìm thấy")

    try:
        new_listing = await crud_listing.create_listing(
            db,
            title=data.title,
            description=data.description,
            price=data.price,
            is_negotiable=data.is_negotiable,
            condition_grade=data.condition_grade,
            seller_id=str(current_user.id),
            category_id=str(data.category_id)
        )
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(status_code=400, detail="ID danh mục không hợp lệ") from err
    return new_listing


@router.patch("/{listing_id}", response_model=ListingRead)
@limiter.limit("10/hour")
async def update_listing(
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
    listing_id: uuid.UUID,
    data: ListingUpdate,
):
    """Cập nhật bài đăng"""
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if str(listing.seller_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Không có quyền chỉnh sửa bài đăng này")

    if listing.status == ListingStatus.SOLD:
        raise HTTPException(
            status_code=400, detail="Không thể chỉnh sửa bài đăng đã bán")

    if current_user.role != UserRole.ADMIN:
        result = await db.execute(
            select(Offer).where(
                Offer.listing_id == listing.id,  # type: ignore
                Offer.status.in_([OfferStatus.PENDING, OfferStatus.COUNTERED])  # type: ignore
            )
        )
        active_offers = result.scalars().first()
        if active_offers:
            raise HTTPException(
                status_code=400,
                detail="Không thể chỉnh sửa bài đăng khi có yêu cầu mua chưa xử lý"
            )

    if data.status is not None and current_user.role != UserRole.ADMIN:
        if data.status not in (ListingStatus.HIDDEN, ListingStatus.ACTIVE, ListingStatus.SOLD):
            raise HTTPException(
                status_code=403, detail="Chỉ admin có thể thay đổi trạng thái")

    if data.category_id is not None:
        category = await crud_category.get_category_by_id(db, data.category_id)
        if not category:
            raise HTTPException(
                status_code=404, detail="Danh mục không tìm thấy")

    updated_listing = await crud_listing.update_listing(
        db,
        str(listing_id),
        title=data.title,
        description=data.description,
        price=data.price,
        is_negotiable=data.is_negotiable,
        condition_grade=data.condition_grade,
        category_id=str(data.category_id) if data.category_id else None,
        status=data.status,
    )
    return updated_listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
async def delete_listing(
    current_user: CurrentUser,
    db: SessionDep,
    request: Request,
    listing_id: uuid.UUID,
):
    """Xóa bài đăng (vĩnh viễn)"""
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if str(listing.seller_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403, detail="Không có quyền xóa bài đăng này")

    if listing.status == ListingStatus.SOLD:
        raise HTTPException(
            status_code=400, detail="Không thể xóa bài đăng đã bán")

    await crud_listing.hard_delete_listing(db, str(listing_id))
    return None


@router.post("/{listing_id}/images", response_model=ListingImageRead)
async def upload_listing_image(
    current_user: CurrentUser,
    db: SessionDep,
    listing_id: uuid.UUID,
    file: UploadFile = File(...),
    is_primary: bool = Query(False),
):
    """Tải ảnh lên cho bài đăng (hỗ trợ MinIO hoặc local filesystem)"""
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if str(listing.seller_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Không có quyền tải ảnh")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail="Định dạng file không được hỗ trợ")

    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Định dạng file không được hỗ trợ")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="File quá lớn")

    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # Upload to MinIO or local filesystem
    if settings.use_minio:
        try:
            minio_service = get_minio_service()
            if not minio_service:
                raise RuntimeError("MinIO service not available")
            file_path = f"listings/{str(listing_id)}/{unique_filename}"
            image_url = minio_service.upload_file(
                file_path,
                file_bytes,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Error uploading to MinIO: {str(e)}") from e
    else:
        # Use local filesystem
        file_path = os.path.abspath(
            os.path.join(ABS_UPLOAD_DIR, unique_filename))
        if not file_path.startswith(f"{ABS_UPLOAD_DIR}{os.sep}"):
            raise HTTPException(
                status_code=400, detail="Đường dẫn upload không hợp lệ")

        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        image_url = f"/{settings.UPLOAD_DIR}/listings/{unique_filename}"

    new_image = await crud_listing.add_listing_image(db, str(listing_id), image_url, is_primary)
    return new_image
