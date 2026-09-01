"""
Cravin — Review Model
Ratings and reviews per baker and per dessert.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    baker_id: Mapped[str] = mapped_column(String(36), ForeignKey("bakers.id"))
    dessert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("desserts.id"), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)

    rating: Mapped[int] = mapped_column(Integer)  # 1-5 stars
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="reviews", lazy="selectin")
    baker: Mapped["Baker"] = relationship("Baker", back_populates="reviews", lazy="selectin")
