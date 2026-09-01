"""
Cravin — Auth API Routes
Registration, login, and session management for all three user types.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.schemas.user import UserRegister, UserLogin, UserOnboarding, UserProfile, TokenResponse
from app.schemas.baker import BakerRegister
from app.services.auth_service import (
    register_user, authenticate_user, create_access_token,
    get_current_user, hash_password,
)
from app.models.user import User
from app.models.baker import Baker, BakerStatus
from app.models.admin import Admin
from app.models.loyalty import LoyaltyAccount
from app.services.loyalty_service import process_referral

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new customer account."""
    user = await register_user(data.email, data.password, data.full_name, data.phone, "customer", db)
    token = create_access_token(user.id, user.role)

    # Set cookie for server-rendered pages
    response.set_cookie("access_token", token, httponly=True, max_age=86400, samesite="lax")

    return TokenResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    """Login for any user type (customer, baker, admin)."""
    user = await authenticate_user(data.email, data.password, db)

    # If baker, check they're approved
    if user.role == "baker":
        result = await db.execute(select(Baker).where(Baker.user_id == user.id))
        baker = result.scalar_one_or_none()
        if baker and baker.status != BakerStatus.APPROVED.value:
            raise HTTPException(status_code=403, detail=f"Baker application status: {baker.status}. Please wait for approval.")

    token = create_access_token(user.id, user.role)
    response.set_cookie("access_token", token, httponly=True, max_age=86400, samesite="lax")

    return TokenResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


@router.post("/baker/register")
async def register_baker(data: BakerRegister, db: AsyncSession = Depends(get_db)):
    """Register a new baker application."""
    user = await register_user(data.email, data.password, data.full_name, data.phone, "baker", db)

    GOA_COORDS = {
        "panjim": (15.4909, 73.8278),
        "margao": (15.2736, 73.9580),
        "ponda": (15.4026, 74.0086),
    }
    area_key = (data.area or "").strip().lower()
    lat, lng = GOA_COORDS.get(area_key, (15.4909, 73.8278))

    baker = Baker(
        id=str(uuid.uuid4()),
        user_id=user.id,
        business_name=data.business_name,
        bio=data.bio,
        skills=data.skills,
        specialties=data.specialties,
        fssai_number=data.fssai_number,
        city=data.city or "Goa",
        area=data.area or "Panjim",
        latitude=lat,
        longitude=lng,
        delivery_radius_km=data.delivery_radius_km or 15.0,
        max_daily_orders=data.max_daily_orders,
        status=BakerStatus.APPLIED.value,
    )
    db.add(baker)

    return {"message": "Application submitted! We'll review it and get back to you soon.", "status": "applied"}


@router.post("/onboarding")
async def complete_onboarding(
    data: UserOnboarding,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save onboarding data (Flavor DNA quiz, dietary prefs, allergies, calorie goal)."""
    user.dietary_prefs = data.dietary_prefs
    user.allergies = data.allergies
    user.calorie_goal = data.calorie_goal
    user.flavor_profile = data.flavor_profile
    user.city = data.city
    user.address = data.address
    user.onboarding_complete = True

    return {"message": "Onboarding complete! Welcome to Cravin 🎉"}


@router.post("/referral/{code}")
async def apply_referral(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply a referral code during signup."""
    result = await process_referral(code, user.id, db)
    return result


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserProfile.model_validate(user)


@router.api_route("/logout", methods=["GET", "POST"])
async def logout(response: Response):
    """Clear auth cookie and redirect to login page."""
    res = RedirectResponse(url="/app/login", status_code=303)
    res.delete_cookie("access_token", path="/")
    return res
