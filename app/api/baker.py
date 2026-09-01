"""
Cravin — Baker API Routes
Order queue management, dashboard, earnings.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.baker import Baker
from app.models.order import Order, OrderStatus
from app.models.dessert import Dessert
from app.services.auth_service import get_current_user, require_role
from app.services.order_service import update_order_status, get_baker_orders

router = APIRouter(prefix="/api/baker", tags=["baker"])


@router.get("/dashboard")
async def baker_dashboard(
    user: User = Depends(require_role("baker")),
    db: AsyncSession = Depends(get_db),
):
    """Get baker's dashboard data: stats + active orders."""
    result = await db.execute(select(Baker).where(Baker.user_id == user.id))
    baker = result.scalar_one_or_none()
    if not baker:
        raise HTTPException(status_code=404, detail="Baker profile not found")

    # Get order counts by status
    active_orders = await get_baker_orders(baker.id, None, db)
    today = datetime.utcnow().date()

    stats = {
        "total_orders": baker.total_orders_completed,
        "avg_rating": baker.avg_rating,
        "total_earnings": baker.total_earnings,
        "pending_payout": baker.pending_payout,
        "today_orders": len([o for o in active_orders if o.placed_at.date() == today]),
        "active_orders": len([o for o in active_orders if o.status in [
            OrderStatus.PLACED.value, OrderStatus.ACCEPTED.value, OrderStatus.PREPARING.value
        ]]),
    }

    return {
        "baker": {
            "id": baker.id,
            "business_name": baker.business_name,
            "status": baker.status,
            "avg_rating": baker.avg_rating,
        },
        "stats": stats,
    }


@router.get("/orders")
async def baker_orders(
    status: Optional[str] = None,
    user: User = Depends(require_role("baker")),
    db: AsyncSession = Depends(get_db),
):
    """Get baker's order queue, optionally filtered by status."""
    result = await db.execute(select(Baker).where(Baker.user_id == user.id))
    baker = result.scalar_one_or_none()
    if not baker:
        raise HTTPException(status_code=404, detail="Baker profile not found")

    orders = await get_baker_orders(baker.id, status, db)

    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "fulfillment_type": o.fulfillment_type,
            "total_amount": o.total_amount,
            "placed_at": o.placed_at.isoformat(),
            "items": [
                {
                    "dessert_id": item.dessert_id,
                    "quantity": item.quantity,
                    "is_customized": item.is_customized,
                    "customization": item.customization,
                }
                for item in (o.items or [])
            ],
        }
        for o in orders
    ]


@router.post("/orders/{order_id}/status")
async def update_status(
    order_id: str,
    new_status: str,
    user: User = Depends(require_role("baker")),
    db: AsyncSession = Depends(get_db),
):
    """Update order status: accept → preparing → ready."""
    result = await db.execute(select(Baker).where(Baker.user_id == user.id))
    baker = result.scalar_one_or_none()
    if not baker:
        raise HTTPException(status_code=404, detail="Baker profile not found")

    # Verify the order belongs to this baker
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.baker_id == baker.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")

    # Validate status transitions
    valid_transitions = {
        OrderStatus.PLACED.value: [OrderStatus.ACCEPTED.value, OrderStatus.CANCELLED.value],
        OrderStatus.ACCEPTED.value: [OrderStatus.PREPARING.value, OrderStatus.CANCELLED.value],
        OrderStatus.PREPARING.value: [OrderStatus.READY.value],
        OrderStatus.READY.value: [OrderStatus.OUT_FOR_DELIVERY.value, OrderStatus.DELIVERED.value],
        OrderStatus.OUT_FOR_DELIVERY.value: [OrderStatus.DELIVERED.value],
    }

    allowed = valid_transitions.get(order.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{order.status}' to '{new_status}'. Allowed: {allowed}"
        )

    updated = await update_order_status(order_id, new_status, db)

    # Update baker stats on delivery
    if new_status == OrderStatus.DELIVERED.value:
        baker.total_orders_completed += 1
        baker.total_earnings += order.total_amount * 0.75  # 75% goes to baker
        baker.pending_payout += order.total_amount * 0.75

    return {
        "order_id": order_id,
        "new_status": new_status,
        "message": f"Order updated to: {new_status}",
    }


@router.get("/earnings")
async def baker_earnings(
    user: User = Depends(require_role("baker")),
    db: AsyncSession = Depends(get_db),
):
    """Get baker's earnings and payout history."""
    result = await db.execute(select(Baker).where(Baker.user_id == user.id))
    baker = result.scalar_one_or_none()
    if not baker:
        raise HTTPException(status_code=404, detail="Baker profile not found")

    return {
        "total_earnings": baker.total_earnings,
        "pending_payout": baker.pending_payout,
        "total_orders": baker.total_orders_completed,
        "avg_order_value": round(baker.total_earnings / max(baker.total_orders_completed, 1), 2),
    }
