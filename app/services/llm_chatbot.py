"""
Cravin — LLM Chatbot Service
Natural language conversational ordering assistant with allergen validation.
"""

import json
import openai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.dessert import DessertModifier
from app.models.user import User
from app.config import get_settings

settings = get_settings()

# Define the tool schema for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "modify_cart_item",
            "description": "Modifies a user's cart item (dessert) based on dietary requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dessert_id": {"type": "string"},
                    "added_modifier_ids": {"type": "array", "items": {"type": "string"}},
                    "removed_modifier_ids": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["dessert_id"]
            }
        }
    }
]


async def process_natural_language_request(
    user_prompt: str,
    user: User,
    db: AsyncSession,
    active_desserts_context: str = "",
) -> dict:
    """
    Process conversational request and validate modifications.
    """
    if settings.is_ai_mock_mode:
        return {
            "message": f"I can help customize your order! (Mock Mode: User preferences for {user.full_name} applied)."
        }

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    system_prompt = f"""
    You are Cravin's AI ordering assistant. The user has allergies: {user.allergies} and preferences: {user.dietary_prefs}.
    Current available modifiers for their cart items: {active_desserts_context}.
    If a user requests a swap (e.g., 'keto-friendly'), use the 'modify_cart_item' function with appropriate modifier IDs.
    Ensure no added modifiers conflict with their allergies.
    """

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "modify_cart_item":
                args = json.loads(tool_call.function.arguments)
                return await apply_cart_modification(db, user, args)

    return {"message": message.content}


async def apply_cart_modification(db: AsyncSession, user: User, args: dict) -> dict:
    """
    Strict validation against user.allergies before applying cart changes.
    """
    added_modifiers = args.get("added_modifier_ids", [])
    if user.allergies:
        for mod_id in added_modifiers:
            result = await db.execute(
                select(DessertModifier).where(DessertModifier.id == mod_id)
            )
            modifier = result.scalar_one_or_none()
            if modifier and modifier.allergen_adds:
                # Check for conflicts
                for allergen in modifier.allergen_adds:
                    if allergen in user.allergies:
                        return {
                            "status": "error",
                            "message": f"Cannot apply modifier: introduces allergen '{allergen}'",
                        }

    return {"status": "success", "cart_updated": True, "details": args}
