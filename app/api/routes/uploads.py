import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services.minio_service import get_minio_service

router = APIRouter(prefix="/upload", tags=["Upload"])

ABS_UPLOAD_DIR = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(ABS_UPLOAD_DIR, exist_ok=True)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("")
async def upload_file(current_user: CurrentUser, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    if settings.use_minio:
        try:
            minio_service = get_minio_service()
            if not minio_service:
                raise RuntimeError("MinIO service not available")
            file_path = f"uploads/{unique_filename}"
            image_url = minio_service.upload_file(
                file_path,
                file_bytes,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}") from e
    else:
        file_path = os.path.abspath(os.path.join(ABS_UPLOAD_DIR, unique_filename))
        if not file_path.startswith(ABS_UPLOAD_DIR + os.sep):
            raise HTTPException(status_code=400, detail="Invalid upload path")
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
        image_url = f"/{settings.UPLOAD_DIR}/{unique_filename}"

    return {"url": image_url}
