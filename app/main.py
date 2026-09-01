"""
Cravin — Main Application Entry Point
Three apps, one server: Customer (/app), Baker (/baker), Admin (/admin).
"""

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.database import init_db, get_db
from app.models.user import User
from app.models.dessert import Dessert
from app.models.order import Order
from app.models.baker import Baker
from app.models.loyalty import LoyaltyAccount
from app.models.nutrition_log import NutritionLog

# API routers
from app.api.auth import router as auth_router
from app.api.customer import router as customer_router
from app.api.baker import router as baker_router
from app.api.admin import router as admin_router
from app.api.orders import router as orders_router
from app.api.vision import router as vision_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup and auto-seed demo data if empty."""
    try:
        await init_db()
    except Exception as e:
        print(f"Lifespan database init notice (non-fatal): {e}")
    try:
        from app.database import async_session
        from seed import populate_seed_data
        async with async_session() as db:
            await populate_seed_data(db)
    except Exception as e:
        print(f"Auto-seed notice (non-fatal): {e}")
    yield


app = FastAPI(
    title="Cravin",
    description="Zero Sugar, Zero Maida, Full Flavor — AI-powered healthy desserts from home bakers",
    version="1.0.0-mvp",
    lifespan=lifespan,
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# Register API routers
app.include_router(auth_router)
app.include_router(customer_router)
app.include_router(baker_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(vision_router)


# ─── Helper: get current user from cookie (for templates) ───────────

async def get_template_user(request: Request, db: AsyncSession) -> dict | None:
    """Try to get user info from cookie for server-rendered pages."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        from app.services.auth_service import decode_token
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                return {
                    "id": user.id, "email": user.email, "full_name": user.full_name,
                    "role": user.role, "calorie_goal": user.calorie_goal,
                    "allergies": user.allergies, "onboarding_complete": user.onboarding_complete,
                    "city": user.city, "address": user.address,
                }
    except Exception:
        pass
    return None


def TR(request: Request, template: str, context: dict = None):
    """TemplateResponse helper — request must be inside context dict (Starlette <=0.41)."""
    ctx = {"request": request, **(context or {})}
    return templates.TemplateResponse(template, ctx)


# ═══════════════════════════════════════════════════════════════════
# CUSTOMER APP PAGES (/app/...)
# ═══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
async def root():
    """Redirect root to customer app."""
    return RedirectResponse(url="/app/")


@app.get("/api/seed", response_class=HTMLResponse)
async def seed_endpoint(db: AsyncSession = Depends(get_db)):
    from seed import populate_seed_data
    try:
        msg = await populate_seed_data(db)
        return HTMLResponse(content=f"<div style='font-family:sans-serif;padding:2rem;background:#111;color:#fff;min-height:100vh;'><h2>🌱 Seeding Status</h2><p>{msg}</p><p><a href='/app/' style='color:#f59e0b;font-weight:bold;'>👉 Go to Cravin Menu</a></p></div>")
    except Exception as e:
        return HTMLResponse(content=f"<div style='font-family:sans-serif;padding:2rem;background:#111;color:#fff;'><h2>❌ Seeding Error</h2><p>{e}</p></div>", status_code=500)


@app.get("/app/", response_class=HTMLResponse)
async def customer_home(request: Request, db: AsyncSession = Depends(get_db)):
    """Customer home / discover page."""
    user = await get_template_user(request, db)

    result = await db.execute(
        select(Dessert).where(Dessert.is_active == True, Dessert.approval_status == "approved")
        .order_by(Dessert.order_count.desc())
    )
    desserts = result.scalars().all()

    return TR(request, "customer/home.html", {
        "user": user, "desserts": desserts,
        "featured": desserts[:3] if desserts else [],
    })


@app.get("/app/login", response_class=HTMLResponse)
async def customer_login_page(request: Request):
    return TR(request, "customer/login.html")


@app.get("/app/register", response_class=HTMLResponse)
async def customer_register_page(request: Request):
    return TR(request, "customer/register.html")


@app.get("/app/onboarding", response_class=HTMLResponse)
async def customer_onboarding(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")
    return TR(request, "customer/onboarding.html", {"user": user})


@app.get("/app/dessert/{dessert_id}", response_class=HTMLResponse)
async def customer_dessert_detail(dessert_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    result = await db.execute(select(Dessert).where(Dessert.id == dessert_id))
    dessert = result.scalar_one_or_none()
    if not dessert:
        return RedirectResponse(url="/app/")

    # Get baker info if assigned
    baker_info = None
    if dessert.baker_id:
        baker_result = await db.execute(select(Baker).where(Baker.id == dessert.baker_id))
        baker = baker_result.scalar_one_or_none()
        if baker:
            baker_user_result = await db.execute(select(User).where(User.id == baker.user_id))
            baker_user = baker_user_result.scalar_one_or_none()
            baker_info = {
                "name": baker_user.full_name if baker_user else baker.business_name,
                "business_name": baker.business_name,
                "avg_rating": baker.avg_rating,
                "total_orders": baker.total_orders_completed,
            }

    return TR(request, "customer/dessert_detail.html", {
        "user": user, "dessert": dessert, "baker": baker_info,
    })


@app.get("/app/customizer/{dessert_id}", response_class=HTMLResponse)
async def customer_customizer(dessert_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")
    result = await db.execute(select(Dessert).where(Dessert.id == dessert_id))
    dessert = result.scalar_one_or_none()
    if not dessert:
        return RedirectResponse(url="/app/")
    return TR(request, "customer/customizer.html", {"user": user, "dessert": dessert})


@app.get("/app/cart", response_class=HTMLResponse)
async def customer_cart(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    return TR(request, "customer/cart.html", {"user": user})


@app.get("/app/checkout", response_class=HTMLResponse)
async def customer_checkout(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")
    return TR(request, "customer/checkout.html", {"user": user})


@app.get("/app/orders", response_class=HTMLResponse)
async def customer_orders(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    result = await db.execute(
        select(Order).where(Order.user_id == user["id"]).order_by(Order.placed_at.desc())
    )
    orders = result.scalars().all()

    return TR(request, "customer/orders.html", {"user": user, "orders": orders})


@app.get("/app/order/{order_id}", response_class=HTMLResponse)
async def customer_order_tracking(order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    return TR(request, "customer/order_tracking.html", {"user": user, "order": order})


@app.get("/app/rewards", response_class=HTMLResponse)
async def customer_rewards(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == user["id"])
    )
    loyalty = result.scalar_one_or_none()

    return TR(request, "customer/rewards.html", {"user": user, "loyalty": loyalty})


@app.get("/app/profile", response_class=HTMLResponse)
async def customer_profile(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user:
        return RedirectResponse(url="/app/login")

    # Get nutrition logs for today
    from datetime import date
    result = await db.execute(
        select(NutritionLog).where(
            NutritionLog.user_id == user["id"],
            NutritionLog.date == date.today(),
        )
    )
    logs = result.scalars().all()

    from app.services.nutrition_engine import get_daily_nutrition_summary
    nutrition_summary = get_daily_nutrition_summary(
        [{"calories": l.calories, "protein_g": l.protein_g, "carbs_g": l.carbs_g, "fat_g": l.fat_g, "fiber_g": l.fiber_g} for l in logs],
        user.get("calorie_goal", 2000) or 2000,
    )

    return TR(request, "customer/profile.html", {"user": user, "nutrition": nutrition_summary})


# ═══════════════════════════════════════════════════════════════════
# BAKER PORTAL PAGES (/baker/...)
# ═══════════════════════════════════════════════════════════════════

@app.get("/baker/", response_class=HTMLResponse)
async def baker_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "baker":
        return TR(request, "baker/login.html")

    result = await db.execute(select(Baker).where(Baker.user_id == user["id"]))
    baker = result.scalar_one_or_none()

    if not baker or baker.status != "approved":
        return TR(request, "baker/pending.html", {"user": user, "baker": baker})

    # Get active orders
    orders_result = await db.execute(
        select(Order).where(Order.baker_id == baker.id)
        .order_by(Order.placed_at.desc())
    )
    orders = orders_result.scalars().all()

    return TR(request, "baker/dashboard.html", {"user": user, "baker": baker, "orders": orders})


@app.get("/baker/login", response_class=HTMLResponse)
async def baker_login_page(request: Request):
    return TR(request, "baker/login.html")


@app.get("/baker/apply", response_class=HTMLResponse)
async def baker_apply_page(request: Request):
    return TR(request, "baker/apply.html")


@app.get("/baker/earnings", response_class=HTMLResponse)
async def baker_earnings_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "baker":
        return RedirectResponse(url="/baker/login")
    result = await db.execute(select(Baker).where(Baker.user_id == user["id"]))
    baker = result.scalar_one_or_none()
    return TR(request, "baker/earnings.html", {"user": user, "baker": baker})


# ═══════════════════════════════════════════════════════════════════
# ADMIN PANEL PAGES (/admin/...)
# ═══════════════════════════════════════════════════════════════════

@app.get("/admin/", response_class=HTMLResponse)
async def admin_home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "admin":
        return TR(request, "admin/login.html")
    return TR(request, "admin/dashboard.html", {"user": user})


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return TR(request, "admin/login.html")


@app.get("/admin/applicants", response_class=HTMLResponse)
async def admin_applicants_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/admin/login")
    return TR(request, "admin/applicants.html", {"user": user})


@app.get("/admin/bakers", response_class=HTMLResponse)
async def admin_bakers_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/admin/login")
    return TR(request, "admin/bakers.html", {"user": user})


@app.get("/admin/orders", response_class=HTMLResponse)
async def admin_orders_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/admin/login")
    return TR(request, "admin/orders.html", {"user": user})


@app.get("/admin/recipes", response_class=HTMLResponse)
async def admin_recipes_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_template_user(request, db)
    if not user or user.get("role") != "admin":
        return RedirectResponse(url="/admin/login")
    return TR(request, "admin/recipes.html", {"user": user})
