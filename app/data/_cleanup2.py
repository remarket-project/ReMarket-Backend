from app.core.db import engine
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from app.models.listing import Listing, ListingImage

with Session(engine) as sess:
    rows = sess.execute(text("""
        SELECT DISTINCT l.id
        FROM listings l
        JOIN listing_images li ON li.listing_id = l.id
        WHERE li.image_url LIKE '%dummyjson%'
    """)).all()
    ids = [str(r[0]) for r in rows]
    print(f"Found {len(ids)} dummyjson listings to delete")

    for lid in ids:
        sess.execute(text("DELETE FROM listing_images WHERE listing_id = :id"), {"id": lid})
        sess.execute(text("DELETE FROM listings WHERE id = :id"), {"id": lid})
    sess.commit()

    remaining = sess.execute(select(func.count()).select_from(Listing)).scalar_one()
    imgs = sess.execute(select(func.count()).select_from(ListingImage)).scalar_one()
    print(f"Remaining: {remaining} listings, {imgs} images")
