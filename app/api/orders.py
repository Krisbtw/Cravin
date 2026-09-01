"""
Cravin — SSE Order Tracking
Server-Sent Events for real-time order status updates.
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import json

from app.database import get_db, async_session
from app.models.order import Order
from app.models.user import User
from app.schemas.order import CreateOrder, UpdatePortionLogRequest
from app.services.auth_service import get_current_user
from app.services.order_service import create_order, update_order_portion_log

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("")
@router.post("/")
@router.post("/checkout")
async def place_order_api(
    data: CreateOrder,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Place a new order via /api/orders or /api/orders/checkout."""
    items = [item.model_dump() for item in data.items]
    order = await create_order(
        user_id=user.id,
        items=items,
        fulfillment_type=data.fulfillment_type,
        is_group_order=data.is_group_order,
        delivery_address=data.delivery_address,
        delivery_notes=data.delivery_notes,
        city=user.city,
        db=db,
        baker_id=data.baker_id,
        delivery_latitude=data.delivery_latitude,
        delivery_longitude=data.delivery_longitude,
    )
    order.payment_status = "paid"
    order.payment_id = f"mock_{order.order_number}"

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "baker_id": order.baker_id,
        "total_amount": order.total_amount,
        "status": order.status,
        "message": "Order placed successfully! 🎉",
    }


@router.get("/{order_id}/track")
async def track_order(order_id: str, request: Request):
    """SSE endpoint for real-time order tracking."""

    async def event_generator():
        last_status = None
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Fetch latest order status
            async with async_session() as db:
                result = await db.execute(select(Order).where(Order.id == order_id))
                order = result.scalar_one_or_none()

            if order and order.status != last_status:
                last_status = order.status
                partner = None
                if order.status in ["out_for_delivery", "delivered"]:
                    partner = {
                        "name": "Ramesh Kumar",
                        "phone": "+91 98765 43210",
                        "vehicle": "Electric Scooter (GA-07-EK-8821)",
                        "rating": 4.9,
                        "badge": "Cravin Express Partner",
                        "eta_mins": 15 if order.status == "out_for_delivery" else 0,
                    }
                data = json.dumps({
                    "status": order.status,
                    "order_number": order.order_number,
                    "estimated_mins": order.estimated_delivery_mins,
                    "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
                    "prepared_at": order.prepared_at.isoformat() if order.prepared_at else None,
                    "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
                    "delivery_partner": partner,
                })
                yield f"data: {data}\n\n"

                # Stop streaming if delivered or cancelled
                if order.status in ["delivered", "cancelled"]:
                    break

            await asyncio.sleep(3)  # Poll every 3 seconds

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.patch("/{order_id}/portion-log")
async def update_portion_log(
    order_id: str,
    data: UpdatePortionLogRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adjust personally consumed portions for group/party orders."""
    from app.services.order_service import update_order_portion_log
    portions_data = [p.model_dump() for p in data.portions]
    order = await update_order_portion_log(order_id, portions_data, user.id, db)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or unauthorized")

    personal_cals = sum(
        (item.calories_per_unit * (item.consumed_quantity if item.consumed_quantity is not None else item.quantity))
        for item in order.items
    )

    return {
        "status": "success",
        "order_id": order.id,
        "is_group_order": order.is_group_order,
        "personal_calories": round(personal_cals, 1),
        "items": [
            {
                "order_item_id": item.id,
                "quantity": item.quantity,
                "consumed_quantity": item.consumed_quantity,
                "personal_calories": round(item.calories_per_unit * item.consumed_quantity, 1),
            }
            for item in order.items
        ],
        "message": "Portion allocation updated successfully! 🥗"
    }
