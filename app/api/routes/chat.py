"""Chat API endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, SessionDep
from app.core.websocket_manager import ws_manager
from app.crud import crud_chat, crud_listing
from app.models.chat import Message as ChatMessage
from app.models.listing import Listing
from app.schemas.listing import ListingWithImages

router = APIRouter(prefix="/chats", tags=["Chats"])
limiter = Limiter(key_func=get_remote_address)


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

    if not conversations:
        return []

    conv_ids = [c.id for c in conversations]

    # Batch-load participants (2 queries instead of N)
    participants_by_conv = await crud_chat.get_conversation_participants_batch(db, conv_ids)

    # Batch-load latest messages (1 window-function query instead of N)
    latest_msgs = await crud_chat.get_conversation_latest_messages_batch(db, conv_ids)

    # Batch-load real message counts
    msg_counts = await crud_chat.get_conversation_message_counts_batch(db, conv_ids)

    # Batch-load listings + images
    listing_ids = [c.listing_id for c in conversations if c.listing_id]
    listings_map: dict[uuid.UUID, ListingWithImages | None] = {}
    if listing_ids:
        for lid in listing_ids:
            listing = await crud_listing.get_listing(db, str(lid))
            if listing:
                images = await crud_listing.get_listing_images(db, str(listing.id))
                listings_map[lid] = _build_listing_payload(listing, images)
            else:
                listings_map[lid] = None

    payloads = []
    for conv in conversations:
        participants = participants_by_conv.get(conv.id, [])
        last_message = latest_msgs.get(conv.id)
        payloads.append(ChatConversationRead(
            id=conv.id,
            listing_id=conv.listing_id,
            created_at=conv.created_at,
            participant_ids=[p.user_id for p in participants],
            messages_count=msg_counts.get(conv.id, 0),
            last_message=_build_message_payload(last_message) if last_message else None,
            listing=listings_map.get(conv.listing_id) if conv.listing_id else None,
        ))

    return payloads


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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    conversation = await crud_chat.get_conversation_by_id(db, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=404, detail="Cuộc trò chuyện không tìm thấy")

    if not await crud_chat.is_participant(db, conversation.id, current_user.id):
        raise HTTPException(
            status_code=403, detail="Không có quyền truy cập cuộc trò chuyện này")

    messages = await crud_chat.get_conversation_messages(db, conversation_id, skip=skip, limit=limit)
    return [_build_message_payload(message) for message in messages]


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def send_message(
    conversation_id: uuid.UUID,
    payload: ChatMessageCreate,
    request: Request,
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

    return _build_message_payload(message)
