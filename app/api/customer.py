"""
Cravin — Customer API Routes
Browse, customize, order, track, review.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.user import User
from app.models.dessert import Dessert
from app.models.order import Order
from app.models.review import Review
from app.models.nutrition_log import NutritionLog
from app.models.loyalty import LoyaltyAccount
from app.schemas.dessert import DessertResponse, DessertDetail, CustomizationRequest
from app.models.baker import Baker
from app.schemas.order import CreateOrder, OrderResponse, BakerMatchRequest
from app.schemas.loyalty import LoyaltyAccountResponse
from app.services.auth_service import get_current_user, get_current_user_optional
from app.services.ai_service import customize_dessert
from app.services.nutrition_engine import calculate_recipe_nutrition, get_daily_nutrition_summary
from app.services.order_service import create_order, get_user_orders
from app.services.baker_matcher import find_matching_bakers
from app.services.loyalty_service import award_order_points
from app.services.recommendation import get_recommendations

router = APIRouter(prefix="/api/customer", tags=["customer"])


@router.get("/recommendations", response_model=list[DessertResponse])
async def get_customer_recommendations(
    time: str = Query("evening"),
    weather: str = Query("warm"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get personalized dessert recommendations based on hybrid scoring."""
    user_id = user.id if user else None
    recommended = await get_recommendations(
        user_id=user_id,
        db=db,
        context={"time": time, "weather": weather},
        limit=6,
    )
    return [DessertResponse.model_validate(d) for d in recommended]


@router.get("/desserts")
async def list_desserts(
    tag: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Browse all available desserts, optionally filtered by tag or search."""
    query = select(Dessert).where(
        Dessert.is_active == True,
        Dessert.approval_status == "approved",
    )
    if tag:
        query = query.where(Dessert.tag == tag)

    result = await db.execute(query.order_by(Dessert.order_count.desc()))
    desserts = result.scalars().all()

    if search:
        search_lower = search.lower()
        desserts = [d for d in desserts if search_lower in d.name.lower() or search_lower in d.description.lower()]

    return [DessertResponse.model_validate(d) for d in desserts]


@router.get("/desserts/{dessert_id}")
async def get_dessert(dessert_id: str, db: AsyncSession = Depends(get_db)):
    """Get full dessert detail with nutrition panel."""
    result = await db.execute(select(Dessert).where(Dessert.id == dessert_id))
    dessert = result.scalar_one_or_none()
    if not dessert:
        raise HTTPException(status_code=404, detail="Dessert not found")

    return DessertDetail.model_validate(dessert)


@router.post("/customize")
async def customize(
    data: CustomizationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI-customize a dessert (scoped: sweetness, protein, allergies)."""
    result = await db.execute(select(Dessert).where(Dessert.id == data.dessert_id))
    dessert = result.scalar_one_or_none()
    if not dessert:
        raise HTTPException(status_code=404, detail="Dessert not found")

    dessert_dict = {
        "name": dessert.name,
        "base_ingredients": dessert.base_ingredients,
        "description": dessert.description,
    }

    customization = await customize_dessert(
        dessert=dessert_dict,
        sweetness=data.sweetness,
        protein_boost=data.protein_boost,
        exclude_allergens=data.exclude_allergens,
        user_message=data.user_message,
        user_allergies=user.allergies or [],
    )

    nutrition = calculate_recipe_nutrition(
        customization["modified_ingredients"],
        servings=dessert.servings_per_recipe,
    )

    return {
        **customization,
        "original_dessert": dessert.name,
        "nutrition": nutrition,
    }


@router.post("/bakers/match")
async def match_bakers(
    data: BakerMatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Find and rank matching bakers for the cart items and delivery location.
    Computes real proximity via haversine distance.
    """
    required_skills = list(data.required_skills or [])

    # Extract required skills from cart items if any
    for item in data.items:
        result = await db.execute(select(Dessert).where(Dessert.id == item.dessert_id))
        dessert = result.scalar_one_or_none()
        if dessert:
            if dessert.dietary_flags:
                required_skills.extend([f.lower().strip() for f in dessert.dietary_flags if f])
            if item.customization and item.customization.get("exclude_allergens"):
                required_skills.extend([a.lower().strip() for a in item.customization["exclude_allergens"] if a])

    # Deduplicate skills
    unique_skills = list(set(required_skills))

    bakers = await find_matching_bakers(
        required_skills=unique_skills,
        city=data.city,
        delivery_lat=data.delivery_latitude,
        delivery_lng=data.delivery_longitude,
        db=db,
    )

    return {
        "count": len(bakers),
        "bakers": bakers,
    }


@router.post("/orders")
async def place_order(
    data: CreateOrder,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Place a new order from cart with optional customer-chosen baker."""
    try:
        items = [item.model_dump() for item in data.items]
        if not items:
            raise HTTPException(status_code=400, detail="Cart is empty")

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

        # Mock payment (Phase 1)
        order.payment_status = "paid"
        order.payment_id = f"mock_{order.order_number}"
        await db.commit()

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "baker_id": order.baker_id,
            "total_amount": order.total_amount,
            "status": order.status,
            "message": "Order placed successfully! 🎉",
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")


@router.get("/orders")
async def my_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all orders for the current user."""
    orders = await get_user_orders(user.id, db)
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total_amount": o.total_amount,
            "total_calories": o.total_calories,
            "fulfillment_type": o.fulfillment_type,
            "placed_at": o.placed_at.isoformat(),
            "items_count": len(o.items) if o.items else 0,
        }
        for o in orders
    ]


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get order details with tracking info and mock delivery partner assignment."""
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items_data = []
    for item in (order.items or []):
        result2 = await db.execute(select(Dessert).where(Dessert.id == item.dessert_id))
        dessert = result2.scalar_one_or_none()
        items_data.append({
            "dessert_name": dessert.name if dessert else "Unknown",
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
            "calories_per_unit": item.calories_per_unit,
            "is_customized": item.is_customized,
            "customization": item.customization,
        })

    # Fetch baker info if assigned
    baker_info = None
    if order.baker_id:
        b_res = await db.execute(select(Baker).where(Baker.id == order.baker_id))
        baker_obj = b_res.scalar_one_or_none()
        if baker_obj:
            baker_info = {
                "id": baker_obj.id,
                "business_name": baker_obj.business_name,
                "avg_rating": baker_obj.avg_rating,
                "area": baker_obj.area,
                "city": baker_obj.city,
            }

    # Mock delivery partner details when out for delivery or delivered
    delivery_partner = None
    if order.status in ["out_for_delivery", "delivered"]:
        delivery_partner = {
            "name": "Ramesh Kumar",
            "phone": "+91 98765 43210",
            "vehicle": "Electric Scooter (GA-07-EK-8821)",
            "rating": 4.9,
            "badge": "Cravin Express Partner",
            "eta_mins": 15 if order.status == "out_for_delivery" else 0,
        }

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "fulfillment_type": order.fulfillment_type,
        "payment_status": order.payment_status,
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "total_amount": order.total_amount,
        "total_calories": order.total_calories,
        "delivery_address": order.delivery_address,
        "delivery_notes": order.delivery_notes,
        "estimated_delivery_mins": order.estimated_delivery_mins,
        "placed_at": order.placed_at.isoformat(),
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        "prepared_at": order.prepared_at.isoformat() if order.prepared_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "items": items_data,
        "baker": baker_info,
        "delivery_partner": delivery_partner,
        "loyalty_points_earned": order.loyalty_points_earned,
    }



@router.post("/reviews")
async def submit_review(
    dessert_id: str,
    baker_id: str,
    order_id: str,
    rating: int,
    text: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review for a dessert/baker after delivery."""
    import uuid
    review = Review(
        id=str(uuid.uuid4()),
        user_id=user.id,
        baker_id=baker_id,
        dessert_id=dessert_id,
        order_id=order_id,
        rating=max(1, min(5, rating)),
        text=text,
    )
    db.add(review)
    return {"message": "Thanks for your review! 🌟"}


@router.get("/nutrition/today")
async def nutrition_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get today's nutrition summary for the donut calorie tracker."""
    result = await db.execute(
        select(NutritionLog).where(
            NutritionLog.user_id == user.id,
            NutritionLog.date == date.today(),
        )
    )
    logs = result.scalars().all()

    log_dicts = [
        {"calories": l.calories, "protein_g": l.protein_g, "carbs_g": l.carbs_g,
         "fat_g": l.fat_g, "fiber_g": l.fiber_g}
        for l in logs
    ]

    return get_daily_nutrition_summary(log_dicts, user.calorie_goal or 2000)


@router.get("/loyalty")
async def get_loyalty(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get loyalty account details (Sweet Streak)."""
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return {"message": "No loyalty account found"}

    return LoyaltyAccountResponse.model_validate(account)
