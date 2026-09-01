"""
Cravin — AI Customizer Service (Shared)
Called by both Customer app and Admin panel.
Phase 1: scoped customization (sweetness, protein, allergies) on a fixed menu.
"""

import json
import os
from typing import Optional
from app.config import get_settings

settings = get_settings()

# Ingredient rules — hard constraints
APPROVED_SWEETENERS = [
    "monk fruit", "stevia", "allulose", "dates", "medjool dates",
    "date syrup", "jaggery", "coconut sugar", "date paste"
]

APPROVED_FLOURS = [
    "almond flour", "oat flour", "ragi flour", "finger millet flour",
    "whole wheat flour", "coconut flour", "foxtail millet flour",
    "jowar flour", "bajra flour"
]

BANNED_INGREDIENTS = [
    "refined sugar", "white sugar", "caster sugar", "powdered sugar",
    "maida", "all-purpose flour", "refined flour", "corn syrup",
    "high fructose corn syrup", "artificial sweetener", "aspartame",
    "sucralose", "saccharin", "artificial preservative",
    "artificial color", "artificial flavoring"
]

PROTEIN_BOOST_OPTIONS = {
    "whey": {"name": "whey protein isolate", "per_scoop_g": 25, "calories": 110, "protein": 25},
    "pea": {"name": "pea protein powder", "per_scoop_g": 25, "calories": 100, "protein": 20},
    "hemp": {"name": "hemp protein powder", "per_scoop_g": 25, "calories": 120, "protein": 15},
    "none": None,
}

SWEETNESS_ADJUSTMENTS = {
    "low": 0.5,    # 50% of base sweetener
    "medium": 1.0,  # standard
    "high": 1.3,    # 130% of base sweetener
}

HEALTH_DISCLAIMER = (
    "⚕️ This information is for general reference only and does not constitute "
    "medical or nutritional advice. Please consult a healthcare professional "
    "for dietary guidance specific to your health conditions."
)


# ── Mock AI responses for when no API key is configured ──────────────

MOCK_RESPONSES = {
    "low_sweetness": "I've reduced the sweetener to half — you'll get a subtle natural sweetness from the {sweetener}, letting the {flavor} really shine through.",
    "high_sweetness": "I've bumped up the {sweetener} for a richer sweetness. Still zero refined sugar — just more of nature's goodness.",
    "protein_boost": "Added a scoop of {protein_source} — that's an extra {protein_g}g of protein per serving without changing the texture much.",
    "allergy_swap": "I've swapped out {removed} and used {replacement} instead. Same great taste, completely {allergen}-free.",
    "default": "Here's your customized {dessert_name}! I've adjusted it to match your preferences while keeping it 100% free of refined sugar and maida.",
}


async def customize_dessert(
    dessert: dict,
    sweetness: str = "medium",
    protein_boost: Optional[str] = None,
    exclude_allergens: list[str] = None,
    user_message: Optional[str] = None,
    user_allergies: list[str] = None,
) -> dict:
    """
    Customize a base dessert within the Cravin ingredient rules.

    Returns a dict with:
    - modified_ingredients: updated ingredient list
    - ai_message: conversational explanation
    - customization_summary: structured summary
    - disclaimer: health disclaimer
    """
    exclude_allergens = exclude_allergens or []
    user_allergies = user_allergies or []

    # Merge user's profile allergies (hard constraint) with request exclusions
    all_exclusions = list(set(exclude_allergens + user_allergies))

    # Start with the base dessert's ingredients
    base_ingredients = list(dessert.get("base_ingredients", []))
    modifications = []
    modified_ingredients = []

    # ── 1. Apply sweetness adjustment ──
    for ing in base_ingredients:
        new_ing = dict(ing)
        name_lower = ing["name"].lower()

        # Check if this is a sweetener
        is_sweetener = any(s in name_lower for s in APPROVED_SWEETENERS)
        if is_sweetener and sweetness != "medium":
            factor = SWEETNESS_ADJUSTMENTS.get(sweetness, 1.0)
            new_ing["quantity_g"] = round(ing["quantity_g"] * factor, 1)
            modifications.append(f"sweetness → {sweetness}")

        modified_ingredients.append(new_ing)

    # ── 2. Apply allergy exclusions (HARD CONSTRAINT) ──
    allergen_map = {
        "nuts": {
            "triggers": ["almond", "walnut", "pistachio", "cashew", "peanut", "hazelnut"],
            "flour_replacement": {"almond flour": "oat flour"},
            "other_replacement": "seeds (sunflower/pumpkin)",
        },
        "dairy": {
            "triggers": ["milk", "cream", "butter", "ghee", "paneer", "khoya", "curd", "yogurt", "cheese"],
            "replacement": "coconut cream / coconut oil",
        },
        "gluten": {
            "triggers": ["wheat", "oat", "barley"],
            "flour_replacement": {"whole wheat flour": "coconut flour", "oat flour": "almond flour"},
        },
        "eggs": {
            "triggers": ["egg"],
            "replacement": "flax egg (ground flaxseed + water)",
        },
        "soy": {
            "triggers": ["soy", "tofu"],
            "replacement": "coconut-based alternative",
        },
    }

    safe_ingredients = []
    for ing in modified_ingredients:
        name_lower = ing["name"].lower()
        excluded = False

        for allergen in all_exclusions:
            allergen_lower = allergen.lower()
            if allergen_lower in allergen_map:
                triggers = allergen_map[allergen_lower]["triggers"]
                if any(t in name_lower for t in triggers):
                    # Replace with safe alternative
                    replacements = allergen_map[allergen_lower]
                    if "flour_replacement" in replacements and ing["name"] in replacements["flour_replacement"]:
                        replacement_name = replacements["flour_replacement"][ing["name"]]
                        safe_ingredients.append({
                            "name": replacement_name,
                            "quantity_g": ing["quantity_g"],
                        })
                        modifications.append(f"replaced {ing['name']} with {replacement_name} ({allergen}-free)")
                    else:
                        rep = replacements.get("other_replacement", replacements.get("replacement", "safe alternative"))
                        safe_ingredients.append({
                            "name": rep,
                            "quantity_g": ing["quantity_g"],
                        })
                        modifications.append(f"removed {ing['name']} ({allergen}-free)")
                    excluded = True
                    break

        if not excluded:
            safe_ingredients.append(ing)

    modified_ingredients = safe_ingredients

    # ── 3. Add protein boost ──
    if protein_boost and protein_boost in PROTEIN_BOOST_OPTIONS and protein_boost != "none":
        protein_info = PROTEIN_BOOST_OPTIONS[protein_boost]
        modified_ingredients.append({
            "name": protein_info["name"],
            "quantity_g": protein_info["per_scoop_g"],
        })
        modifications.append(f"added {protein_info['name']} (+{protein_info['protein']}g protein)")

    # ── 4. Validate — ensure no banned ingredients snuck in ──
    for ing in modified_ingredients:
        name_lower = ing["name"].lower()
        for banned in BANNED_INGREDIENTS:
            if banned in name_lower:
                raise ValueError(f"Recipe validation failed: '{ing['name']}' is not allowed in Cravin desserts.")

    # ── 5. Generate AI message ──
    if settings.is_ai_mock_mode:
        ai_message = _generate_mock_message(dessert, sweetness, protein_boost, all_exclusions, modifications)
    else:
        ai_message = await _generate_ai_message(dessert, sweetness, protein_boost, all_exclusions, modifications, user_message)

    return {
        "modified_ingredients": modified_ingredients,
        "ai_message": ai_message,
        "customization_summary": {
            "sweetness": sweetness,
            "protein_boost": protein_boost,
            "excluded_allergens": all_exclusions,
            "modifications": modifications,
        },
        "disclaimer": HEALTH_DISCLAIMER,
    }


def _generate_mock_message(
    dessert: dict, sweetness: str, protein_boost: Optional[str],
    exclusions: list[str], modifications: list[str]
) -> str:
    """Generate a friendly mock AI message without calling any API."""
    dessert_name = dessert.get("name", "your dessert")
    parts = [f"✨ Here's your customized **{dessert_name}**!\n"]

    if sweetness != "medium":
        sweetener = "natural sweetener"
        for ing in dessert.get("base_ingredients", []):
            if any(s in ing["name"].lower() for s in APPROVED_SWEETENERS):
                sweetener = ing["name"]
                break
        if sweetness == "low":
            parts.append(f"🍯 Reduced the {sweetener} for a more subtle sweetness — the natural flavors take center stage.")
        else:
            parts.append(f"🍯 Boosted the {sweetener} for a richer, more indulgent sweetness. Still 100% natural!")

    if protein_boost and protein_boost != "none":
        info = PROTEIN_BOOST_OPTIONS[protein_boost]
        parts.append(f"💪 Added {info['name']} for an extra {info['protein']}g protein per serving.")

    if exclusions:
        parts.append(f"🛡️ Made it completely free of: {', '.join(exclusions)}.")

    parts.append(f"\nAll ingredients remain zero refined sugar, zero maida. Fresh, made-to-order by your baker.")
    parts.append(f"\n{HEALTH_DISCLAIMER}")

    return "\n".join(parts)


async def _generate_ai_message(
    dessert: dict, sweetness: str, protein_boost: Optional[str],
    exclusions: list[str], modifications: list[str], user_message: Optional[str]
) -> str:
    """Call OpenAI API for a conversational customization message."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        system_prompt = f"""You are Cravin's AI dessert customizer. You help users customize healthy Indian desserts.

HARD RULES (NEVER break these):
1. NEVER include refined sugar, white sugar, caster sugar, powdered sugar, or any artificial sweetener
2. NEVER include maida (all-purpose flour / refined flour)
3. NEVER include artificial preservatives, colors, or flavors
4. Approved sweeteners ONLY: {', '.join(APPROVED_SWEETENERS)}
5. Approved flours ONLY: {', '.join(APPROVED_FLOURS)}
6. User allergies are ABSOLUTE constraints — NEVER include an allergen, even as a trace ingredient
7. User allergen exclusions for this request: {', '.join(exclusions) if exclusions else 'none'}

STYLE: Be warm, knowledgeable, concise. Use 2-3 short paragraphs max. Use food emojis sparingly.
End every response with the disclaimer: "{HEALTH_DISCLAIMER}"
"""

        user_prompt = f"""Base dessert: {dessert.get('name', 'Unknown')}
Base ingredients: {json.dumps(dessert.get('base_ingredients', []))}
Requested sweetness: {sweetness}
Protein boost: {protein_boost or 'none'}
Allergen exclusions: {', '.join(exclusions) if exclusions else 'none'}
Modifications applied: {', '.join(modifications) if modifications else 'none'}
User's message: {user_message or 'No specific message'}

Explain the customization in a friendly, confident way. Mention the specific changes and why they work."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception as e:
        # Fall back to mock if API fails
        return _generate_mock_message(dessert, sweetness, protein_boost, exclusions, modifications)
