"""
Cravin — Order Model
Full order lifecycle: placed → accepted → preparing → ready → out_for_delivery → delivered.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class OrderStatus(str, enum.Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class FulfillmentType(str, enum.Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    baker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bakers.id"), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.PLACED.value)
    fulfillment_type: Mapped[str] = mapped_column(String(20), default=FulfillmentType.DELIVERY.value)
    payment_status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING.value)

    # Pricing
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)

    # Nutrition totals for the order
    total_calories: Mapped[float] = mapped_column(Float, default=0.0)

    # Delivery
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_delivery_mins: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Payment (Razorpay, mocked for Phase 1)
    payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # UPI, card, etc.

    # Loyalty
    loyalty_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    loyalty_points_redeemed: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders", lazy="selectin")
    baker: Mapped["Baker | None"] = relationship("Baker", back_populates="orders", lazy="selectin")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", lazy="selectin",
                                                      cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.order_number} ({self.status})>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"))
    dessert_id: Mapped[str] = mapped_column(String(36), ForeignKey("desserts.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    calories_per_unit: Mapped[float] = mapped_column(Float, default=0.0)

    # AI customization (if any)
    customization: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g. {"sweetness": "low", "protein_boost": "whey", "excluded": ["nuts"]}
    is_customized: Mapped[bool] = mapped_column(default=False)
    customized_nutrition: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items", lazy="selectin")
    dessert: Mapped["Dessert"] = relationship("Dessert", lazy="selectin")
