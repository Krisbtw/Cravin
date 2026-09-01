"""
Cravin — Baker Model
Home bakers: Instagram/WhatsApp bakers getting steady income through the platform.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Float, Integer, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class BakerStatus(str, enum.Enum):
    APPLIED = "applied"
    UNDER_REVIEW = "under_review"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class Baker(Base):
    __tablename__ = "bakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)

    # Professional info
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. ["eggless", "sugar-free", "vegan", "chocolate specialist", "Indian sweets"]
    specialties: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. ["brownies", "barfi", "cheesecake", "ladoo"]

    # Certifications & compliance
    fssai_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fssai_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Kitchen details (photos stored as paths/URLs)
    kitchen_photos: Mapped[list] = mapped_column(JSON, default=list)
    sample_photos: Mapped[list] = mapped_column(JSON, default=list)

    # Location & availability
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=5.0)
    availability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g. {"mon": {"start": "09:00", "end": "18:00"}, "tue": {...}, ...}
    accepts_ai_custom_orders: Mapped[bool] = mapped_column(Boolean, default=True)
    max_daily_orders: Mapped[int] = mapped_column(Integer, default=10)

    # Status & ratings
    status: Mapped[str] = mapped_column(String(30), default=BakerStatus.APPLIED.value)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_orders_completed: Mapped[int] = mapped_column(Integer, default=0)
    avg_prep_time_mins: Mapped[int] = mapped_column(Integer, default=45)

    # Financials
    total_earnings: Mapped[float] = mapped_column(Float, default=0.0)
    pending_payout: Mapped[float] = mapped_column(Float, default=0.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="baker", lazy="selectin")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="baker", lazy="selectin")
    desserts: Mapped[list["Dessert"]] = relationship("Dessert", back_populates="baker", lazy="selectin")

    def __repr__(self):
        return f"<Baker {self.business_name} ({self.status})>"


class BakerApplication(Base):
    """Tracks the application process separately for audit purposes."""
    __tablename__ = "baker_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    baker_id: Mapped[str] = mapped_column(String(36), ForeignKey("bakers.id"))
    status: Mapped[str] = mapped_column(String(30), default=BakerStatus.APPLIED.value)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # admin user_id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    baker: Mapped["Baker"] = relationship("Baker", lazy="selectin")
