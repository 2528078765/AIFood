import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    wechat_code: str = Field(..., min_length=1)
    nickname: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    id: uuid.UUID
    nickname: str | None = None
    avatar_url: str | None = None
    gender: str | None = None
    birthday: date | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    fitness_goal: str | None = None
    daily_calorie_target: int | None = None
    exercise_details: str | None = None
    allergies: list[str] = []
    dietary_restrictions: list[str] = []

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)
    height_cm: float | None = Field(default=None, gt=0)
    weight_kg: float | None = Field(default=None, gt=0)
    fitness_goal: str | None = Field(
        default=None, pattern="^(lose_fat|build_muscle|maintain)$"
    )
    allergies: list[str] | None = None
    dietary_restrictions: list[str] | None = None
    exercise_details: str | None = Field(default=None, max_length=1024)
    birthday: date | None = None
    gender: str | None = Field(default=None, pattern="^(male|female)$")

    @model_validator(mode="after")
    def birthday_not_future(self) -> "ProfileUpdate":
        if self.birthday and self.birthday > date.today():
            raise ValueError("Birthday cannot be in the future")
        return self
