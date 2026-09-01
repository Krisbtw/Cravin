"""
Cravin — Baker Matcher Service
Matches custom orders to bakers by skill tags, availability, and proximity.
"""

import math
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.baker import Baker, BakerStatus


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth
    in kilometers using the Haversine formula.
    """
    R = 6371.0  # Earth's mean radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


async def find_matching_bakers(
    required_skills: list[str] = None,
    city: Optional[str] = None,
    exclude_allergens: list[str] = None,
    delivery_lat: Optional[float] = None,
    delivery_lng: Optional[float] = None,
    db: AsyncSession = None,
) -> list[dict]:
    """
    Find bakers who can fulfill a custom order.

    Matching logic:
    1. Baker must be approved and active
    2. If coordinates are provided, baker must be within their delivery_radius_km
    3. Baker's skills must match required skill tags (if any)
    4. Baker must be in the same city (if city specified and no coords)
    5. Ranked by: proximity (if coords) + skill match + rating + queue availability

    Returns sorted list of baker dicts with match scores & distance.
    """
    if not db:
        return []

    required_skills = required_skills or []

    # Get all approved bakers
    result = await db.execute(
        select(Baker).where(Baker.status == BakerStatus.APPROVED.value)
    )
    bakers = result.scalars().all()

    has_coords = delivery_lat is not None and delivery_lng is not None

    matches = []
    for baker in bakers:
        # Distance & Radius Check
        distance_km = None
        proximity_score = 0.5

        if has_coords and baker.latitude is not None and baker.longitude is not None:
            distance_km = calculate_haversine_distance(
                delivery_lat, delivery_lng, baker.latitude, baker.longitude
            )
            # Filter out any baker whose distance exceeds their delivery radius
            radius = baker.delivery_radius_km or 7.0
            if distance_km > radius:
                continue
            proximity_score = max(0.0, 1.0 - (distance_km / max(radius, 1.0)))
        elif city and baker.city and baker.city.lower() != city.lower():
            # City filter fallback if coordinates are not available
            continue

        # Skill matching
        baker_skills = [s.lower() for s in (baker.skills or [])]
        baker_specialties = [s.lower() for s in (baker.specialties or [])]
        all_baker_skills = set(baker_skills + baker_specialties)

        if required_skills:
            matched_skills = [s for s in required_skills if s.lower() in all_baker_skills]
            skill_score = len(matched_skills) / len(required_skills)
        else:
            skill_score = 1.0  # No specific skills required = all bakers match

        # Rating score (0.0 to 1.0)
        rating_score = min(1.0, (baker.avg_rating or 4.5) / 5.0)

        # Queue availability (simple: check if under max daily orders)
        max_orders = baker.max_daily_orders or 10
        queue_score = max(0, (max_orders - (baker.total_orders_completed or 0) % max_orders)) / max_orders

        # Composite ranking score (additive factor including proximity)
        if distance_km is not None:
            total_score = (
                (skill_score * 0.35)
                + (proximity_score * 0.35)
                + (rating_score * 0.20)
                + (queue_score * 0.10)
            )
        else:
            total_score = (
                (skill_score * 0.50)
                + (rating_score * 0.30)
                + (queue_score * 0.20)
            )

        matches.append({
            "baker_id": baker.id,
            "business_name": baker.business_name,
            "skills": baker.skills or [],
            "specialties": baker.specialties or [],
            "avg_rating": baker.avg_rating or 5.0,
            "city": baker.city,
            "area": baker.area or "",
            "distance_km": distance_km,
            "avg_prep_time_mins": baker.avg_prep_time_mins or 45,
            "delivery_radius_km": baker.delivery_radius_km or 7.0,
            "skill_score": round(skill_score, 2),
            "total_score": round(total_score, 2),
            "accepts_ai_custom": baker.accepts_ai_custom_orders,
        })

    # Sort by total score descending (highest score first)
    matches.sort(key=lambda x: x["total_score"], reverse=True)
    return matches


async def assign_baker_to_order(
    order_id: str,
    required_skills: list[str] = None,
    city: Optional[str] = None,
    delivery_lat: Optional[float] = None,
    delivery_lng: Optional[float] = None,
    db: AsyncSession = None,
) -> Optional[str]:
    """
    Auto-assign the best-matching baker to an order.
    Returns the assigned baker_id or None if no match.
    """
    matches = await find_matching_bakers(
        required_skills=required_skills or [],
        city=city,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng,
        db=db,
    )

    if matches:
        return matches[0]["baker_id"]
    return None

