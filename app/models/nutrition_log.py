"""
Cravin — Nutrition Log Model
Tracks what users eat against their daily calorie goal.
"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date, default=date.today)
    dessert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("desserts.id"), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)

    # Per-item nutrition consumed
    calories: Mapped[float] = mapped_column(Float, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, default=0.0)
    fiber_g: Mapped[float] = mapped_column(Float, default=0.0)
    sugar_equivalent_g: Mapped[float] = mapped_column(Float, default=0.0)

    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    macros: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="nutrition_logs", lazy="selectin")
