"""
Cravin — Dessert Schemas
"""

from pydantic import BaseModel
from typing import Optional


class DessertResponse(BaseModel):
    id: str
    name: str
    description: str
    short_description: str
    image_url: Optional[str] = None
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sugar_equivalent_g: float
    tag: str  # light, balanced, heavy
    allergens: list[str] = []
    dietary_flags: list[str] = []
    price: float
    is_ai_generated: bool
    is_signature: bool

    class Config:
        from_attributes = True


class DessertDetail(DessertResponse):
    base_ingredients: list[dict] = []
    recipe_steps: list[str] = []
    serving_size_g: float
    full_nutrition: Optional[dict] = None
    baker_id: Optional[str] = None
    order_count: int = 0


class CustomizationRequest(BaseModel):
    dessert_id: str
    sweetness: str = "medium"  # low, medium, high
    protein_boost: Optional[str] = None  # whey, pea, none
    exclude_allergens: list[str] = []
    user_message: Optional[str] = None
