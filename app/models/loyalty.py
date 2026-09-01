"""
Cravin — Loyalty Model (Sweet Streak)
Playful loyalty: streaks, tiers, referrals, unlockable badges.
"""

import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class LoyaltyTier(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


# Tier thresholds (total lifetime points)
TIER_THRESHOLDS = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 500,
    LoyaltyTier.GOLD: 2000,
    LoyaltyTier.PLATINUM: 5000,
}


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)

    # Points
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_points: Mapped[int] = mapped_column(Integer, default=0)

    # Sweet Streak
    current_streak: Mapped[int] = mapped_column(Integer, default=0)  # consecutive weeks with orders
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_order_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Tier
    tier: Mapped[str] = mapped_column(String(20), default=LoyaltyTier.BRONZE.value)

    # Referral
    referral_code: Mapped[str] = mapped_column(String(20), unique=True)
    referred_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)

    # Badges (unlockable achievements)
    badges: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. ["first_order", "5_streak", "10_bakers", "customizer_pro", "ragi_lover"]

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="loyalty_account", lazy="selectin")
    transactions: Mapped[list["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", back_populates="account", lazy="selectin"
    )

    def __repr__(self):
        return f"<LoyaltyAccount {self.tier} ({self.points_balance} pts, {self.current_streak} streak)>"


class LoyaltyTransaction(Base):
    """Tracks every points earn/spend event."""
    __tablename__ = "loyalty_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("loyalty_accounts.id"))
    type: Mapped[str] = mapped_column(String(20))  # earn, redeem, bonus, referral
    points: Mapped[int] = mapped_column(Integer)  # positive = earn, negative = spend
    description: Mapped[str] = mapped_column(String(200))
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["LoyaltyAccount"] = relationship("LoyaltyAccount", back_populates="transactions", lazy="selectin")
