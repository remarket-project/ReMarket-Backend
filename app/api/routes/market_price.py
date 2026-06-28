import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.models.listing import Listing
from app.schemas.market_price import (
    MarketAnalysisResponse,
    PriceSuggestionRequest,
    PriceSuggestionResponse,
)
from app.services.market_price import (
    get_market_analysis,
    get_price_suggestion,
)

router = APIRouter(prefix="/market-price", tags=["Market Price"])


@router.post("/suggest", response_model=PriceSuggestionResponse)
async def suggest_price(
    db: SessionDep,
    current_user: CurrentUser,
    body: PriceSuggestionRequest,
):
    result = await get_price_suggestion(
        db=db,
        category_id=body.category_id,
        condition_grade=body.condition_grade,
        title=body.title,
        description=body.description,
    )
    return result


@router.get("/analyze/{listing_id}", response_model=MarketAnalysisResponse)
async def analyze_price(
    db: SessionDep,
    current_user: CurrentUser,
    listing_id: uuid.UUID,
):
    from sqlalchemy import select

    stmt = select(Listing).where(Listing.id == listing_id)
    row = await db.execute(stmt)
    listing = row.scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy listing")

    result = await get_market_analysis(
        db=db,
        listing_id=listing_id,
        listing=listing,
    )
    return result
