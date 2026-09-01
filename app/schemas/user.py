"""
Cravin — User & Auth Schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserOnboarding(BaseModel):
    dietary_prefs: Optional[dict] = None
    allergies: Optional[list[str]] = None
    calorie_goal: Optional[float] = None
    flavor_profile: Optional[dict] = None
    city: Optional[str] = None
    address: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    dietary_prefs: Optional[dict] = None
    allergies: Optional[list[str]] = None
    calorie_goal: Optional[float] = None
    flavor_profile: Optional[dict] = None
    city: Optional[str] = None
    onboarding_complete: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
