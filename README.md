# South Asian Food Oil Analyser

Estimate calories and oil usage from a food photo using Gemini.

## Setup

1. Create and activate a virtual environment

   ```bash
   python -m venv .venv

   # Windows
   .\.venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

2. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

3. Add your Gemini API key

   Create a `.env` file in the project root:

   ```bash
   GEMINI_API_KEY=your_key_here
   ```

## Run

### CLI test run

```bash
python main.py --image path/to/food_photo.jpg
```

Optional:

```bash
python main.py --image path/to/food_photo.jpg --model gemini-3.6-flash
python main.py --image path/to/food_photo.jpg --api-key YOUR_KEY
```

### Web app

```bash
uvicorn app:app --reload
```

Open:

```text
http://localhost:8000
```

## Project split

- `main.py` — quick CLI testing
- `app.py` — browser UI
- `analyzer.py` — Gemini + calorie logic

## Requirements

- Python 3.10+
- Gemini API key from Google AI Studio
