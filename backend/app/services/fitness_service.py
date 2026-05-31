"""Fitness checkin business logic."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fitness import FitnessCheckin


def _to_uuid(user_id: str) -> uuid.UUID:
    return uuid.UUID(user_id)


async def get_streak(user_id: str, db: AsyncSession) -> int:
    """Calculate consecutive check-in days ending today (or yesterday if today not yet checked)."""
    uid = _to_uuid(user_id)
    today = date.today()
    streak = 0
    check_date = today

    while True:
        result = await db.execute(
            select(FitnessCheckin).where(
                FitnessCheckin.user_id == uid,
                FitnessCheckin.checkin_date == check_date,
            )
        )
        if result.scalar_one_or_none():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    if streak == 0 and check_date == today:
        check_date = today - timedelta(days=1)
        while True:
            result = await db.execute(
                select(FitnessCheckin).where(
                    FitnessCheckin.user_id == uid,
                    FitnessCheckin.checkin_date == check_date,
                )
            )
            if result.scalar_one_or_none():
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

    return streak


async def get_stats(
    user_id: str,
    period: str,
    db: AsyncSession,
) -> dict:
    """Returns {total_days, total_minutes, exercises: {type: count}}."""
    uid = _to_uuid(user_id)
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    else:
        start = today.replace(day=1)

    result = await db.execute(
        select(FitnessCheckin).where(
            FitnessCheckin.user_id == uid,
            FitnessCheckin.checkin_date >= start,
            FitnessCheckin.checkin_date <= today,
        )
    )
    records = result.scalars().all()

    total_days = len({r.checkin_date for r in records})
    total_minutes = sum(r.duration_min for r in records)
    exercises: dict[str, int] = {}
    for r in records:
        exercises[r.exercise_type] = exercises.get(r.exercise_type, 0) + 1

    return {
        "total_days": total_days,
        "total_minutes": total_minutes,
        "exercises": exercises,
    }


async def get_records(
    user_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession,
) -> list[dict]:
    """Returns checkin records in date range."""
    uid = _to_uuid(user_id)
    result = await db.execute(
        select(FitnessCheckin)
        .where(
            FitnessCheckin.user_id == uid,
            FitnessCheckin.checkin_date >= start_date,
            FitnessCheckin.checkin_date <= end_date,
        )
        .order_by(FitnessCheckin.checkin_date.desc())
    )
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "exercise_type": r.exercise_type,
            "duration_min": r.duration_min,
            "intensity": r.intensity,
            "calories_burned": r.calories_burned,
            "notes": r.notes,
            "checkin_date": str(r.checkin_date),
            "created_at": str(r.created_at),
        }
        for r in records
    ]
