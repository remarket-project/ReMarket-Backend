"""Chat API endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.core.websocket_manager import ws_manager
from app.crud import crud_chat, crud_listing, crud_notification
from app.models.chat import Message as ChatMessage
from app.models.listing import Listing
from app.schemas.listing import ListingWithImages

router = APIRouter(prefix="/chats", tags=["Chats"])


class ChatMessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatConversationRead(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID | None = None
    created_at: datetime
    participant_ids: list[uuid.UUID]
    messages_count: int
    last_message: ChatMessageRead | None = None
    listing: ListingWithImages | None = None


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


def _build_listing_payload(listing: Listing, images) -> ListingWithImages:
    listing_dict = listing.model_dump(
        exclude={"seller", "category", "images", "offers", "orders"}
    )
    listing_dict["images"] = images
    if listing.seller:
        listing_dict["seller_name"] = listing.seller.full_name
        listing_dict["seller_avatar_url"] = listing.seller.avatar_url
    return ListingWithImages(**listing_dict)


def _build_message_payload(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead.model_validate(message)


async def _build_conversation_payload(db: SessionDep, conversation) -> ChatConversationRead:
    participants = await crud_chat.get_conversation_participants(db, conversation.id)
    messages = await crud_chat.get_conversation_messages(db, conversation.id)
    last_message = _build_message_payload(messages[-1]) if messages else None

    listing_payload = None
    if conversation.listing_id:
        listing = await crud_listing.get_listing(db, str(conversation.listing_id))
        if listing:
            images = await crud_listing.get_listing_images(db, str(listing.id))
            listing_payload = _build_listing_payload(listing, images)

    return ChatConversationRead(
        id=conversation.id,
        listing_id=conversation.listing_id,
        created_at=conversation.created_at,
        participant_ids=[participant.user_id for participant in participants],
        messages_count=len(messages),
        last_message=last_message,
        listing=listing_payload,
    )


@router.get("/conversations", response_model=list[ChatConversationRead])
async def list_my_conversations(
    current_user: CurrentUser,
    db: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    conversations, _ = await crud_chat.get_user_conversations(db, current_user.id, skip=skip, limit=limit)
    return [await _build_conversation_payload(db, conversation) for conversation in conversations]


@router.post("/conversations/listing/{listing_id}", response_model=ChatConversationRead, status_code=status.HTTP_201_CREATED)
async def create_listing_conversation(
    listing_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep,
):
    listing = await crud_listing.get_listing(db, str(listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Bài đăng không tìm thấy")

    if listing.seller_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Không thể nhắn tin với bài đăng của chính mình")

    existing = await crud_chat.get_conversation_by_listing_and_user(db, listing_id, current_user.id)
    if existing:
        return await _build_conversation_payload(db, existing)

    conversation = await crud_chat.create_conversation(db, listing_id=listing_id)
    await crud_chat.add_participant(db, conversation.id, current_user.id)
    await crud_chat.add_participant(db, conversation.id, listing.seller_id)
    return await _build_conversation_payload(db, conversation)


@router.get("/conversations/{conversation_id}", response_model=ChatConversationRead)
async def get_conversation_detail(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep,
):
    conversation = await crud_chat.get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail="Cuộc trò chuyện không tìm thấy")

    if not await crud_chat.is_participant(db, conversation.id, current_user.id):
        raise HTTPException(
            status_code=403, detail="Không có quyền truy cập cuộc trò chuyện này")

    return await _build_conversation_payload(db, conversation)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: SessionDep,
):
    conversation = await crud_chat.get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail="Cuộc trò chuyện không tìm thấy")

    if not await crud_chat.is_participant(db, conversation.id, current_user.id):
        raise HTTPException(
            status_code=403, detail="Không có quyền truy cập cuộc trò chuyện này")

    messages = await crud_chat.get_conversation_messages(db, conversation_id)
    return [_build_message_payload(message) for message in messages]


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: uuid.UUID,
    payload: ChatMessageCreate,
    current_user: CurrentUser,
    db: SessionDep,
):
    conversation = await crud_chat.get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail="Cuộc trò chuyện không tìm thấy")

    if not await crud_chat.is_participant(db, conversation.id, current_user.id):
        raise HTTPException(
            status_code=403, detail="Không có quyền nhắn tin trong cuộc trò chuyện này")

    message = await crud_chat.post_message(
        db,
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=payload.content,
    )

    participants = await crud_chat.get_conversation_participants(db, conversation.id)

    ws_message = {
        "type": "chat_message",
        "conversation_id": str(conversation.id),
        "message": {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "sender_id": str(message.sender_id),
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
    }

    for participant in participants:
        if participant.user_id != current_user.id:
            await ws_manager.send_to_user(participant.user_id, ws_message)

            listing_title = "sản phẩm"
            if conversation.listing_id:
                listing_obj = await crud_listing.get_listing(db, str(conversation.listing_id))
                listing_title = listing_obj.title if listing_obj else "sản phẩm"

            notif = await crud_notification.create_notification(
                db,
                user_id=participant.user_id,
                type="offer_received",
                title=f"Tin nhắn mới từ {current_user.full_name}",
                message=f"{current_user.full_name} đã gửi tin nhắn về {listing_title}",
                data={
                    "conversation_id": str(conversation.id),
                    "listing_id": str(conversation.listing_id) if conversation.listing_id else None,
                    "sender_name": current_user.full_name,
                },
            )
            await ws_manager.send_to_user(participant.user_id, {
                "type": "notification",
                "title": f"Tin nhắn mới từ {current_user.full_name}",
                "message": f"{current_user.full_name} đã gửi tin nhắn về {listing_title}",
                "notification_id": str(notif.id),
                "data": {
                    "conversation_id": str(conversation.id),
                },
            })

    return _build_message_payload(message)
