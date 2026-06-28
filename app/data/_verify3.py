from app.core.db import engine
from sqlmodel import Session, text

with Session(engine) as sess:
    rows = sess.execute(text("""
        SELECT l.title, l.description, li.image_url, c.name
        FROM listings l
        JOIN categories c ON c.id = l.category_id
        JOIN listing_images li ON li.listing_id = l.id AND li.is_primary = true
        WHERE li.image_url LIKE '%dummyjson%'
        ORDER BY l.created_at DESC
        LIMIT 12
    """)).all()
    print(f"Sample of {len(rows)} Vietnamese listings:")
    for title, desc, url, cat in rows:
        print(f"  [{cat}] {title}")
        print(f"    Desc: {str(desc)[:80]}...")
        print(f"    URL:  {url[:60]}...")
        print()
