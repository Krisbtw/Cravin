"""
Cravin — SSE Order Tracking
Server-Sent Events for real-time order status updates.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import json

from app.database import get_db, async_session
from app.models.order import Order
from app.models.user import User
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])


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
