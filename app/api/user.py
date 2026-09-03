"""
Cravin — User Profile API Routes
Manage user profile details, email, and target macro parameters.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/user", tags=["user"])


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, min_length=5, max_length=255)
    calorie_goal: Optional[float] = Field(None, ge=500, le=10000)
    protein_goal: Optional[float] = Field(None, ge=10, le=500)


@router.get("/profile")
async def get_user_profile(user: User = Depends(get_current_user)):
    """Get current user's profile and macro goals."""
    dietary_prefs = user.dietary_prefs or {}
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "calorie_goal": user.calorie_goal or 1800.0,
        "protein_goal": dietary_prefs.get("protein_goal", 50.0),
        "allergies": user.allergies or [],
    }


@router.api_route("/profile", methods=["PATCH", "PUT"])
async def update_user_profile(
    data: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's profile information and nutritional goals."""
    if data.full_name is not None and data.full_name.strip():
        user.full_name = data.full_name.strip()

    if data.email is not None and data.email.strip():
        new_email = data.email.strip().lower()
        if new_email != user.email:
            # Check for duplicate email across other accounts
            result = await db.execute(select(User).where(User.email == new_email, User.id != user.id))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This email is already in use by another account.",
                )
            user.email = new_email

    if data.calorie_goal is not None:
        user.calorie_goal = float(data.calorie_goal)

    if data.protein_goal is not None:
        prefs = dict(user.dietary_prefs or {})
        prefs["protein_goal"] = float(data.protein_goal)
        user.dietary_prefs = prefs

    await db.commit()
    await db.refresh(user)

    dietary_prefs = user.dietary_prefs or {}
    return {
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "calorie_goal": user.calorie_goal,
            "protein_goal": dietary_prefs.get("protein_goal", 50.0),
        },
    }
