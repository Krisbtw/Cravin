"""
Cravin — Admin Model
Ops team: vets bakers, moderates AI recipes, runs analytics.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True)
    role: Mapped[str] = mapped_column(String(50), default="ops")  # ops, super_admin
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    # e.g. {"baker_approval": true, "recipe_moderation": true, "analytics": true}

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self):
        return f"<Admin {self.role} ({self.user_id})>"
