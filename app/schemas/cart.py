from pydantic import BaseModel
from typing import List, Optional

class CartModifierRequest(BaseModel):
    modifier_id: str
    quantity: int = 1

class CartItemRequest(BaseModel):
    dessert_id: str
    quantity: int = 1
    modifiers: List[CartModifierRequest] = []

class MacroEstimate(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fats_g: float

class DetectedFood(BaseModel):
    name: str
    confidence: float
    macros: MacroEstimate
