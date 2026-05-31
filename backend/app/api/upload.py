import uuid
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.common import APIResponse
from app.utils.security import get_current_user

router = APIRouter(prefix=f"{settings.api_prefix}/upload", tags=["upload"])

UPLOAD_DIR = Path("/app/static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("", response_model=APIResponse)
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传图片到本地存储，返回可访问的 URL."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Only image files are allowed")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="File size must be under 10MB")

    ext = Path(file.filename).suffix if file.filename else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    user_dir = UPLOAD_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    filepath = user_dir / filename
    filepath.write_bytes(contents)

    image_url = f"https://aifood-264055-6-1409000155.sh.run.tcloudbase.com/static/uploads/{user.id}/{filename}"
    return APIResponse.success(data={"image_url": image_url})
