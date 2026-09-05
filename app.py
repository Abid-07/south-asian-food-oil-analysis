"""FastAPI app for the South Asian Food Oil Analyser UI."""

import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from google.genai.errors import ClientError
from PIL import Image
from pydantic import BaseModel

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from analyzer import (
    DEFAULT_MODEL,
    CalorieAnalysis,
    adjust_dish_weight,
    adjust_oil_calories,
    analyze_food_image,
    normalize_model_name,
    resolve_gemini_api_key,
)


def resolve_db_path() -> Path:
    configured_path = os.environ.get("FOOD_LOG_DB_PATH")
    if configured_path:
        return Path(configured_path).expanduser()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "south-asian-food-oil-analysis" / "food_logs.db"

    return Path.home() / ".south-asian-food-oil-analysis" / "food_logs.db"


DB_PATH = resolve_db_path()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS food_logs (
                id         TEXT PRIMARY KEY,
                date       TEXT NOT NULL,
                meal_type  TEXT NOT NULL,
                analysis   TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="South Asian Food Oil Analyser", lifespan=lifespan)


async def analyze_uploaded_bytes(image_bytes: bytes, model_name: str, api_key: str) -> dict:
    tmp_path = Path(f"_tmp_{uuid.uuid4().hex}.jpg")
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img.save(tmp_path, format="JPEG")

        def run_analysis(selected_model: str) -> dict:
            return analyze_food_image(str(tmp_path), model=selected_model, api_key=api_key).model_dump()

        try:
            return await asyncio.to_thread(run_analysis, model_name)
        except ClientError as exc:
            if (
                model_name != DEFAULT_MODEL
                and "no longer available to new users" in str(exc).lower()
            ):
                return await asyncio.to_thread(run_analysis, DEFAULT_MODEL)
            raise HTTPException(
                status_code=502,
                detail=f"Vision API error for model '{model_name}': {exc}",
            ) from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.get("/")
async def index():
    return FileResponse("templates/index.html", media_type="text/html")


@app.post("/api/analyze")
async def analyze_endpoint(
    image: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
):
    try:
        api_key = resolve_gemini_api_key()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="No image content received.")

    return await analyze_uploaded_bytes(contents, normalize_model_name(model or DEFAULT_MODEL), api_key)


class OilAdjustRequest(BaseModel):
    analysis: dict
    oil_amount: float
    oil_unit: str


class WeightAdjustRequest(BaseModel):
    analysis: dict
    new_weight: float


@app.post("/api/adjust/oil")
async def adjust_oil_endpoint(req: OilAdjustRequest):
    analysis = CalorieAnalysis.model_validate(req.analysis)
    return adjust_oil_calories(analysis, req.oil_amount, req.oil_unit).model_dump()


@app.post("/api/adjust/weight")
async def adjust_weight_endpoint(req: WeightAdjustRequest):
    analysis = CalorieAnalysis.model_validate(req.analysis)
    return adjust_dish_weight(analysis, req.new_weight).model_dump()


class LogEntry(BaseModel):
    date: str
    meal_type: str
    analysis: dict


@app.post("/api/logs")
async def add_log(entry: LogEntry):
    log_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO food_logs (id, date, meal_type, analysis) VALUES (?, ?, ?, ?)",
            (log_id, entry.date, entry.meal_type, json.dumps(entry.analysis)),
        )
        conn.commit()
    return {"id": log_id}


@app.get("/api/logs/{log_date}")
async def get_logs(log_date: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM food_logs WHERE date = ? ORDER BY meal_type, created_at",
            (log_date,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "date": row["date"],
            "meal_type": row["meal_type"],
            "analysis": json.loads(row["analysis"]),
        }
        for row in rows
    ]


@app.delete("/api/logs/{log_id}")
async def delete_log(log_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM food_logs WHERE id = ?", (log_id,))
        conn.commit()
    return {"ok": True}
