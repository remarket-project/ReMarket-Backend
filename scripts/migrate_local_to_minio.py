"""Migrate local filesystem images to MinIO"""
import asyncio
import mimetypes
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.services.minio_service import get_minio_service
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

LOCAL_DIR = os.path.abspath(os.path.join(settings.UPLOAD_DIR, "listings"))


def _guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


async def migrate():
    print(f"Database: {DATABASE_URL}")
    print(f"Local dir: {LOCAL_DIR}")
    print(f"use_minio: {settings.use_minio}")
    print(f"MINIO_PUBLIC_ENDPOINT: {settings.MINIO_PUBLIC_ENDPOINT}")

    if not settings.use_minio:
        print("ERROR: MinIO is not configured. Check MINIO_* env vars.")
        sys.exit(1)

    minio = get_minio_service()
    if not minio:
        print("ERROR: Failed to initialize MinIO service.")
        sys.exit(1)

    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, listing_id, image_url FROM listing_images WHERE image_url LIKE '/uploads/%'")
        )
        rows = result.fetchall()

        if not rows:
            print("No local images found to migrate.")
            return

        print(f"Found {len(rows)} local images to migrate.")

        for row in rows:
            img_id, listing_id, image_url = row
            # image_url = /uploads/listings/uuid.ext
            filename = os.path.basename(image_url)
            local_path = os.path.join(LOCAL_DIR, filename)

            if not os.path.isfile(local_path):
                print(f"  WARN: File not found: {local_path}")
                continue

            with open(local_path, "rb") as f:
                file_data = f.read()

            object_path = f"listings/{listing_id}/{filename}"
            new_url = minio.upload_file(
                object_path,
                file_data,
                content_type=_guess_mime(filename),
            )

            await conn.execute(
                text("UPDATE listing_images SET image_url = :new_url WHERE id = :img_id"),
                {"new_url": new_url, "img_id": img_id},
            )
            print(f"  OK: {image_url} -> {new_url}")

        await conn.commit()
        print(f"\nMigrated {len(rows)} images successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
