from fastapi import APIRouter
from pydantic import BaseModel

from app.services.faq_chatbot import ask_faq

router = APIRouter(prefix="/faq", tags=["FAQ"])


class Message(BaseModel):
    role: str
    content: str


class FaqQuestion(BaseModel):
    question: str
    history: list[Message] | None = None


class FaqProduct(BaseModel):
    id: str
    title: str
    price: float
    condition: str
    location: str
    seller: str
    image_url: str | None = None

class FaqSuggestedAction(BaseModel):
    label: str
    payload: str


class FaqResponse(BaseModel):
    answer: str
    source: str | None = None
    mode: str = "gemini"
    products: list[FaqProduct] = []
    suggested_actions: list[FaqSuggestedAction] = []


@router.post("/ask")
async def ask_question(data: FaqQuestion):
    history = [m.model_dump() for m in data.history] if data.history else None
    result = await ask_faq(data.question, history=history)
    return FaqResponse(**result)
