"""
Cravin — Admin API Routes
Baker approvals, order oversight, analytics, recipe moderation.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.models.baker import Baker, BakerApplication, BakerStatus
from app.models.order import Order, OrderStatus
from app.models.dessert import Dessert
from app.models.review import Review
from app.services.auth_service import require_role
from app.services.order_service import get_all_orders, update_order_status

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/dashboard")
async def admin_dashboard(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin dashboard: key metrics and stats."""
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)

    # Order stats
    all_orders = await db.execute(select(func.count(Order.id)))
    total_orders = all_orders.scalar() or 0

    today_orders = await db.execute(
        select(func.count(Order.id)).where(
            func.date(Order.placed_at) == today
        )
    )
    today_count = today_orders.scalar() or 0

    # Revenue
    revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.payment_status == "paid")
    )
    total_revenue = revenue_result.scalar() or 0

    today_revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(
            Order.payment_status == "paid",
            func.date(Order.placed_at) == today,
        )
    )
    today_revenue = today_revenue_result.scalar() or 0

    # Baker stats
    active_bakers = await db.execute(
        select(func.count(Baker.id)).where(Baker.status == BakerStatus.APPROVED.value)
    )
    pending_apps = await db.execute(
        select(func.count(Baker.id)).where(Baker.status == BakerStatus.APPLIED.value)
    )

    # User stats
    user_count = await db.execute(
        select(func.count(User.id)).where(User.role == "customer")
    )

    # Dessert stats
    dessert_count = await db.execute(select(func.count(Dessert.id)))

    return {
        "orders": {
            "total": total_orders,
            "today": today_count,
        },
        "revenue": {
            "total": round(total_revenue, 2),
            "today": round(today_revenue, 2),
        },
        "bakers": {
            "active": active_bakers.scalar() or 0,
            "pending_applications": pending_apps.scalar() or 0,
        },
        "customers": user_count.scalar() or 0,
        "desserts": dessert_count.scalar() or 0,
    }


@router.get("/applicants")
async def list_applicants(
    status: Optional[str] = None,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List baker applications for review."""
    query = select(Baker)
    if status:
        query = query.where(Baker.status == status)
    else:
        query = query.where(Baker.status.in_([
            BakerStatus.APPLIED.value,
            BakerStatus.UNDER_REVIEW.value,
            BakerStatus.INTERVIEW_SCHEDULED.value,
        ]))

    result = await db.execute(query.order_by(Baker.created_at.desc()))
    bakers = result.scalars().all()

    applicants = []
    for baker in bakers:
        # Get user info
        user_result = await db.execute(select(User).where(User.id == baker.user_id))
        baker_user = user_result.scalar_one_or_none()

        applicants.append({
            "baker_id": baker.id,
            "user_id": baker.user_id,
            "name": baker_user.full_name if baker_user else "Unknown",
            "email": baker_user.email if baker_user else "",
            "business_name": baker.business_name,
            "skills": baker.skills,
            "specialties": baker.specialties,
            "fssai_number": baker.fssai_number,
            "city": baker.city,
            "area": baker.area,
            "status": baker.status,
            "applied_at": baker.created_at.isoformat(),
        })

    return applicants


@router.post("/applicants/{baker_id}/status")
async def update_applicant_status(
    baker_id: str,
    new_status: str,
    notes: Optional[str] = None,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approve/reject/update a baker application."""
    result = await db.execute(select(Baker).where(Baker.id == baker_id))
    baker = result.scalar_one_or_none()
    if not baker:
        raise HTTPException(status_code=404, detail="Baker not found")

    valid_statuses = [s.value for s in BakerStatus]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    baker.status = new_status
    if new_status == BakerStatus.APPROVED.value:
        baker.approved_at = datetime.utcnow()

    # Log the application status change
    import uuid
    app_log = BakerApplication(
        id=str(uuid.uuid4()),
        baker_id=baker.id,
        status=new_status,
        admin_notes=notes,
        reviewed_by=user.id,
    )
    db.add(app_log)

    return {"message": f"Baker status updated to: {new_status}", "baker_id": baker_id}


@router.get("/bakers")
async def list_bakers(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all approved bakers with performance metrics."""
    result = await db.execute(
        select(Baker).where(Baker.status == BakerStatus.APPROVED.value)
    )
    bakers = result.scalars().all()

    baker_list = []
    for baker in bakers:
        user_result = await db.execute(select(User).where(User.id == baker.user_id))
        baker_user = user_result.scalar_one_or_none()

        baker_list.append({
            "baker_id": baker.id,
            "name": baker_user.full_name if baker_user else "Unknown",
            "business_name": baker.business_name,
            "city": baker.city,
            "avg_rating": baker.avg_rating,
            "total_orders": baker.total_orders_completed,
            "total_earnings": baker.total_earnings,
            "status": baker.status,
            "fssai_verified": baker.fssai_verified,
        })

    return baker_list


@router.get("/orders")
async def admin_orders(
    status: Optional[str] = None,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """View all orders with optional status filter."""
    orders = await get_all_orders(status, db)
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total_amount": o.total_amount,
            "payment_status": o.payment_status,
            "fulfillment_type": o.fulfillment_type,
            "placed_at": o.placed_at.isoformat(),
            "baker_id": o.baker_id,
        }
        for o in orders
    ]


@router.get("/recipes/pending")
async def pending_recipes(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """List AI-generated recipes pending moderation."""
    result = await db.execute(
        select(Dessert).where(
            Dessert.is_ai_generated == True,
            Dessert.approval_status == "pending",
        )
    )
    desserts = result.scalars().all()

    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "calories": d.calories,
            "tag": d.tag,
            "base_ingredients": d.base_ingredients,
            "ai_generation_prompt": d.ai_generation_prompt,
            "created_at": d.created_at.isoformat(),
        }
        for d in desserts
    ]


@router.post("/recipes/{dessert_id}/moderate")
async def moderate_recipe(
    dessert_id: str,
    action: str,  # approve or reject
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an AI-generated recipe."""
    result = await db.execute(select(Dessert).where(Dessert.id == dessert_id))
    dessert = result.scalar_one_or_none()
    if not dessert:
        raise HTTPException(status_code=404, detail="Dessert not found")

    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    dessert.approval_status = "approved" if action == "approve" else "rejected"
    dessert.approved_by = user.id

    return {"message": f"Recipe '{dessert.name}' has been {dessert.approval_status}"}
