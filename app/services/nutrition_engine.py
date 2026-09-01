"""
Cravin — Nutrition Calculation Engine
Deterministic math from a proper ingredient database. NOT LLM-computed.
"""

import json
import os
from typing import Optional
from pathlib import Path


# Load the nutrition database
DATA_DIR = Path(__file__).parent.parent / "data"


def _load_nutrition_db() -> dict:
    """Load the ingredient nutrition database."""
    db_path = DATA_DIR / "nutrition_db.json"
    if db_path.exists():
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Cache the database in memory
_nutrition_db: Optional[dict] = None


def get_nutrition_db() -> dict:
    global _nutrition_db
    if _nutrition_db is None:
        _nutrition_db = _load_nutrition_db()
    return _nutrition_db


def reload_nutrition_db():
    """Force reload (useful after data updates)."""
    global _nutrition_db
    _nutrition_db = _load_nutrition_db()


def calculate_ingredient_nutrition(ingredient_name: str, quantity_g: float) -> dict:
    """
    Calculate nutrition for a single ingredient at a given quantity.
    Returns per-quantity values (not per-100g).
    """
    db = get_nutrition_db()

    # Normalize the name for lookup
    lookup_key = ingredient_name.lower().strip()

    # Try exact match, then partial match
    entry = db.get(lookup_key)
    if not entry:
        # Try partial matching
        for key, val in db.items():
            if lookup_key in key or key in lookup_key:
                entry = val
                break

    if not entry:
        # Unknown ingredient — return zeros with a warning
        return {
            "calories": 0, "protein_g": 0, "carbs_g": 0,
            "fat_g": 0, "fiber_g": 0, "sugar_equivalent_g": 0,
            "warning": f"Nutrition data not found for '{ingredient_name}'",
        }

    # nutrition_db stores values per 100g — scale to actual quantity
    factor = quantity_g / 100.0

    return {
        "calories": round(entry.get("calories", 0) * factor, 1),
        "protein_g": round(entry.get("protein_g", 0) * factor, 1),
        "carbs_g": round(entry.get("carbs_g", 0) * factor, 1),
        "fat_g": round(entry.get("fat_g", 0) * factor, 1),
        "fiber_g": round(entry.get("fiber_g", 0) * factor, 1),
        "sugar_equivalent_g": round(entry.get("sugar_equivalent_g", 0) * factor, 1),
    }


def calculate_recipe_nutrition(ingredients: list[dict], servings: int = 1) -> dict:
    """
    Calculate total and per-serving nutrition for a complete recipe.

    ingredients: [{"name": "ragi flour", "quantity_g": 100}, ...]
    servings: number of servings the recipe yields

    Returns:
    {
        "per_serving": {"calories": ..., "protein_g": ..., ...},
        "total": {"calories": ..., "protein_g": ..., ...},
        "per_ingredient": [...],
        "allergens": [...],
        "tag": "light" | "balanced" | "heavy",
        "warnings": [...]
    }
    """
    db = get_nutrition_db()
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0, "sugar_equivalent_g": 0}
    per_ingredient = []
    allergens = set()
    warnings = []

    for ing in ingredients:
        name = ing.get("name", "")
        qty = ing.get("quantity_g", 0)

        nutrition = calculate_ingredient_nutrition(name, qty)

        if "warning" in nutrition:
            warnings.append(nutrition["warning"])

        per_ingredient.append({
            "name": name,
            "quantity_g": qty,
            **{k: v for k, v in nutrition.items() if k != "warning"},
        })

        # Accumulate totals
        for key in totals:
            totals[key] += nutrition.get(key, 0)

        # Detect allergens from the database
        lookup_key = name.lower().strip()
        entry = db.get(lookup_key, {})
        if not entry:
            for key, val in db.items():
                if lookup_key in key or key in lookup_key:
                    entry = val
                    break

        ing_allergens = entry.get("allergens", [])
        allergens.update(ing_allergens)

    # Round totals
    for key in totals:
        totals[key] = round(totals[key], 1)

    # Per-serving
    per_serving = {key: round(val / max(servings, 1), 1) for key, val in totals.items()}

    # Tag classification (per serving)
    cal = per_serving["calories"]
    if cal < 150:
        tag = "light"
    elif cal <= 300:
        tag = "balanced"
    else:
        tag = "heavy"

    return {
        "per_serving": per_serving,
        "total": totals,
        "per_ingredient": per_ingredient,
        "allergens": sorted(list(allergens)),
        "tag": tag,
        "servings": servings,
        "warnings": warnings,
    }


def get_daily_nutrition_summary(logs: list[dict], calorie_goal: float = 2000) -> dict:
    """
    Summarize daily nutrition intake vs goal.
    Used for the donut calorie indicator on the profile page.

    logs: list of nutrition log entries for today
    """
    totals = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0}

    for log in logs:
        for key in totals:
            totals[key] += log.get(key, 0)

    for key in totals:
        totals[key] = round(totals[key], 1)

    progress = min(round(totals["calories"] / max(calorie_goal, 1) * 100, 1), 100)

    return {
        "consumed": totals,
        "calorie_goal": calorie_goal,
        "calories_remaining": round(max(calorie_goal - totals["calories"], 0), 1),
        "progress_percent": progress,
    }
