import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FitnessCheckin(Base):
    __tablename__ = "fitness_checkins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    exercise_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_min: Mapped[int] = mapped_column(nullable=False)
    intensity: Mapped[int | None]
    calories_burned: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    checkin_date: Mapped[date] = mapped_column(Date, default=date.today)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("intensity BETWEEN 1 AND 10", name="ck_intensity_range"),
    )
