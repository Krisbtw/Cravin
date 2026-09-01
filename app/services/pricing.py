import math

def calculate_surge_fee(base_fee: float, active_bakers: int, active_orders: int, distance_km: float, traffic_index: float) -> float:
    """
    Mathematical pricing function for surge fee.
    traffic_index: 1.0 (clear) to 2.0 (heavy traffic)
    """
    # Prevent division by zero
    bakers = max(active_bakers, 1)
    
    # Order-to-Baker Ratio
    density_ratio = active_orders / bakers
    
    # Exponential surge based on density, capped at a max multiplier
    density_multiplier = min(math.exp(0.2 * (density_ratio - 1)), 2.5) if density_ratio > 1 else 1.0
    
    # Distance and Traffic Impact
    logistics_multiplier = 1.0 + (distance_km * 0.05) + (traffic_index - 1.0)
    
    total_multiplier = density_multiplier * logistics_multiplier
    
    return round(base_fee * total_multiplier, 2)
