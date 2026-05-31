import uuid

from pydantic import BaseModel


class FoodItem(BaseModel):
    name: str
    calories_per_100g: float | None = None
    estimated_weight_g: float | None = None
    estimated_calories: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbs_g: float | None = None


class FoodRecordResponse(BaseModel):
    id: uuid.UUID
    image_url: str | None = None
    meal_type: str | None = None
    foods: list[FoodItem]
    total_calories: int
    total_protein_g: float | None = None
    total_fat_g: float | None = None
    total_carbs_g: float | None = None
    recorded_at: str
    created_at: str

    model_config = {"from_attributes": True}


class NutritionSearchResult(BaseModel):
    name: str
    calories_per_100g: float
    protein_g: float
    fat_g: float
    carbs_g: float
