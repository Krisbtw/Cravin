import json
import openai
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.dessert import Dessert, DessertModifier
from app.models.user import User

client = openai.AsyncOpenAI()

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

async def process_natural_language_request(user_prompt: str, user: User, db: Session, active_desserts_context: str):
    # 1. Provide Context to LLM
    system_prompt = f"""
    You are Cravin's AI ordering assistant. The user has allergies: {user.allergies} and preferences: {user.dietary_prefs}.
    Current available modifiers for their cart items: {active_desserts_context}.
    If a user requests a swap (e.g., 'keto-friendly'), use the 'modify_cart_item' function with appropriate modifier IDs.
    Ensure no added modifiers conflict with their allergies.
    """

    response = await client.chat.completions.create(
        model="gpt-4o",
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
                # 2. Validate Allergies before applying
                return apply_cart_modification(db, user, args)
    
    return {"message": message.content}

def apply_cart_modification(db: Session, user: User, args: dict):
    # Strict validation logic here against user.allergies
    added_modifiers = args.get("added_modifier_ids", [])
    if user.allergies:
        for mod_id in added_modifiers:
            modifier = db.query(DessertModifier).filter(DessertModifier.id == mod_id).first()
            if modifier and modifier.allergen_adds:
                # Check for conflicts
                for allergen in modifier.allergen_adds:
                    if allergen in user.allergies:
                        return {"status": "error", "message": f"Cannot apply modifier: introduces allergen '{allergen}'"}
                        
    # Return updated cart state (sync via WebSockets/REST)
    return {"status": "success", "cart_updated": True, "details": args}
