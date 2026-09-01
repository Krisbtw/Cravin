"""
Cravin — Auth Service
JWT authentication with role-based access for Customer / Baker / Admin.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt as _bcrypt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import secrets

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.loyalty import LoyaltyAccount

settings = get_settings()
# Use bcrypt directly (passlib is incompatible with bcrypt>=4.0)
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def generate_referral_code() -> str:
    """Generate a unique 8-char referral code."""
    return "CRAV" + secrets.token_hex(3).upper()


async def register_user(
    email: str, password: str, full_name: str,
    phone: Optional[str], role: str, db: AsyncSession
) -> User:
    """Register a new user with a loyalty account."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        phone=phone,
        role=role,
    )
    db.add(user)
    await db.flush()

    # Create loyalty account for customers
    if role == "customer":
        loyalty = LoyaltyAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            referral_code=generate_referral_code(),
        )
        db.add(loyalty)

    await db.flush()
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    """Authenticate by email + password, return user or raise."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — extracts current user from JWT (header or cookie)."""
    token = None

    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    else:
        # Fall back to cookie (for server-rendered pages)
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    """Dependency factory — restricts access to specific roles."""
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {', '.join(roles)}"
            )
        return user
    return role_checker
