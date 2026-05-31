from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.food_record import FoodRecord
from app.models.user import User
from app.schemas.common import APIResponse
from app.utils.security import get_current_user

router = APIRouter(prefix=f"{settings.api_prefix}/food", tags=["food"])


@router.get("/records")
async def get_records(
    query_date: date | None = Query(default=None, alias="date"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询指定日期的食物记录，默认今天."""
    target_date = query_date or date.today()
    result = await db.execute(
        select(FoodRecord)
        .where(FoodRecord.user_id == user.id, FoodRecord.recorded_at == target_date)
        .order_by(FoodRecord.created_at.desc())
    )
    records = result.scalars().all()
    return APIResponse.success(
        data=[
            {
                "id": str(r.id),
                "image_url": r.image_url,
                "meal_type": r.meal_type,
                "foods": r.foods,
                "total_calories": r.total_calories,
                "total_protein_g": float(r.total_protein_g) if r.total_protein_g is not None else None,
                "total_fat_g": float(r.total_fat_g) if r.total_fat_g is not None else None,
                "total_carbs_g": float(r.total_carbs_g) if r.total_carbs_g is not None else None,
                "recorded_at": str(r.recorded_at),
                "created_at": str(r.created_at),
            }
            for r in records
        ]
    )


@router.get("/search", response_model=APIResponse)
async def search_nutrition(
    keyword: str = Query(..., min_length=1),
    user: User = Depends(get_current_user),
):
    """本地营养数据库关键词搜索."""
    from app.utils.nutrition_db import search_food

    results = search_food(keyword, limit=10)
    return APIResponse.success(data=results)
