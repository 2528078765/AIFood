import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class CheckinRequest(BaseModel):
    exercise_type: str = Field(..., pattern="^(running|swimming|weightlifting|yoga|cycling|hiit|other)$")
    duration_min: int = Field(..., gt=0)
    intensity: int | None = Field(default=None, ge=1, le=10)
    calories_burned: int | None = None
    notes: str | None = None
    checkin_date: date | None = None


class CheckinResponse(BaseModel):
    id: uuid.UUID
    exercise_type: str
    duration_min: int
    intensity: int | None = None
    calories_burned: int | None = None
    notes: str | None = None
    checkin_date: str
    created_at: str

    model_config = {"from_attributes": True}


class FitnessStats(BaseModel):
    total_days: int
    total_minutes: int
    exercises: dict[str, int]  # exercise_type -> count


class StreakResponse(BaseModel):
    streak_days: int
