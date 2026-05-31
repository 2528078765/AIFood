from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.fitness import FitnessCheckin
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.fitness import CheckinRequest
from app.services import fitness_service
from app.utils.security import get_current_user

router = APIRouter(prefix=f"{settings.api_prefix}/fitness", tags=["fitness"])


@router.post("/checkin", response_model=APIResponse)
async def checkin(
    req: CheckinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交健身打卡."""
    record = FitnessCheckin(
        user_id=user.id,
        exercise_type=req.exercise_type,
        duration_min=req.duration_min,
        intensity=req.intensity,
        calories_burned=req.calories_burned,
        notes=req.notes,
        checkin_date=req.checkin_date or date.today(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return APIResponse.success(
        data={
            "id": str(record.id),
            "exercise_type": record.exercise_type,
            "duration_min": record.duration_min,
            "intensity": record.intensity,
            "calories_burned": record.calories_burned,
            "notes": record.notes,
            "checkin_date": str(record.checkin_date),
            "created_at": str(record.created_at),
        }
    )


@router.get("/records", response_model=APIResponse)
async def get_records(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询时间段打卡记录."""
    if start_date and end_date and start_date > end_date:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="start_date must be before end_date")

    if not start_date:
        start_date = date.today() - timedelta(days=date.today().weekday())
    if not end_date:
        end_date = date.today()

    records = await fitness_service.get_records(str(user.id), start_date, end_date, db)
    return APIResponse.success(data=records)


@router.get("/stats", response_model=APIResponse)
async def get_stats(
    period: str = Query(default="week", pattern="^(week|month)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """周/月运动统计."""
    stats = await fitness_service.get_stats(str(user.id), period, db)
    return APIResponse.success(data=stats)


@router.get("/streak", response_model=APIResponse)
async def get_streak(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """计算当前连续打卡天数."""
    streak = await fitness_service.get_streak(str(user.id), db)
    return APIResponse.success(data={"streak_days": streak})
