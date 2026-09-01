"""
Cravin — Dessert Model
Every dessert: zero added sugar, zero maida, full nutrition panel.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Boolean, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Dessert(Base):
    __tablename__ = "desserts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    short_description: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Recipe
    base_ingredients: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. [{"name": "ragi flour", "quantity_g": 100}, {"name": "dates", "quantity_g": 80}, ...]
    recipe_steps: Mapped[list] = mapped_column(JSON, default=list)
    serving_size_g: Mapped[float] = mapped_column(Float, default=100.0)
    servings_per_recipe: Mapped[int] = mapped_column(Integer, default=1)

    # Computed nutrition (per serving) — calculated by nutrition engine, NOT LLM
    calories: Mapped[float] = mapped_column(Float, default=0.0)
    protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    fat_g: Mapped[float] = mapped_column(Float, default=0.0)
    fiber_g: Mapped[float] = mapped_column(Float, default=0.0)
    sugar_equivalent_g: Mapped[float] = mapped_column(Float, default=0.0)
    # Full nutrition JSON for the detail panel
    full_nutrition: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Classification
    tag: Mapped[str] = mapped_column(String(20), default="balanced")  # light, balanced, heavy
    allergens: Mapped[list] = mapped_column(JSON, default=list)  # ["nuts", "dairy", "gluten"]
    dietary_flags: Mapped[list] = mapped_column(JSON, default=list)  # ["vegan", "eggless", "gluten-free"]

    # Pricing
    price: Mapped[float] = mapped_column(Float, default=0.0)  # INR

    # AI & moderation
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="approved")
    # pending, approved, rejected — AI desserts start as pending
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Baker (null for platform-level signature desserts)
    baker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bakers.id"), nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_signature: Mapped[bool] = mapped_column(Boolean, default=False)  # platform signature items
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    baker: Mapped["Baker | None"] = relationship("Baker", back_populates="desserts", lazy="selectin")
    ingredients: Mapped[list["DessertIngredient"]] = relationship("DessertIngredient", back_populates="dessert", lazy="selectin")
    modifiers: Mapped[list["DessertModifier"]] = relationship("DessertModifier", back_populates="dessert", lazy="selectin")

    def __repr__(self):
        return f"<Dessert {self.name} ({self.tag}, {self.calories:.0f} cal)>"


class DessertIngredient(Base):
    """Individual ingredient in a dessert — links to nutrition DB for computation."""
    __tablename__ = "dessert_ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dessert_id: Mapped[str] = mapped_column(String(36), ForeignKey("desserts.id"))
    ingredient_name: Mapped[str] = mapped_column(String(100))  # matches nutrition_db.json key
    quantity_g: Mapped[float] = mapped_column(Float)
    is_approved_sweetener: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved_flour: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(50), default="other")
    # sweetener, flour, dairy, protein, fat, flavoring, other

    dessert: Mapped["Dessert"] = relationship("Dessert", back_populates="ingredients", lazy="selectin")


class DessertModifier(Base):
    __tablename__ = "dessert_modifiers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dessert_id: Mapped[str] = mapped_column(String(36), ForeignKey("desserts.id"))
    name: Mapped[str] = mapped_column(String(200)) # e.g., "Swap sugar for Stevia"
    price_delta: Mapped[float] = mapped_column(Float, default=0.0) # INR
    allergen_adds: Mapped[list] = mapped_column(JSON, default=list)
    allergen_removes: Mapped[list] = mapped_column(JSON, default=list)
    
    dessert: Mapped["Dessert"] = relationship("Dessert", back_populates="modifiers", lazy="selectin")
