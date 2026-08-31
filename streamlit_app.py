import os
import tempfile
from datetime import date

import streamlit as st
from google.genai.errors import ClientError

from analyzer import (
    CalorieAnalysis,
    adjust_dish_weight,
    adjust_oil_calories,
    analyze_food_image,
    format_oil_grams,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = "gemini-3.6-flash"
AVAILABLE_MODELS = [
    "gemini-3.6-flash",
]
MEAL_TYPES = ("breakfast", "lunch", "dinner")


def get_api_key() -> str | None:
    return st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")


def load_analysis(data: dict | None) -> CalorieAnalysis | None:
    if data is None:
        return None
    return CalorieAnalysis.model_validate(data)


def save_analysis(analysis: CalorieAnalysis | None) -> None:
    st.session_state.current_analysis = (
        analysis.model_dump() if analysis is not None else None
    )


def get_logs() -> list[dict]:
    if "meal_logs" not in st.session_state:
        st.session_state.meal_logs = []
    return st.session_state.meal_logs


def add_log_entry(log_date: date, meal_type: str, analysis: CalorieAnalysis) -> None:
    get_logs().append(
        {
            "date": log_date.isoformat(),
            "meal_type": meal_type,
            "analysis": analysis.model_dump(),
        }
    )


def render_analysis(label: str, analysis: CalorieAnalysis) -> None:
    st.subheader(label)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Calories", f"{analysis.total_calories} kcal")
    metric_cols[1].metric("Weight", f"{analysis.estimated_weight_grams:.0f} g")
    metric_cols[2].metric("Confidence", f"{analysis.confidence_score:.0%}")

    macro_cols = st.columns(3)
    macro_cols[0].metric("Protein", f"{analysis.macros.protein_grams:.1f} g")
    macro_cols[1].metric("Carbs", f"{analysis.macros.carbs_grams:.1f} g")
    macro_cols[2].metric("Fat", f"{analysis.macros.fat_grams:.1f} g")

    badge = "Yes" if analysis.is_south_asian_food else "No"
    st.write(f"**Dish:** {analysis.dish_name}")
    st.write(f"**South Asian food:** {badge}")
    if analysis.notes:
        st.write(f"**Notes:** {analysis.notes}")


def render_daily_summary(selected_date: date) -> None:
    logs = [
        entry
        for entry in get_logs()
        if entry["date"] == selected_date.isoformat()
    ]

    st.subheader("Daily food log")
    if not logs:
        st.info("No meals logged for this date yet.")
        return

    total_calories = 0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for entry in logs:
        analysis = CalorieAnalysis.model_validate(entry["analysis"])
        total_calories += analysis.total_calories
        total_protein += analysis.macros.protein_grams
        total_carbs += analysis.macros.carbs_grams
        total_fat += analysis.macros.fat_grams

    summary_cols = st.columns(4)
    summary_cols[0].metric("Calories", f"{total_calories} kcal")
    summary_cols[1].metric("Protein", f"{total_protein:.1f} g")
    summary_cols[2].metric("Carbs", f"{total_carbs:.1f} g")
    summary_cols[3].metric("Fat", f"{total_fat:.1f} g")

    for meal_type in MEAL_TYPES:
        meal_logs = [entry for entry in logs if entry["meal_type"] == meal_type]
        if not meal_logs:
            continue

        with st.expander(meal_type.capitalize(), expanded=True):
            for index, entry in enumerate(meal_logs):
                analysis = CalorieAnalysis.model_validate(entry["analysis"])
                st.write(
                    f"**{analysis.dish_name}** - {analysis.total_calories} kcal, "
                    f"{analysis.estimated_weight_grams:.0f} g"
                )
                st.caption(
                    f"Protein {analysis.macros.protein_grams:.1f} g | "
                    f"Carbs {analysis.macros.carbs_grams:.1f} g | "
                    f"Fat {analysis.macros.fat_grams:.1f} g"
                )

                delete_key = f"delete-{meal_type}-{index}-{entry['date']}"
                if st.button("Delete", key=delete_key):
                    get_logs().remove(entry)
                    st.rerun()


def analyze_uploaded_image(uploaded_file, model: str, api_key: str) -> CalorieAnalysis:
    suffix = os.path.splitext(uploaded_file.name or "upload.jpg")[1] or ".jpg"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            temp_path = tmp.name
        return analyze_food_image(temp_path, model=model, api_key=api_key)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


st.set_page_config(
    page_title="South Asian Food Oil Analyser",
    page_icon="🍛",
    layout="centered",
)

st.title("🍛 South Asian Food Oil Analyser")
st.caption("Estimate calories and adjust oil/ghee or portion size from a food photo.")

api_key = get_api_key()
if not api_key:
    st.error(
        "Set GEMINI_API_KEY in Streamlit secrets or environment variables before "
        "running this app."
    )
    st.stop()

selected_date = st.date_input("Log date", value=date.today(), max_value=date.today())
meal_type = st.selectbox("Meal type", options=MEAL_TYPES, format_func=str.capitalize)
model = st.selectbox("Vision model", options=AVAILABLE_MODELS, index=0)
uploaded_file = st.file_uploader(
    "Upload a food photo", type=["jpg", "jpeg", "png", "webp"]
)

if st.button("Analyze image", type="primary", use_container_width=True):
    if uploaded_file is None:
        st.error("Please upload an image before running the analysis.")
    else:
        try:
            with st.spinner("Analyzing your food image..."):
                analysis = analyze_uploaded_image(uploaded_file, model, api_key)
        except ClientError as exc:
            st.error(f"Gemini API error: {exc}")
        except (OSError, ValueError) as exc:
            st.error(f"Could not process image: {exc}")
        else:
            save_analysis(analysis)

current_analysis = load_analysis(st.session_state.get("current_analysis"))
if current_analysis is not None:
    render_analysis("Current analysis", current_analysis)

    if (
        current_analysis.intervention_needed
        and current_analysis.suggested_oil_adjustment_grams != 0
    ):
        st.warning(
            "High oil/ghee detected. Suggested adjustment: "
            f"{format_oil_grams(current_analysis.suggested_oil_adjustment_grams)}"
        )
        if st.button("Apply suggested adjustment", use_container_width=True):
            updated = adjust_oil_calories(
                current_analysis,
                current_analysis.suggested_oil_adjustment_grams,
                "grams",
            )
            save_analysis(updated)
            st.rerun()

    st.markdown("### Adjust the estimate")
    oil_cols = st.columns([2, 1])
    oil_amount = oil_cols[0].number_input(
        "Oil / ghee adjustment",
        value=0.0,
        step=0.5,
        help="Use a negative value to remove oil.",
    )
    oil_unit = oil_cols[1].selectbox("Unit", options=["grams", "tsp", "tbsp"])
    if st.button("Apply oil adjustment", use_container_width=True):
        updated = adjust_oil_calories(current_analysis, oil_amount, oil_unit)
        save_analysis(updated)
        st.rerun()

    new_weight = st.number_input(
        "Actual portion weight (grams)",
        min_value=1.0,
        value=float(current_analysis.estimated_weight_grams),
        step=10.0,
    )
    if st.button("Apply weight adjustment", use_container_width=True):
        updated = adjust_dish_weight(current_analysis, new_weight)
        save_analysis(updated)
        st.rerun()

    if st.button("Log this meal", use_container_width=True):
        add_log_entry(selected_date, meal_type, current_analysis)
        st.success(f"Logged {current_analysis.dish_name} to {meal_type}.")

st.divider()
render_daily_summary(selected_date)
