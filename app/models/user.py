"""
Cravin — User Model
The Customer: health-conscious, urban India, 20s-30s.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(15), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="customer")  # customer, baker, admin

    # Encrypted PII (AES-256)
    encrypted_phone: Mapped[str | None] = mapped_column(String(500), nullable=True) 
    encrypted_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Onboarding / Flavor DNA
    dietary_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g. {"vegan": false, "eggless": true, "gluten_free": false}
    allergies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # e.g. ["nuts", "dairy", "gluten"]
    calorie_goal: Mapped[float | None] = mapped_column(Float, nullable=True)  # daily kcal target
    flavor_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Flavor DNA quiz results: {"sweet_vs_rich": 0.7, "texture": "creamy", "adventurousness": 0.8, ...}

    # Profile
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user", lazy="selectin")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user", lazy="selectin")
    loyalty_account: Mapped["LoyaltyAccount"] = relationship("LoyaltyAccount", back_populates="user", uselist=False, lazy="selectin")
    nutrition_logs: Mapped[list["NutritionLog"]] = relationship("NutritionLog", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<User {self.full_name} ({self.email})>"
