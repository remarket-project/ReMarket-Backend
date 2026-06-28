from app.core.db import engine
from sqlmodel import Session, text
from sqlalchemy import text as sa_text

with Session(engine) as sess:
    rows = sess.execute(sa_text("""
        SELECT DISTINCT l.id
        FROM listings l
        JOIN listing_images li ON li.listing_id = l.id
        WHERE li.image_url LIKE '%dummyjson%'
    """)).all()
    ids = [str(r[0]) for r in rows]
    print(f"Found {len(ids)} dummyjson listings to delete")

    for lid in ids:
        sess.execute(sa_text("DELETE FROM listing_images WHERE listing_id = :id"), {"id": lid})
        sess.execute(sa_text("DELETE FROM listings WHERE id = :id"), {"id": lid})
    sess.commit()

    remaining = sess.exec(text("SELECT COUNT(*) FROM listings")).scalar()
    imgs = sess.exec(text("SELECT COUNT(*) FROM listing_images")).scalar()
    print(f"Remaining: {remaining} listings, {imgs} images")
