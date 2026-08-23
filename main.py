"""
South Asian Food Oil Analyser
=============================
Runs a Gemini-powered calorie analysis on a food image, shows an initial
estimate, then lets you amend the oil content and/or dish weight before
printing the final adjusted figures.

Usage
-----
    python main.py                          # fully interactive
    python main.py --image path/to/img.jpg  # skip the image-path prompt
    python main.py --image img.jpg --model gemini-2.5-flash
    python main.py --image img.jpg --api-key YOUR_KEY

Environment variables
---------------------
    GEMINI_API_KEY   Gemini API key (alternative to --api-key flag)
"""

import argparse
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on environment variables

from analyzer import (
    CalorieAnalysis,
    OIL_GRAMS_PER_TBSP,
    OIL_GRAMS_PER_TSP,
    adjust_dish_weight,
    adjust_oil_calories,
    analyze_food_image,
    convert_oil_to_grams,
    format_oil_grams,
)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gemini-3.6-flash"
AVAILABLE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.6-flash-lite",
    "gemini-3.5-flash",
]

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def print_analysis(label: str, a: CalorieAnalysis) -> None:
    width = 54
    print(f"\n{'=' * width}")
    print(f"  {label}")
    print(f"{'=' * width}")
    print(f"  Dish           : {a.dish_name}")
    print(f"  South Asian    : {'Yes' if a.is_south_asian_food else 'No'}")
    print(f"  Portion        : {a.estimated_weight_grams:.0f} g")
    print(f"  Calories       : {a.total_calories} kcal")
    print(f"  Protein        : {a.macros.protein_grams:.1f} g")
    print(f"  Carbs          : {a.macros.carbs_grams:.1f} g")
    print(f"  Fat            : {a.macros.fat_grams:.1f} g")
    print(f"  Confidence     : {a.confidence_score:.0%}")
    if a.notes:
        print(f"  Notes          : {a.notes}")
    if a.intervention_needed:
        print(
            f"  *** Oil intervention suggested: "
            f"{format_oil_grams(a.suggested_oil_adjustment_grams)} extra ***"
        )
    print(f"{'=' * width}")


# ---------------------------------------------------------------------------
# Interactive prompt helpers
# ---------------------------------------------------------------------------


def prompt_yes_no(question: str, default: bool = True) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{question} {hint}: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please enter y or n.")


def prompt_oil_adjustment() -> tuple[float, str] | None:
    """
    Ask the user for an oil adjustment.
    Returns (amount, unit) or None if the user skips.
    """
    print(
        "\nOil/ghee adjustment:"
        "\n  Enter an amount and unit, e.g.  '1.5 tsp'  '-0.5 tbsp'  '10 grams'"
        "\n  Use a negative value to remove oil.  Press Enter to skip."
    )
    while True:
        raw = input("  Adjustment: ").strip()
        if raw == "":
            return None
        parts = raw.split()
        if len(parts) == 2:
            try:
                amount = float(parts[0])
                unit = parts[1].lower()
                # Validate unit by attempting conversion
                convert_oil_to_grams(amount, unit)
                return amount, unit
            except ValueError as e:
                print(f"  Error: {e}")
        else:
            print("  Expected format: <number> <unit>  e.g. '1.5 tsp'")


def prompt_weight_adjustment(current_weight: float) -> float | None:
    """
    Ask the user for a new dish weight in grams.
    Returns the new weight or None to skip.
    """
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
            w = float(raw)
            if w <= 0:
                print("  Weight must be positive.")
            else:
                return w
        except ValueError:
            print("  Please enter a number.")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse South Asian food images for calories and oil content.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--image", "-i",
        metavar="PATH",
        help="Path to the food image file.",
    )
    parser.add_argument(
        "--model", "-m",
        metavar="MODEL",
        default=DEFAULT_MODEL,
        help=(
            f"Gemini model to use. Default: {DEFAULT_MODEL}. "
            f"Options: {', '.join(AVAILABLE_MODELS)} (or any current Gemini model)"
        ),
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="Gemini API key (overrides GEMINI_API_KEY environment variable).",
    )
    return parser


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- Resolve API key ---
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No Gemini API key found.")
        print("Set the GEMINI_API_KEY environment variable or use --api-key.")
        sys.exit(1)

    # --- Resolve image path ---
    image_path = args.image
    if not image_path:
        image_path = input("Enter the path to the food image: ").strip()
        if not image_path:
            print("Error: No image path provided.")
            sys.exit(1)

    image_path = os.path.expanduser(image_path)
    if not os.path.isfile(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    # --- Run initial analysis ---
    print(f"\nAnalysing image with {args.model} ...")
    try:
        result = analyze_food_image(image_path, model=args.model, api_key=api_key)
    except Exception as exc:
        print(f"Error during analysis: {exc}")
        sys.exit(1)

    print_analysis("Initial Estimate", result)

    # --- Apply suggested oil intervention if flagged ---
    current = result
    if result.intervention_needed and result.suggested_oil_adjustment_grams != 0:
        adj_label = format_oil_grams(result.suggested_oil_adjustment_grams)
        if prompt_yes_no(
            f"\nApply the suggested oil adjustment ({adj_label})?"
        ):
            current = adjust_oil_calories(
                current,
                result.suggested_oil_adjustment_grams,
                "grams",
            )
            print_analysis("After Suggested Oil Adjustment", current)

    # --- Custom oil adjustment ---
    oil_adj = prompt_oil_adjustment()
    if oil_adj is not None:
        amount, unit = oil_adj
        current = adjust_oil_calories(current, amount, unit)
        print_analysis("After Custom Oil Adjustment", current)

    # --- Weight scaling ---
    new_weight = prompt_weight_adjustment(current.estimated_weight_grams)
    if new_weight is not None:
        current = adjust_dish_weight(current, new_weight)
        print_analysis("After Weight Adjustment", current)

    # --- Final summary ---
    if oil_adj is not None or new_weight is not None or (
        result.intervention_needed and result.suggested_oil_adjustment_grams != 0
    ):
        print_analysis("FINAL RESULT", current)
    else:
        print("\nNo adjustments made. The initial estimate is your final result.")


if __name__ == "__main__":
    main()
