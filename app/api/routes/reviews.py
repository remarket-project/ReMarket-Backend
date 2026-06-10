import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_notification, crud_order, crud_review, crud_user
from app.models.enums import NotificationType, OrderStatus
from app.schemas.review import ReviewCreate, ReviewRead

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    current_user: CurrentUser,
    db: SessionDep,
    data: ReviewCreate,
):
    """Tạo đánh giá cho đơn hàng"""
    order = await crud_order.get_order_by_id(db, data.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Đơn hàng không tìm thấy")

    if order.status != OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=400, detail="Không thể đánh giá đơn hàng chưa hoàn thành")

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Không có quyền đánh giá đơn hàng này")

    existing = await crud_review.get_review_by_order_and_reviewer(db, data.order_id, current_user.id)
    if existing:
        raise HTTPException(
            status_code=400, detail="Bạn đã đánh giá đơn hàng này rồi")

    reviewee_id = order.seller_id if current_user.id == order.buyer_id else order.buyer_id

    review = await crud_review.create_review(
        db,
        order_id=data.order_id,
        reviewer_id=current_user.id,
        reviewee_id=reviewee_id,
        rating=data.rating,
        comment=data.comment
    )
    await crud_notification.create_notification(
        db=db,
        user_id=reviewee_id,
        type=NotificationType.REVIEW_RECEIVED,
        title="Nhận đánh giá mới",
        message="Bạn đã nhận được một đánh giá từ một đơn hàng hoàn thành.",
        data={"order_id": str(data.order_id), "review_id": str(review.id)},
    )

    # Update reviewee's ratings
    await crud_user.update_user_ratings(db, reviewee_id)

    return review


@router.get("/user/{user_id}", response_model=list[ReviewRead])
async def get_user_reviews(user_id: uuid.UUID, db: SessionDep):
    """Lấy tất cả đánh giá của một người dùng"""
    items, total = await crud_review.get_user_reviews(db, user_id)
    return items


@router.get("/{order_id}", response_model=list[ReviewRead])
async def get_review(order_id: uuid.UUID, db: SessionDep):
    """Lấy tất cả đánh giá cho một đơn hàng"""
    reviews = await crud_review.get_reviews_by_order(db, order_id)
    return reviews
