import os
from PIL import Image
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MacroBreakdown(BaseModel):
    protein_grams: float = Field(description="Estimated protein in grams")
    carbs_grams: float = Field(description="Estimated carbohydrates in grams")
    fat_grams: float = Field(description="Estimated total fat in grams (including oil/ghee)")


class CalorieAnalysis(BaseModel):
    dish_name: str = Field(description="Identified dish name (e.g., Paneer Butter Masala)")
    is_south_asian_food: bool = Field(description="True if the image is confirmed to be South Asian food")
    estimated_weight_grams: float = Field(description="Estimated standard portion size in grams")
    total_calories: int = Field(description="Calculated total calories for the estimated weight")
    macros: MacroBreakdown
    confidence_score: float = Field(description="Confidence from 0.0 to 1.0")
    notes: str = Field(description="Brief note on key ingredients or heavy oil/ghee presence")
    intervention_needed: bool = Field(default=False, description="True if user intervention is recommended for oil adjustment")
    suggested_oil_adjustment_grams: float = Field(default=0.0, description="Suggested oil adjustment in grams if intervention is needed")


# ---------------------------------------------------------------------------
# Oil unit conversion
# ---------------------------------------------------------------------------

OIL_GRAMS_PER_TSP = 4.5
OIL_GRAMS_PER_TBSP = 13.5


def convert_oil_to_grams(amount: float, unit: str) -> float:
    """Convert an oil amount to grams given a unit ('grams', 'tsp', or 'tbsp')."""
    unit = unit.lower().strip()
    if unit == "grams" or unit == "g":
        return amount
    elif unit == "tsp":
        return amount * OIL_GRAMS_PER_TSP
    elif unit == "tbsp":
        return amount * OIL_GRAMS_PER_TBSP
    else:
        raise ValueError(f"Unsupported unit '{unit}'. Use 'grams', 'tsp', or 'tbsp'.")


def format_oil_grams(grams: float) -> str:
    """Return a human-readable string for an oil amount in grams."""
    if grams == 0:
        return "0 g"
    elif abs(grams) < OIL_GRAMS_PER_TBSP:
        return f"{grams:.1f} g ({grams / OIL_GRAMS_PER_TSP:.1f} tsp)"
    else:
        return f"{grams:.1f} g ({grams / OIL_GRAMS_PER_TBSP:.1f} tbsp)"


# ---------------------------------------------------------------------------
# Adjustment helpers
# ---------------------------------------------------------------------------

def adjust_oil_calories(
    analysis: CalorieAnalysis,
    oil_adjustment_value: float,
    oil_adjustment_unit: str = "grams",
) -> CalorieAnalysis:
    """Return a new CalorieAnalysis with fat and calories adjusted for an oil change."""
    oil_grams = convert_oil_to_grams(oil_adjustment_value, oil_adjustment_unit)
    new_fat_grams = max(0.0, analysis.macros.fat_grams + oil_grams)
    calorie_change = (new_fat_grams - analysis.macros.fat_grams) * 9

    updated_macros = MacroBreakdown(
        protein_grams=analysis.macros.protein_grams,
        carbs_grams=analysis.macros.carbs_grams,
        fat_grams=new_fat_grams,
    )
    sign = "+" if oil_adjustment_value >= 0 else ""
    notes_suffix = (
        f" | Oil adjusted {sign}{oil_adjustment_value} {oil_adjustment_unit}"
        if oil_adjustment_value != 0
        else ""
    )
    return CalorieAnalysis(
        dish_name=analysis.dish_name,
        is_south_asian_food=analysis.is_south_asian_food,
        estimated_weight_grams=analysis.estimated_weight_grams,
        total_calories=int(analysis.total_calories + calorie_change),
        macros=updated_macros,
        confidence_score=analysis.confidence_score,
        notes=analysis.notes + notes_suffix,
        intervention_needed=False,
        suggested_oil_adjustment_grams=0.0,
    )


def adjust_dish_weight(analysis: CalorieAnalysis, new_weight_grams: float) -> CalorieAnalysis:
    """Return a new CalorieAnalysis with macros and calories scaled to a new weight."""
    if analysis.estimated_weight_grams == 0:
        raise ValueError("Cannot scale: original estimated_weight_grams is zero.")

    scale = new_weight_grams / analysis.estimated_weight_grams
    updated_macros = MacroBreakdown(
        protein_grams=analysis.macros.protein_grams * scale,
        carbs_grams=analysis.macros.carbs_grams * scale,
        fat_grams=analysis.macros.fat_grams * scale,
    )
    notes_suffix = (
        f" | Weight scaled from {analysis.estimated_weight_grams:.0f} g "
        f"to {new_weight_grams:.0f} g"
    )
    return CalorieAnalysis(
        dish_name=analysis.dish_name,
        is_south_asian_food=analysis.is_south_asian_food,
        estimated_weight_grams=new_weight_grams,
        total_calories=int(analysis.total_calories * scale),
        macros=updated_macros,
        confidence_score=analysis.confidence_score,
        notes=analysis.notes + notes_suffix,
        intervention_needed=False,
        suggested_oil_adjustment_grams=0.0,
    )


# ---------------------------------------------------------------------------
# Vision analysis
# ---------------------------------------------------------------------------

def analyze_food_image(image_path: str, model: str, api_key: str | None = None) -> CalorieAnalysis:
    """Send an image to Gemini and return a structured CalorieAnalysis."""
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    client = genai.Client()
    img = Image.open(image_path)

    prompt = (
        "Analyze this image of South Asian food.\n"
        "1. Identify the exact dish name.\n"
        "2. Estimate the portion size/weight in grams based on visual cues.\n"
        "3. Calculate total calories and macro breakdown (protein, carbs, fat). "
        "Be mindful of typical oil/ghee usage in this specific dish.\n"
        "4. If the dish is known to be traditionally high in oil/ghee (e.g., korma, "
        "butter chicken, deep-fried items), set `intervention_needed` to `true` and "
        "provide a `suggested_oil_adjustment_grams` (positive value) representing the "
        "extra oil/ghee likely present beyond a conservative estimate."
    )

    response = client.models.generate_content(
        model=model,
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CalorieAnalysis,
        ),
    )

    return CalorieAnalysis.model_validate_json(response.text)
