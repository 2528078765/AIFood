import uuid
from datetime import date, datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    wechat_openid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    wechat_unionid: Mapped[str | None] = mapped_column(String(128))
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(String(8))
    birthday: Mapped[date | None]
    height_cm: Mapped[float | None]
    weight_kg: Mapped[float | None]
    fitness_goal: Mapped[str | None] = mapped_column(String(16))
    daily_calorie_target: Mapped[int | None]
    exercise_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[list | None] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list | None] = mapped_column(JSON, default=list)
    free_tokens_remaining: Mapped[int | None] = mapped_column(default=1_000_000)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
