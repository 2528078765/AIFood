import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.food import FoodItem


class Ingredient(BaseModel):
    name: str
    amount_g: float


class NutritionPerServing(BaseModel):
    calories: int
    protein_g: float
    fat_g: float
    carbs_g: float


class RecipeItem(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None = None
    meal_type: str | None = None
    cooking_method: str | None = None
    prep_time_min: int | None = None
    cook_time_min: int | None = None
    difficulty: str | None = None
    image_url: str | None = None
    ingredients: list[Ingredient] = []
    steps: list[str] = []
    nutrition_per_serving: NutritionPerServing
    serving_size: str | None = None
    tags: list[str] = []
    suitable_goal: str | None = None

    model_config = {"from_attributes": True}


class DailyMeals(BaseModel):
    breakfast: list[RecipeItem] = []
    lunch: list[RecipeItem] = []
    dinner: list[RecipeItem] = []
