"""Quick CLI for testing the food analysis flow."""

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from analyzer import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    CalorieAnalysis,
    adjust_dish_weight,
    adjust_oil_calories,
    analyze_food_image,
    convert_oil_to_grams,
    format_oil_grams,
    normalize_model_name,
    resolve_gemini_api_key,
)


def print_analysis(label: str, analysis: CalorieAnalysis) -> None:
    width = 54
    print(f"\n{'=' * width}")
    print(f"  {label}")
    print(f"{'=' * width}")
    print(f"  Dish           : {analysis.dish_name}")
    print(f"  South Asian    : {'Yes' if analysis.is_south_asian_food else 'No'}")
    print(f"  Portion        : {analysis.estimated_weight_grams:.0f} g")
    print(f"  Calories       : {analysis.total_calories} kcal")
    print(f"  Protein        : {analysis.macros.protein_grams:.1f} g")
    print(f"  Carbs          : {analysis.macros.carbs_grams:.1f} g")
    print(f"  Fat            : {analysis.macros.fat_grams:.1f} g")
    print(f"  Confidence     : {analysis.confidence_score:.0%}")
    if analysis.notes:
        print(f"  Notes          : {analysis.notes}")
    if analysis.intervention_needed:
        print(
            f"  *** Oil intervention suggested: " 
            f"{format_oil_grams(analysis.suggested_oil_adjustment_grams)} extra ***"
        )
    print(f"{'=' * width}")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{question} {hint}: ").strip().lower()
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("  Please enter y or n.")


def prompt_oil_adjustment() -> tuple[float, str] | None:
    print(
        "\nOil/ghee adjustment:"
        "\n  Enter an amount and unit, e.g. '1.5 tsp', '-0.5 tbsp', '10 grams'"
        "\n  Press Enter to skip."
    )
    while True:
        raw = input("  Adjustment: ").strip()
        if raw == "":
            return None
        parts = raw.split()
        if len(parts) != 2:
            print("  Expected format: <number> <unit>")
            continue
        try:
            amount = float(parts[0])
            unit = parts[1].lower()
            convert_oil_to_grams(amount, unit)
            return amount, unit
        except ValueError as exc:
            print(f"  Error: {exc}")


def prompt_weight_adjustment(current_weight: float) -> float | None:
    print(
        f"\nDish weight adjustment:"
        f"\n  Current estimate: {current_weight:.0f} g"
        f"\n  Enter a new weight in grams or press Enter to skip."
    )
    while True:
        raw = input("  New weight (g): ").strip()
        if raw == "":
            return None
        try:
            weight = float(raw)
            if weight <= 0:
                print("  Weight must be positive.")
                continue
            return weight
        except ValueError:
            print("  Please enter a number.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test the food image analysis flow.")
    parser.add_argument("--image", "-i", metavar="PATH", help="Path to the food image file.")
    parser.add_argument(
        "--model",
        "-m",
        metavar="MODEL",
        default=DEFAULT_MODEL,
        help=f"Gemini model to use. Options: {', '.join(AVAILABLE_MODELS)}",
    )
    parser.add_argument("--api-key", metavar="KEY", help="Gemini API key override.")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        api_key = resolve_gemini_api_key(args.api_key)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    image_path = args.image or input("Enter the path to the food image: ").strip()
    if not image_path:
        print("Error: No image path provided.")
        sys.exit(1)

    image_path = os.path.expanduser(image_path)
    if not os.path.isfile(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    model_name = normalize_model_name(args.model)
    print(f"\nAnalysing image with {model_name} ...")
    try:
        result = analyze_food_image(image_path, model=model_name, api_key=api_key)
    except Exception as exc:
        print(f"Error during analysis: {exc}")
        sys.exit(1)

    print_analysis("Initial Estimate", result)

    current = result
    if result.intervention_needed and result.suggested_oil_adjustment_grams != 0:
        label = format_oil_grams(result.suggested_oil_adjustment_grams)
        if prompt_yes_no(f"\nApply the suggested oil adjustment ({label})?"):
            current = adjust_oil_calories(current, result.suggested_oil_adjustment_grams, "grams")
            print_analysis("After Suggested Oil Adjustment", current)

    oil_adjustment = prompt_oil_adjustment()
    if oil_adjustment is not None:
        amount, unit = oil_adjustment
        current = adjust_oil_calories(current, amount, unit)
        print_analysis("After Custom Oil Adjustment", current)

    new_weight = prompt_weight_adjustment(current.estimated_weight_grams)
    if new_weight is not None:
        current = adjust_dish_weight(current, new_weight)
        print_analysis("After Weight Adjustment", current)

    if oil_adjustment is not None or new_weight is not None or (
        result.intervention_needed and result.suggested_oil_adjustment_grams != 0
    ):
        print_analysis("FINAL RESULT", current)
    else:
        print("\nNo adjustments made. The initial estimate is your final result.")


if __name__ == "__main__":
    main()
