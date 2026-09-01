"""
Cravin — Loyalty Schemas
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoyaltyAccountResponse(BaseModel):
    points_balance: int
    lifetime_points: int
    current_streak: int
    longest_streak: int
    tier: str
    referral_code: str
    referral_count: int
    badges: list[str] = []

    class Config:
        from_attributes = True


class LoyaltyTransactionResponse(BaseModel):
    type: str
    points: int
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class RedeemPoints(BaseModel):
    points: int
    order_id: Optional[str] = None
