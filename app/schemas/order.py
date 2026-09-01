"""
Cravin — Order Schemas
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CartItem(BaseModel):
    dessert_id: str
    quantity: int = 1
    customization: Optional[dict] = None


class CreateOrder(BaseModel):
    items: list[CartItem]
    fulfillment_type: str = "delivery"  # delivery, pickup
    baker_id: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    delivery_notes: Optional[str] = None
    payment_method: str = "upi"
    redeem_points: int = 0


class BakerMatchRequest(BaseModel):
    items: list[CartItem] = []
    required_skills: list[str] = []
    city: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None


class OrderResponse(BaseModel):
    id: str
    order_number: str
    status: str
    fulfillment_type: str
    payment_status: str
    subtotal: float
    delivery_fee: float
    discount: float
    total_amount: float
    total_calories: float
    delivery_address: Optional[str] = None
    estimated_delivery_mins: Optional[int] = None
    loyalty_points_earned: int
    placed_at: datetime
    baker_name: Optional[str] = None
    items: list[dict] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str
