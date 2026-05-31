import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.common import APIResponse
from app.services import recipe_service
from app.utils.security import get_current_user

router = APIRouter(prefix=f"{settings.api_prefix}/recipe", tags=["recipe"])


@router.get("/daily", response_model=APIResponse)
async def get_daily(
    date: date = Query(default_factory=date.today),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取一日三餐推荐."""
    meals = await recipe_service.get_daily_recommendations(
        user_id=str(user.id),
        target_date=date,
        db=db,
    )
    return APIResponse.success(data=meals)


@router.get("/recommend", response_model=APIResponse)
async def recommend_meal(
    date: date = Query(default_factory=date.today),
    meal: str = Query(..., pattern="^(breakfast|lunch|dinner)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单餐推荐."""
    result = await recipe_service.get_meal_recommendation(
        user_id=str(user.id),
        target_date=date,
        meal_type=meal,
        db=db,
    )
    return APIResponse.success(data=result)


@router.get("/generate", response_model=APIResponse)
async def generate_recipe(
    meal: str = Query(..., pattern="^(breakfast|lunch|dinner)$"),
    exercise_details: str | None = Query(default=None, max_length=1024),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 根据用户档案实时生成个性化食谱，可选传入运动详情估算体脂率."""
    # Save exercise_details to profile if provided
    if exercise_details is not None:
        user.exercise_details = exercise_details
        await db.commit()

    from app.services.ai_recipe import generate_recipes
    result = await generate_recipes(
        user_id=str(user.id),
        meal_type=meal,
        db=db,
        exercise_details=exercise_details or user.exercise_details,
    )
    return APIResponse.success(data=result)


@router.get("/{recipe_id}", response_model=APIResponse)
async def get_recipe_detail(
    recipe_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个食谱详情."""
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    return APIResponse.success(
        data={
            "id": str(recipe.id),
            "name": recipe.name,
            "category": recipe.category,
            "meal_type": recipe.meal_type,
            "cooking_method": recipe.cooking_method,
            "prep_time_min": recipe.prep_time_min,
            "cook_time_min": recipe.cook_time_min,
            "difficulty": recipe.difficulty,
            "image_url": recipe.image_url,
            "ingredients": recipe.ingredients,
            "steps": recipe.steps or [],
            "nutrition_per_serving": recipe.nutrition_per_serving,
            "serving_size": recipe.serving_size,
            "tags": recipe.tags or [],
            "suitable_goal": recipe.suitable_goal,
        }
    )
