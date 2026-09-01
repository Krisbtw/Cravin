import numpy as np
from sqlalchemy.orm import Session
from app.models.dessert import Dessert

def calculate_hybrid_score(user_history: list, item: Dessert, current_time: str, weather: str) -> float:
    # 1. Collaborative Score (mock logic - ideally precomputed in Redis/Vector DB)
    collab_score = 0.5 # Based on similarity matrix
    
    # 2. Content-Based Score
    content_score = 0.0
    
    # Safely handle None values for dietary_flags
    dietary_flags = item.dietary_flags or []
    
    if "cold" in weather and "warm" in dietary_flags: # Adjust to Cravin tags
        content_score += 0.3
    if "morning" in current_time and "light" in [item.tag]: # Using item.tag
        content_score += 0.4
        
    # Combine (weighted)
    return (0.6 * collab_score) + (0.4 * content_score)

def get_recommendations(user_id: str, db: Session, context: dict):
    items = db.query(Dessert).filter(Dessert.is_active == True).all()
    # Score and sort items
    scored_items = [(item, calculate_hybrid_score([], item, context.get('time', ''), context.get('weather', ''))) for item in items]
    scored_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored_items[:5]]
