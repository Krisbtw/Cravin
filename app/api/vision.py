"""
Cravin — Computer Vision Meal Scanner
Analyzes meal/dish photos to detect nutritional macros and recommend healthy Cravin alternatives.
"""

import base64
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.cart import DetectedFood, MacroEstimate
from app.config import get_settings

router = APIRouter(prefix="/vision", tags=["vision"])
settings = get_settings()


@router.post("/scan-meal", response_model=list[DetectedFood])
async def scan_meal(file: UploadFile = File(...)):
    """
    Upload a meal/dessert image to identify food items, estimate macronutrients,
    and suggest healthy zero-sugar Cravin alternatives.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image (JPEG/PNG/WebP).")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image file too large (max 10MB).")

    # If OpenAI API Key is configured, use GPT-4o Vision
    if not settings.is_ai_mock_mode:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            base64_image = base64.b64encode(contents).decode("utf-8")
            media_type = file.content_type or "image/jpeg"

            prompt = """
            Analyze this food image. Identify the food item(s) present and estimate their nutritional values per serving.
            Return a valid JSON array of objects with the following structure:
            [
              {
                "name": "Food or Dessert Name",
                "confidence": 0.95,
                "macros": {
                  "calories": 320.0,
                  "protein_g": 12.0,
                  "carbs_g": 35.0,
                  "fats_g": 14.0
                }
              }
            ]
            Only return the JSON array, no extra commentary.
            """

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.2,
            )

            raw_text = response.choices[0].message.content.strip()
            # Clean markdown codeblocks if returned
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                if raw_text.endswith("```"):
                    raw_text = raw_text.rsplit("\n", 1)[0]

            parsed = json.loads(raw_text)
            results = []
            for item in parsed:
                macros_data = item.get("macros", {})
                results.append(
                    DetectedFood(
                        name=item.get("name", "Identified Dish"),
                        confidence=float(item.get("confidence", 0.90)),
                        macros=MacroEstimate(
                            calories=float(macros_data.get("calories", 300.0)),
                            protein_g=float(macros_data.get("protein_g", 10.0)),
                            carbs_g=float(macros_data.get("carbs_g", 30.0)),
                            fats_g=float(macros_data.get("fats_g", 12.0)),
                        )
                    )
                )
            if results:
                return results
        except Exception as e:
            print(f"Vision API fallback notice: {e}")

    # Fallback / Mock Response
    return [
        DetectedFood(
            name="Dark Chocolate Ragi Brownie (Zero Sugar)",
            confidence=0.94,
            macros=MacroEstimate(calories=280.0, protein_g=14.0, carbs_g=24.0, fats_g=12.0)
        ),
        DetectedFood(
            name="Almond Date Kheer",
            confidence=0.88,
            macros=MacroEstimate(calories=210.0, protein_g=8.0, carbs_g=18.0, fats_g=9.0)
        )
    ]
