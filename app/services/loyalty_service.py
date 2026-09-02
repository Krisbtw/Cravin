"""
Cravin — Loyalty Service (Sweet Streak)
Points, streaks, tiers, badges, referrals.
"""

from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction, LoyaltyTier, TIER_THRESHOLDS


# Points config
POINTS_PER_ORDER = 10
POINTS_PER_100_INR = 5
STREAK_BONUS_MULTIPLIER = {
    0: 1.0,
    3: 1.2,   # 3-week streak → 20% bonus
    5: 1.5,   # 5-week streak → 50% bonus
    10: 2.0,  # 10-week streak → 2x bonus
}
REFERRAL_BONUS = 50
REFEREE_BONUS = 25  # person who was referred gets this too

# Badge definitions
BADGE_CRITERIA = {
    "first_order": {"description": "Placed your first order!", "icon": "🎉"},
    "5_streak": {"description": "5-week ordering streak!", "icon": "🔥"},
    "10_streak": {"description": "10-week ordering streak!", "icon": "⚡"},
    "tried_5_bakers": {"description": "Ordered from 5 different bakers", "icon": "🧑‍🍳"},
    "customizer_pro": {"description": "Customized 5 desserts with AI", "icon": "🤖"},
    "ragi_lover": {"description": "Ordered 3+ ragi-based desserts", "icon": "🌾"},
    "health_hero": {"description": "Stayed under calorie goal for 7 days", "icon": "💪"},
    "referral_star": {"description": "Referred 3 friends", "icon": "⭐"},
    "silver_member": {"description": "Reached Silver tier!", "icon": "🥈"},
    "gold_member": {"description": "Reached Gold tier!", "icon": "🥇"},
}


async def award_order_points(
    user_id: str, order_total: float, order_id: str, db: AsyncSession
) -> dict:
    """Award points for completing an order. Returns points earned and any new badges/tier changes."""
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return {"points_earned": 0, "new_badges": [], "tier_change": None}

    # Calculate base points
    base_points = POINTS_PER_ORDER + int(order_total / 100) * POINTS_PER_100_INR

    # Apply streak multiplier
    multiplier = 1.0
    for threshold, mult in sorted(STREAK_BONUS_MULTIPLIER.items(), reverse=True):
        if account.current_streak >= threshold:
            multiplier = mult
            break

    total_points = int(base_points * multiplier)

    # Update account
    account.points_balance += total_points
    account.lifetime_points += total_points
    account.last_order_date = date.today()

    # Update streak
    _update_streak(account)

    # Check for tier upgrade
    old_tier = account.tier
    new_tier = _calculate_tier(account.lifetime_points)
    tier_change = None
    if new_tier != old_tier:
        account.tier = new_tier
        tier_change = {"from": old_tier, "to": new_tier}

    # Check for new badges
    new_badges = _check_badges(account)

    # Record transaction
    transaction = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        account_id=account.id,
        type="earn",
        points=total_points,
        description=f"Order #{order_id[:8]} — {base_points} base × {multiplier}x streak bonus",
        order_id=order_id,
    )
    db.add(transaction)

    return {
        "points_earned": total_points,
        "new_badges": new_badges,
        "tier_change": tier_change,
        "streak": account.current_streak,
        "total_balance": account.points_balance,
    }


async def redeem_points(
    user_id: str, points: int, order_id: str, db: AsyncSession
) -> dict:
    """Redeem points for a discount. 100 points = ₹10 off."""
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account or account.points_balance < points:
        return {"success": False, "message": "Not enough points"}

    discount_inr = points / 10  # 100 points = ₹10

    account.points_balance -= points

    transaction = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        account_id=account.id,
        type="redeem",
        points=-points,
        description=f"Redeemed for ₹{discount_inr:.0f} off on order #{order_id[:8]}",
        order_id=order_id,
    )
    db.add(transaction)

    return {"success": True, "discount_inr": discount_inr, "remaining_points": account.points_balance}


async def process_referral(
    referrer_code: str, new_user_id: str, db: AsyncSession
) -> dict:
    """Process a referral when a new user signs up with a referral code."""
    # Find the referrer
    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.referral_code == referrer_code)
    )
    referrer_account = result.scalar_one_or_none()
    if not referrer_account:
        return {"success": False, "message": "Invalid referral code"}

    # Award referrer
    referrer_account.points_balance += REFERRAL_BONUS
    referrer_account.lifetime_points += REFERRAL_BONUS
    referrer_account.referral_count += 1

    ref_txn = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        account_id=referrer_account.id,
        type="referral",
        points=REFERRAL_BONUS,
        description=f"Referral bonus — friend joined Cravin!",
    )
    db.add(ref_txn)

    # Award the new user
    new_result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == new_user_id)
    )
    new_account = new_result.scalar_one_or_none()
    if new_account:
        new_account.points_balance += REFEREE_BONUS
        new_account.lifetime_points += REFEREE_BONUS
        new_account.referred_by = referrer_account.user_id

        new_txn = LoyaltyTransaction(
            id=str(uuid.uuid4()),
            account_id=new_account.id,
            type="referral",
            points=REFEREE_BONUS,
            description="Welcome bonus — joined via referral!",
        )
        db.add(new_txn)

    return {"success": True, "referrer_points": REFERRAL_BONUS, "referee_points": REFEREE_BONUS}


def _update_streak(account: LoyaltyAccount):
    """Update ordering streak. A streak continues if the user orders at least once per week."""
    today = date.today()
    if account.last_order_date:
        days_since = (today - account.last_order_date).days
        if days_since <= 7:
            # Within the week — streak continues
            pass
        elif days_since <= 14:
            # Missed a week but came back — increment streak
            account.current_streak += 1
        else:
            # Streak broken
            account.current_streak = 1
    else:
        account.current_streak = 1

    account.longest_streak = max(account.longest_streak, account.current_streak)


def _calculate_tier(lifetime_points: int) -> str:
    """Determine tier based on lifetime points."""
    tier = LoyaltyTier.BRONZE.value
    for t, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if lifetime_points >= threshold:
            tier = t.value
            break
    return tier


def _check_badges(account: LoyaltyAccount) -> list[str]:
    """Check and award new badges. Returns list of newly earned badge names."""
    current_badges = set(account.badges or [])
    new_badges = []

    if account.lifetime_points > 0 and "first_order" not in current_badges:
        new_badges.append("first_order")

    if account.current_streak >= 5 and "5_streak" not in current_badges:
        new_badges.append("5_streak")

    if account.current_streak >= 10 and "10_streak" not in current_badges:
        new_badges.append("10_streak")

    if account.referral_count >= 3 and "referral_star" not in current_badges:
        new_badges.append("referral_star")

    if account.tier == LoyaltyTier.SILVER.value and "silver_member" not in current_badges:
        new_badges.append("silver_member")

    if account.tier == LoyaltyTier.GOLD.value and "gold_member" not in current_badges:
        new_badges.append("gold_member")

    if new_badges:
        from sqlalchemy.orm.attributes import flag_modified
        account.badges = list(current_badges | set(new_badges))
        flag_modified(account, "badges")

    return new_badges


async def sync_user_loyalty(user_id: str, db: AsyncSession) -> LoyaltyAccount:
    """Ensure user loyalty account exists and badges/points are synchronized with order history."""
    from app.models.order import Order, OrderItem
    from sqlalchemy.orm import selectinload
    from sqlalchemy.orm.attributes import flag_modified

    result = await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        import random, string
        ref_code = "CRAV" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        account = LoyaltyAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            points_balance=0,
            lifetime_points=0,
            tier=LoyaltyTier.BRONZE.value,
            current_streak=0,
            longest_streak=0,
            referral_code=ref_code,
            badges=[],
        )
        db.add(account)
        await db.flush()

    # Query all active/placed/delivered orders for this user
    orders_res = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.dessert))
        .where(Order.user_id == user_id, Order.status != "cancelled")
    )
    orders = orders_res.scalars().all()

    current_badges = set(account.badges or [])
    new_badges = set()

    # 1. First Order badge and points
    if len(orders) >= 1:
        new_badges.add("first_order")
        # Ensure user has points earned for their placed orders
        if account.lifetime_points == 0:
            total_earned = 0
            for o in orders:
                pts = POINTS_PER_ORDER + int(o.total_amount / 100) * POINTS_PER_100_INR
                total_earned += pts
            account.points_balance = total_earned
            account.lifetime_points = total_earned
            if account.current_streak == 0:
                account.current_streak = 1
                account.longest_streak = 1
            account.last_order_date = date.today()

    # 2. Check bakers count
    baker_ids = {o.baker_id for o in orders if o.baker_id}
    if len(baker_ids) >= 5:
        new_badges.add("tried_5_bakers")

    # 3. Check customizer orders
    custom_count = sum(1 for o in orders for item in o.items if item.is_customized)
    if custom_count >= 5:
        new_badges.add("customizer_pro")

    # 4. Check ragi lovers
    ragi_count = sum(1 for o in orders for item in o.items if item.dessert and "ragi" in item.dessert.name.lower())
    if ragi_count >= 3:
        new_badges.add("ragi_lover")

    # 5. Check streak badges
    if account.current_streak >= 5:
        new_badges.add("5_streak")
    if account.current_streak >= 10:
        new_badges.add("10_streak")

    # 6. Check tier badges
    account.tier = _calculate_tier(account.lifetime_points)
    if account.tier == LoyaltyTier.SILVER.value:
        new_badges.add("silver_member")
    if account.tier == LoyaltyTier.GOLD.value:
        new_badges.add("gold_member")

    combined = list(current_badges | new_badges)
    account.badges = combined
    flag_modified(account, "badges")

    await db.commit()
    await db.refresh(account)
    return account


