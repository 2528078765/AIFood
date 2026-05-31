from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import auth, chat, fitness, food, recipe, settings, upload
from app.config import settings as app_settings
from app.database import engine, get_db
from app.models.base import Base
from app.models.food_record import FoodRecord
from app.models.user import User
from app.schemas.common import APIResponse
from app.services import fitness_service
from app.utils.security import get_current_user

import logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add missing columns for existing DBs
        from sqlalchemy import text
        for col, spec in [("exercise_details", "TEXT")]:
            try:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {spec}"))
                logger.info(f"Added column: users.{col}")
            except Exception:
                pass
    logger.info("Database tables created/verified")

    # Auto-seed recipes if table is empty
    from app.database import async_session
    from app.models.recipe import Recipe
    from sqlalchemy import select, func
    async with async_session() as db:
        count = (await db.execute(select(func.count()).select_from(Recipe))).scalar()
        if count == 0:
            try:
                from scripts.seed_recipes import RECIPES
                for r in RECIPES:
                    db.add(Recipe(**r))
                await db.commit()
                logger.info(f"Seeded {len(RECIPES)} recipes")
            except Exception as e:
                logger.warning(f"Recipe seeding skipped: {e}")

    yield


app = FastAPI(
    title="AIFood API",
    version="0.1.0",
    docs_url="/docs" if app_settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded images
import os
os.makedirs("/app/static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Routes
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(food.router)
app.include_router(recipe.router)
app.include_router(fitness.router)
app.include_router(settings.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get(f"{app_settings.api_prefix}/dashboard", response_model=APIResponse)
async def dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """仪表盘聚合数据."""
    from datetime import date

    from sqlalchemy import func, select

    from app.models.fitness import FitnessCheckin

    today = date.today()

    # Today's food calories
    food_result = await db.execute(
        select(func.coalesce(func.sum(FoodRecord.total_calories), 0)).where(
            FoodRecord.user_id == user.id, FoodRecord.recorded_at == today
        )
    )
    consumed = food_result.scalar() or 0

    # Today's checkin status
    checkin_result = await db.execute(
        select(FitnessCheckin).where(
            FitnessCheckin.user_id == user.id, FitnessCheckin.checkin_date == today
        )
    )
    checked_in_today = checkin_result.scalar_one_or_none() is not None

    # Streak — delegated to fitness service
    streak = await fitness_service.get_streak(str(user.id), db)

    # Week stats — delegated to fitness service
    week_stats = await fitness_service.get_stats(str(user.id), "week", db)

    # Meals — try recipe_service, fall back to placeholder
    try:
        from app.services import recipe_service

        meals = await recipe_service.get_daily_recommendations(user.id, today, db)
    except (ImportError, AttributeError):
        meals = {"breakfast": None, "lunch": None, "dinner": None}

    return APIResponse.success(
        data={
            "date": str(today),
            "calories": {
                "consumed": consumed,
                "target": user.daily_calorie_target or 2000,
                "percentage": round(consumed / max(user.daily_calorie_target or 2000, 1) * 100, 1),
            },
            "meals": meals,
            "fitness": {
                "checked_in_today": checked_in_today,
                "streak_days": streak,
                "week_stats": week_stats,
            },
        }
    )
