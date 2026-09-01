"""
Cravin — Smart Recommendation Engine
Hybrid collaborative and content-based filtering.
Factors in user flavor profile, dietary flags, calorie goal, time of day, and weather.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.dessert import Dessert
from app.models.user import User


def calculate_hybrid_score(
    user: Optional[User],
    item: Dessert,
    current_time: str = "",
    weather: str = "",
) -> float:
    """
    Calculate a hybrid recommendation score (0.0 to 1.0) for a dessert.
    """
    collab_score = 0.5  # Base collaborative rating
    content_score = 0.0

    dietary_flags = item.dietary_flags or []
    allergens = item.allergens or []

    # 1. Hard filter: Never recommend items with user allergies
    if user and user.allergies:
        user_allergies = [a.lower() for a in user.allergies]
        for a in allergens:
            if a.lower() in user_allergies:
                return -1.0  # Disqualify immediately

    # 2. Dietary preference match
    if user and user.dietary_prefs:
        if user.dietary_prefs.get("vegan") and "vegan" in dietary_flags:
            content_score += 0.3
        if user.dietary_prefs.get("eggless") and "eggless" in dietary_flags:
            content_score += 0.3
        if user.dietary_prefs.get("gluten_free") and "gluten-free" in dietary_flags:
            content_score += 0.3

    # 3. Flavor profile matching
    if user and user.flavor_profile:
        fav_flavors = [f.lower() for f in user.flavor_profile.get("favorite_flavors", [])]
        item_text = (item.name + " " + item.description).lower()
        if any(flavor in item_text for flavor in fav_flavors):
            content_score += 0.35

        # Sweetness preference (sweet_vs_rich: 0.0 = subtle/light, 1.0 = rich/heavy)
        sweet_vs_rich = user.flavor_profile.get("sweet_vs_rich", 0.5)
        if sweet_vs_rich > 0.6 and item.tag in ["balanced", "heavy"]:
            content_score += 0.2
        elif sweet_vs_rich <= 0.4 and item.tag in ["light"]:
            content_score += 0.2

    # 4. Contextual signals (time of day & weather)
    if "morning" in current_time.lower() or "breakfast" in current_time.lower():
        if item.tag == "light":
            content_score += 0.25
    elif "evening" in current_time.lower() or "night" in current_time.lower():
        if item.tag in ["balanced", "heavy"]:
            content_score += 0.2

    if "cold" in weather.lower() or "rain" in weather.lower():
        if "chocolate" in item.name.lower() or "warm" in dietary_flags:
            content_score += 0.2
    elif "hot" in weather.lower() or "summer" in weather.lower():
        if "kheer" in item.name.lower() or "pudding" in item.name.lower() or item.tag == "light":
            content_score += 0.2

    # Popularity boost based on order count
    popularity_boost = min((item.order_count or 0) / 100.0, 0.2)

    # Combine weighted scores
    return round((0.4 * collab_score) + (0.5 * min(content_score, 1.0)) + (0.1 * popularity_boost), 4)


async def get_recommendations(
    user_id: Optional[str],
    db: AsyncSession,
    context: Optional[dict] = None,
    limit: int = 4,
) -> list[Dessert]:
    """
    Fetch personalized dessert recommendations for a user asynchronously.
    """
    context = context or {}
    user = None
    if user_id:
        user_res = await db.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()

    result = await db.execute(
        select(Dessert).where(Dessert.is_active == True, Dessert.approval_status == "approved")
    )
    items = result.scalars().all()

    scored_items = []
    for item in items:
        score = calculate_hybrid_score(
            user=user,
            item=item,
            current_time=context.get("time", "evening"),
            weather=context.get("weather", "warm"),
        )
        if score >= 0:  # Exclude disqualified allergen items
            scored_items.append((item, score))

    scored_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored_items[:limit]]
