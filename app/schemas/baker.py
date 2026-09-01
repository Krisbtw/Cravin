"""
Cravin — Baker Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BakerRegister(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    business_name: Optional[str] = None
    bio: Optional[str] = None
    skills: list[str] = []
    specialties: list[str] = []
    fssai_number: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    delivery_radius_km: float = 5.0
    max_daily_orders: int = 10


class BakerProfile(BaseModel):
    id: str
    user_id: str
    business_name: Optional[str] = None
    bio: Optional[str] = None
    skills: list[str] = []
    specialties: list[str] = []
    fssai_number: Optional[str] = None
    status: str
    avg_rating: float
    total_orders_completed: int
    total_earnings: float
    pending_payout: float
    city: Optional[str] = None
    area: Optional[str] = None
    delivery_radius_km: float
    accepts_ai_custom_orders: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BakerStatusUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None
