import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(20))
    meal_type: Mapped[str | None] = mapped_column(String(10))
    cooking_method: Mapped[str | None] = mapped_column(String(20))
    prep_time_min: Mapped[int | None]
    cook_time_min: Mapped[int | None]
    difficulty: Mapped[str | None] = mapped_column(String(10))
    image_url: Mapped[str | None] = mapped_column(Text)
    ingredients: Mapped[dict] = mapped_column(JSON, default=list)
    steps: Mapped[list | None] = mapped_column(JSON, default=list)
    nutrition_per_serving: Mapped[dict] = mapped_column(JSON, default=dict)
    serving_size: Mapped[str | None] = mapped_column(String(30))
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    suitable_goal: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class RecipeRecommendation(Base):
    __tablename__ = "recipe_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_accepted: Mapped[bool | None]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "date", "meal_type", "recipe_id"),
    )
