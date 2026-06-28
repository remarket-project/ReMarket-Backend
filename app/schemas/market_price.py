import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import ConditionGrade


class ExternalReference(BaseModel):
    source: str
    title: str
    search_url: str


class SimilarListingSummary(BaseModel):
    id: str | None = None
    title: str
    price: Decimal
    condition_grade: ConditionGrade
    location_summary: str | None = None


class PriceSuggestionRequest(BaseModel):
    category_id: uuid.UUID
    condition_grade: ConditionGrade
    title: str = Field(..., min_length=5, max_length=500)
    description: str | None = None


class PriceSuggestionResponse(BaseModel):
    suggested_price: float
    price_range_min: float
    price_range_max: float
    market_insight: str
    average_price: float
    similar_listings: list[SimilarListingSummary] = []
    external_references: list[ExternalReference] = []
    analysis: str


class MarketAnalysisResponse(BaseModel):
    listing_id: uuid.UUID
    listing_price: float
    assessment: str
    average_price: float
    price_range_min: float
    price_range_max: float
    reasoning: str
    similar_listings: list[SimilarListingSummary] = []
    external_references: list[ExternalReference] = []
    recommendation: str
