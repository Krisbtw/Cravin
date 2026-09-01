"""
Cravin — Order Service
Manages the full order lifecycle: create → assign baker → track → deliver.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.dessert import Dessert
from app.models.baker import Baker, BakerStatus
from app.models.nutrition_log import NutritionLog
from app.services.baker_matcher import assign_baker_to_order
from app.services.loyalty_service import award_order_points
from app.services.nutrition_engine import calculate_recipe_nutrition


def generate_order_number() -> str:
    """Generate a human-readable order number: CRV-XXXXXX"""
    return f"CRV-{uuid.uuid4().hex[:6].upper()}"


async def create_order(
    user_id: str,
    items: list[dict],
    fulfillment_type: str,
    delivery_address: Optional[str],
    delivery_notes: Optional[str],
    city: Optional[str],
    db: AsyncSession,
    is_group_order: bool = False,
    baker_id: Optional[str] = None,
    delivery_latitude: Optional[float] = None,
    delivery_longitude: Optional[float] = None,
) -> Order:
    """
    Create a new order from cart items.
    items: [{"dessert_id": "...", "quantity": 1, "consumed_quantity": 1, "customization": {...}}]
    If baker_id is provided, uses customer's choice; otherwise falls back to auto-matching.
    """
    calculated_delivery_fee = 0.0
    estimated_mins = 30
    if fulfillment_type == "delivery":
        # Dynamic regression surge pricing based on real-time density and distance
        from app.services.pricing import calculate_surge_fee
        active_bakers_count = await db.scalar(
            select(func.count(Baker.id)).where(Baker.status == BakerStatus.APPROVED)
        ) or 1
        active_orders_count = await db.scalar(
            select(func.count(Order.id)).where(
                Order.status.in_([OrderStatus.PLACED.value, OrderStatus.ACCEPTED.value, OrderStatus.PREPARING.value])
            )
        ) or 0

        calculated_delivery_fee = calculate_surge_fee(
            base_fee=30.0,
            active_bakers=active_bakers_count,
            active_orders=active_orders_count,
            distance_km=4.5,
            traffic_index=1.1,
        )
        estimated_mins = min(60, 30 + int(calculated_delivery_fee / 2.0))

    order = Order(
        id=str(uuid.uuid4()),
        order_number=generate_order_number(),
        user_id=user_id,
        fulfillment_type=fulfillment_type,
        is_group_order=is_group_order,
        delivery_address=delivery_address,
        delivery_latitude=delivery_latitude,
        delivery_longitude=delivery_longitude,
        delivery_notes=delivery_notes,
        delivery_fee=calculated_delivery_fee,
        discount=0.0,
        estimated_delivery_mins=estimated_mins,
    )

    subtotal = 0.0
    total_calories = 0.0

    for item_data in items:
        # Fetch the dessert
        result = await db.execute(
            select(Dessert).where(Dessert.id == item_data["dessert_id"])
        )
        dessert = result.scalar_one_or_none()
        if not dessert:
            continue

        qty = item_data.get("quantity", 1)
        consumed_qty = item_data.get("consumed_quantity")
        if consumed_qty is None:
            consumed_qty = 1 if is_group_order else qty
        else:
            consumed_qty = min(qty, max(0, int(consumed_qty)))

        customization = item_data.get("customization")
        unit_price = dessert.price
        item_calories = dessert.calories

        # If customized, recalculate nutrition
        if customization and customization.get("modified_ingredients"):
            nutrition = calculate_recipe_nutrition(
                customization["modified_ingredients"],
                servings=dessert.servings_per_recipe,
            )
            item_calories = nutrition["per_serving"]["calories"]

        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            dessert_id=dessert.id,
            quantity=qty,
            consumed_quantity=consumed_qty,
            unit_price=unit_price,
            total_price=unit_price * qty,
            calories_per_unit=item_calories,
            is_customized=bool(customization),
            customization=customization,
        )
        db.add(order_item)

        subtotal += order_item.total_price
        total_calories += item_calories * qty

    order.subtotal = round(subtotal, 2)
    order.total_amount = round(subtotal + order.delivery_fee - order.discount, 2)
    order.total_calories = round(total_calories, 1)

    # Baker assignment: Use customer choice if valid, otherwise auto-match
    assigned_baker_id = None
    if baker_id:
        baker_check = await db.execute(
            select(Baker).where(Baker.id == baker_id, Baker.status == BakerStatus.APPROVED)
        )
        valid_baker = baker_check.scalar_one_or_none()
        if valid_baker:
            assigned_baker_id = valid_baker.id

    if not assigned_baker_id:
        assigned_baker_id = await assign_baker_to_order(
            order_id=order.id,
            city=city,
            delivery_lat=delivery_latitude,
            delivery_lng=delivery_longitude,
            db=db,
        )

    if assigned_baker_id:
        order.baker_id = assigned_baker_id

    db.add(order)
    return order


async def update_order_status(
    order_id: str, new_status: str, db: AsyncSession
) -> Optional[Order]:
    """Update order status with timestamp tracking."""
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    order.status = new_status
    now = datetime.utcnow()

    if new_status == OrderStatus.ACCEPTED.value:
        order.accepted_at = now
    elif new_status == OrderStatus.PREPARING.value:
        pass
    elif new_status == OrderStatus.READY.value:
        order.prepared_at = now
    elif new_status == OrderStatus.OUT_FOR_DELIVERY.value:
        pass
    elif new_status == OrderStatus.DELIVERED.value:
        order.delivered_at = now
        # Award loyalty points
        await award_order_points(order.user_id, order.total_amount, order.id, db)
        # Log nutrition
        await _log_order_nutrition(order, db)
    elif new_status == OrderStatus.CANCELLED.value:
        order.cancelled_at = now

    return order


async def mark_payment_complete(order_id: str, payment_id: str, db: AsyncSession) -> Optional[Order]:
    """Mark order as paid (mocked in Phase 1)."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None

    order.payment_status = PaymentStatus.PAID.value
    order.payment_id = payment_id
    return order


async def _log_order_nutrition(order: Order, db: AsyncSession):
    """Log nutrition for delivered items to the user's daily tracker based on personal consumed portion."""
    from datetime import date as date_type
    for item in order.items:
        portion = item.consumed_quantity if item.consumed_quantity is not None else item.quantity
        if portion <= 0:
            continue
        log = NutritionLog(
            id=str(uuid.uuid4()),
            user_id=order.user_id,
            date=date_type.today(),
            dessert_id=item.dessert_id,
            order_id=order.id,
            calories=item.calories_per_unit * portion,
            quantity=portion,
        )
        db.add(log)


async def update_order_portion_log(
    order_id: str,
    portions: list[dict],
    user_id: str,
    db: AsyncSession,
) -> Optional[Order]:
    """
    Update consumed portions on order items and recalculate/sync NutritionLog records.
    portions: [{"order_item_id": "...", "consumed_quantity": 2}]
    """
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id, Order.user_id == user_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    portion_map = {p["order_item_id"]: max(0, int(p["consumed_quantity"])) for p in portions}

    for item in order.items:
        if item.id in portion_map:
            # Cap consumed quantity at total ordered quantity
            item.consumed_quantity = min(item.quantity, portion_map[item.id])

    # Sync existing NutritionLogs for this order if already delivered
    logs_res = await db.execute(select(NutritionLog).where(NutritionLog.order_id == order.id))
    existing_logs = logs_res.scalars().all()
    for log in existing_logs:
        matching_item = next((i for i in order.items if i.dessert_id == log.dessert_id), None)
        if matching_item:
            log.quantity = matching_item.consumed_quantity
            log.calories = matching_item.calories_per_unit * matching_item.consumed_quantity

    await db.flush()
    return order


async def get_user_orders(user_id: str, db: AsyncSession) -> list[Order]:
    """Get all orders for a user, most recent first."""
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.placed_at.desc())
    )
    return list(result.scalars().all())


async def get_baker_orders(baker_id: str, status_filter: Optional[str], db: AsyncSession) -> list[Order]:
    """Get orders assigned to a baker, optionally filtered by status."""
    query = select(Order).where(Order.baker_id == baker_id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    query = query.order_by(Order.placed_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_all_orders(status_filter: Optional[str], db: AsyncSession) -> list[Order]:
    """Admin: get all orders with optional status filter."""
    query = select(Order)
    if status_filter:
        query = query.where(Order.status == status_filter)
    query = query.order_by(Order.placed_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())
