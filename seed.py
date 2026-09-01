"""
Cravin — Database Seeder
Seeds: 10 desserts, 3 demo bakers, 1 admin, 2 demo customers with loyalty accounts.
Run: python seed.py
"""

import asyncio
import json
import uuid
import os
import sys

# Fix Windows console encoding for emojis
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, async_session, Base
from app.models import *
from app.services.auth_service import hash_password, generate_referral_code
from app.services.nutrition_engine import calculate_recipe_nutrition


async def seed():
    """Seed the database with demo data."""
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        print("🌱 Seeding Cravin database...")

        # ── 1. Admin User ──
        admin_user = User(
            id=str(uuid.uuid4()), email="admin@cravin.in", password_hash=hash_password("admin123"),
            full_name="Cravin Admin", role="admin", is_active=True, onboarding_complete=True,
        )
        db.add(admin_user)
        admin = Admin(id=str(uuid.uuid4()), user_id=admin_user.id, role="super_admin",
                      permissions={"baker_approval": True, "recipe_moderation": True, "analytics": True})
        db.add(admin)
        print("  ✅ Admin: admin@cravin.in / admin123")

        # ── 2. Demo Customers ──
        customers = []
        for i, (name, email, area, lat, lng) in enumerate([
            ("Priya Sharma", "priya@example.com", "Panjim", 15.4909, 73.8278),
            ("Arjun Patel", "arjun@example.com", "Margao", 15.2736, 73.9580),
        ]):
            user = User(
                id=str(uuid.uuid4()), email=email, password_hash=hash_password("demo123"),
                full_name=name, role="customer", is_active=True, onboarding_complete=True,
                city="Goa", address=f"Near Municipal Garden, {area}, Goa",
                latitude=lat, longitude=lng,
                calorie_goal=1800 + i * 200,
                allergies=[["nuts"], []][i],
                dietary_prefs={"vegan": False, "eggless": i == 0, "gluten_free": False},
                flavor_profile={"sweet_vs_rich": 0.6 + i * 0.1, "texture": ["creamy", "crunchy"][i],
                                "adventurousness": 0.7, "favorite_flavors": ["chocolate", "mango"]},
            )
            db.add(user)
            loyalty = LoyaltyAccount(
                id=str(uuid.uuid4()), user_id=user.id,
                referral_code=generate_referral_code(),
                points_balance=50 + i * 30, lifetime_points=100 + i * 50,
                current_streak=2 + i, tier="bronze",
                badges=["first_order"],
            )
            db.add(loyalty)
            customers.append(user)
        print("  ✅ Customers: priya@example.com, arjun@example.com / demo123")

        # ── 3. Demo Bakers ──
        baker_data = [
            ("Meera's Kitchen", "Meera Iyer", "meera@example.com", "Goa", "Panjim",
             ["eggless", "sugar-free", "Indian sweets"], ["barfi", "ladoo", "halwa"],
             15.4909, 73.8278, 20.0, 35),
            ("The Healthy Baker", "Rohan Singh", "rohan@example.com", "Goa", "Margao",
             ["chocolate specialist", "sugar-free", "vegan"], ["brownies", "cakes", "cookies"],
             15.2736, 73.9580, 20.0, 45),
            ("Amma's Treats", "Lakshmi Nair", "lakshmi@example.com", "Goa", "Ponda",
             ["eggless", "sugar-free", "South Indian", "Goan treats"], ["payasam", "ladoo", "halwa", "bebinca"],
             15.4026, 74.0086, 20.0, 40),
        ]
        bakers = []
        for bname, name, email, city, area, skills, specialties, lat, lng, radius, prep_time in baker_data:
            user = User(
                id=str(uuid.uuid4()), email=email, password_hash=hash_password("baker123"),
                full_name=name, role="baker", is_active=True, onboarding_complete=True, city=city,
                address=f"{area}, Goa", latitude=lat, longitude=lng,
            )
            db.add(user)
            baker = Baker(
                id=str(uuid.uuid4()), user_id=user.id, business_name=bname,
                bio=f"Passionate home baker specializing in healthy, zero-sugar treats.",
                skills=skills, specialties=specialties,
                fssai_number=f"1234567890{len(bakers) + 1:04d}", fssai_verified=True,
                city=city, area=area,
                latitude=lat, longitude=lng, delivery_radius_km=radius,
                avg_prep_time_mins=prep_time,
                status="approved", avg_rating=4.5 + len(bakers) * 0.1,
                total_orders_completed=20 + len(bakers) * 10,
                total_earnings=15000 + len(bakers) * 5000,
                accepts_ai_custom_orders=True,
            )
            db.add(baker)
            bakers.append(baker)
        print("  ✅ Bakers: meera@, rohan@, lakshmi@ / baker123")

        # ── 4. Seed Desserts ──
        data_dir = os.path.join(os.path.dirname(__file__), "app", "data")
        with open(os.path.join(data_dir, "seed_desserts.json"), "r", encoding="utf-8") as f:
            dessert_data = json.load(f)

        for i, d in enumerate(dessert_data):
            # Calculate nutrition using the engine
            nutrition = calculate_recipe_nutrition(
                d["base_ingredients"],
                servings=d.get("servings_per_recipe", 1),
            )

            dessert = Dessert(
                id=str(uuid.uuid4()),
                name=d["name"],
                description=d["description"],
                short_description=d["short_description"],
                image_url=d.get("image_url", ""),
                base_ingredients=d["base_ingredients"],
                recipe_steps=d.get("recipe_steps", []),
                serving_size_g=d.get("serving_size_g", 100),
                servings_per_recipe=d.get("servings_per_recipe", 1),
                calories=nutrition["per_serving"]["calories"],
                protein_g=nutrition["per_serving"]["protein_g"],
                carbs_g=nutrition["per_serving"]["carbs_g"],
                fat_g=nutrition["per_serving"]["fat_g"],
                fiber_g=nutrition["per_serving"]["fiber_g"],
                sugar_equivalent_g=nutrition["per_serving"]["sugar_equivalent_g"],
                full_nutrition=nutrition,
                tag=nutrition["tag"],
                allergens=nutrition["allergens"],
                dietary_flags=d.get("dietary_flags", []),
                price=d.get("price", 299),
                is_signature=True,
                is_active=True,
                approval_status="approved",
                baker_id=bakers[i % len(bakers)].id,
                order_count=50 - i * 4,
            )
            db.add(dessert)
            print(f"  🍰 {d['name']} — {nutrition['per_serving']['calories']:.0f} cal ({nutrition['tag']})")

        await db.commit()
        print("\n✨ Database seeded successfully!")
        print("\n📱 Start the server: uvicorn app.main:app --reload --port 8000")
        print("   Customer: http://localhost:8000/app/")
        print("   Baker:    http://localhost:8000/baker/")
        print("   Admin:    http://localhost:8000/admin/")


if __name__ == "__main__":
    asyncio.run(seed())
