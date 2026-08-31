# South Asian Food Oil Analyser

A food-photo calorie estimator for South Asian dishes powered by Google Gemini. The repo now includes:

- a **Streamlit app** for Streamlit Community Cloud deployment
- a **FastAPI app** for the existing web UI
- a **CLI tool** for local terminal use

---

## Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free)

---

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/your-username/south-asian-food-oil-analysis.git
   cd south-asian-food-oil-analysis
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv

   # Windows
   .\.venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your API key**

   Copy the example env file and fill in your key:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   The `.env` file is gitignored — it stays on your machine only. Alternatively, pass your key at runtime with `--api-key` (see below).

   If you use the web app food log, its SQLite database is now stored outside the repo by default, so it does not get pushed to GitHub. You can override the path with:
   ```
   FOOD_LOG_DB_PATH=C:\path\to\food_logs.db
   ```
   If you set a custom path, keep it outside the repo or make sure the file stays gitignored.

---

## Streamlit app

### Run locally

```bash
streamlit run streamlit_app.py
```

Set `GEMINI_API_KEY` in `.env` for local use, or add it to Streamlit secrets when deploying.

### Deploy on Streamlit Community Cloud

Use these settings in Streamlit:

- **Repository:** this GitHub repo
- **Main file path:** `streamlit_app.py`
- **Python version:** 3.10+ recommended

Then add this secret in the Streamlit dashboard:

```toml
GEMINI_API_KEY = "your_key_here"
```

If you point Streamlit at `app.py`, deployment will fail because that file is a FastAPI app, not a Streamlit entrypoint.

---

## CLI usage

```bash
python main.py --image path/to/food_photo.jpg
```

### Options

| Flag | Description | Default |
|---|---|---|
| `--image` / `-i` | Path to the food image | prompted if omitted |
| `--model` / `-m` | Gemini model to use | `gemini-3.6-flash` |
| `--api-key` | Gemini API key (overrides `.env`) | reads from `GEMINI_API_KEY` |

### Examples

```bash
# Fully interactive — prompts for the image path
python main.py

# Pass the image directly
python main.py --image ~/photos/curry.jpg

# Override the model
python main.py --image curry.jpg --model gemini-3.5-flash

# Pass the API key inline (without a .env file)
python main.py --image curry.jpg --api-key YOUR_KEY
```

---

## Interactive flow

Once the image is analysed, the tool walks you through three optional amendments:

1. **Suggested oil adjustment** — if the model flags the dish as likely high in oil/ghee, it suggests an adjustment and asks whether to apply it (`y`/`n`).

2. **Custom oil adjustment** — enter your own oil correction in any supported unit, or press Enter to skip.
   ```
   1.5 tsp      # add 1.5 teaspoons of oil
   -0.5 tbsp    # remove 0.5 tablespoons
   10 grams     # add 10 g directly
   ```

3. **Dish weight** — if the estimated portion size looks wrong, enter the correct weight in grams, or press Enter to skip.

A final summary is printed after all adjustments.

---

## Project structure

```
streamlit_app.py # Streamlit entry point for Streamlit Cloud
app.py           # FastAPI entry point for the existing web UI
main.py          # CLI entry point and interactive flow
analyzer.py      # Pydantic models, Gemini vision call, adjustment helpers
requirements.txt
.env             # Your API key (not committed)
```
