import uuid
from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FoodRecord(Base):
    __tablename__ = "food_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    image_url: Mapped[str | None] = mapped_column(Text)
    meal_type: Mapped[str | None] = mapped_column(String(10))
    foods: Mapped[dict] = mapped_column(JSON, default=list)
    total_calories: Mapped[int]
    total_protein_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    total_fat_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    total_carbs_g: Mapped[float | None] = mapped_column(Numeric(6, 1))
    recorded_at: Mapped[date] = mapped_column(default=date.today)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
