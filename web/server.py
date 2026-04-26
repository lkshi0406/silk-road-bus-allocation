from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.engine import (
    bootstrap_engine,
    build_series_for_day,
    get_top_features,
    insert_override,
    insert_sms,
    load_logs,
    map_payload,
    optimize_dispatch,
    predict_row,
)

BASE_DIR = Path(__file__).resolve().parent

authors_note = "BusIQ dynamic web app backend"
app = FastAPI(title="BusIQ Web API", version="1.0.0", description=authors_note)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = bootstrap_engine()
df = state["df"]
models = state["models"]

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class OverrideRequest(BaseModel):
    day_index: int = Field(ge=1, le=30)
    hour: int = Field(ge=7, le=10)
    bus_id: str
    reason: str = Field(min_length=3, max_length=280)


class ApproveRequest(BaseModel):
    day_index: int = Field(ge=1, le=30)
    hour: int = Field(ge=7, le=10)


class SmsRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=24)
    message: str = Field(min_length=5, max_length=400)


def _select_row(day_index: int, hour: int):
    unique_dates = df["date"].drop_duplicates().reset_index(drop=True)
    date_value = unique_dates.iloc[day_index - 1]
    row = df[(df["date"] == date_value) & (df["hour"] == hour)]
    if row.empty:
        raise HTTPException(status_code=404, detail="Replay slice not found")
    return date_value, row.iloc[0]


def _py(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _py(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_py(v) for v in value]
    return value


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    html_path = BASE_DIR / "templates" / "dashboard.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/state")
def get_state(day_index: int = 12, hour: int = 8) -> dict[str, Any]:
    if day_index < 1 or day_index > 30:
        raise HTTPException(status_code=422, detail="day_index must be 1..30")
    if hour not in [7, 8, 9, 10]:
        raise HTTPException(status_code=422, detail="hour must be one of 7,8,9,10")

    date_value, row = _select_row(day_index, hour)
    prediction, lower, upper, _ = predict_row(models, row)
    trigger = prediction > (df["actual_demand"].mean() + 2 * models["full_residual_std"])

    candidates, chosen = optimize_dispatch(prediction, row)
    top_choice = candidates.iloc[0]

    return _py({
        "scope": {
            "corridor": "Silk Board-Koramangala",
            "route": "500C",
            "window": "7:00 AM - 10:00 AM",
            "day": date_value.strftime("%Y-%m-%d"),
            "hour": f"{hour:02d}:00",
        },
        "status": {
            "live": True,
            "data_synced": True,
            "model_accuracy": round(100 - (models["full_mae"] / 6.0), 1),
        },
        "forecast": {
            "prediction": round(prediction, 1),
            "lower": round(lower, 1),
            "upper": round(upper, 1),
            "trigger": trigger,
            "rain_mm": float(row["rain_mm"]),
            "metro_delay_min": float(row["metro_delay_min"]),
            "od_index": float(row["od_index"]),
        },
        "wait_times": {
            "baseline": float(row["baseline_wait_min"]),
            "predicted": float(row["busiq_wait_min"]),
            "improvement": round(float(row["baseline_wait_min"] - row["busiq_wait_min"]), 2),
        },
        "dispatch": {
            "recommended": {
                "bus_id": chosen.bus_id,
                "eta_min": chosen.eta_min,
                "capacity": chosen.capacity,
                "utilization_pct": chosen.utilization_pct,
                "shift_remaining_min": chosen.shift_remaining_min,
                "est_wait_after_dispatch": float(top_choice["estimated_wait_after_dispatch"]),
            },
            "candidates": candidates.to_dict(orient="records"),
        },
        "metrics": {
            "full_mae": models["full_mae"],
            "baseline_mae": models["baseline_mae"],
            "trigger_mae": models["trigger_mae"],
            "rolling_mae": models["rolling_mae"].to_dict(orient="records"),
        },
        "series": build_series_for_day(df, date_value),
        "map": map_payload(),
        "features": get_top_features(row),
        "override_log": load_logs("override_log", 10),
        "sms_log": load_logs("sms_log", 10),
    })


@app.post("/api/approve")
def approve_dispatch(payload: ApproveRequest) -> dict[str, Any]:
    _, row = _select_row(payload.day_index, payload.hour)
    prediction, _, _, _ = predict_row(models, row)
    candidates, chosen = optimize_dispatch(prediction, row)
    top_choice = candidates.iloc[0]

    insert_override(
        corridor="Silk Board-Koramangala / Route 500C",
        forecast=float(prediction),
        recommendation=f"Approve {chosen.bus_id}",
        operator_action=f"Approve {chosen.bus_id}",
        outcome="System was right",
        notes="Dispatch approved from API dashboard",
    )

    return {
        "ok": True,
        "message": f"Approved {chosen.bus_id}",
        "expected_wait_after_dispatch": float(top_choice["estimated_wait_after_dispatch"]),
        "override_log": load_logs("override_log", 10),
    }


@app.post("/api/override")
def override_dispatch(payload: OverrideRequest) -> dict[str, Any]:
    _, row = _select_row(payload.day_index, payload.hour)
    prediction, _, _, _ = predict_row(models, row)
    candidates, chosen = optimize_dispatch(prediction, row)
    recommended_row = candidates[candidates["bus_id"] == chosen.bus_id].iloc[0]

    selected = candidates[candidates["bus_id"] == payload.bus_id]
    if selected.empty:
        raise HTTPException(status_code=404, detail="Bus candidate not found")
    selected_row = selected.iloc[0]

    system_wait = float(recommended_row["estimated_wait_after_dispatch"])
    override_wait = float(selected_row["estimated_wait_after_dispatch"])
    outcome = "Operator override better" if override_wait < system_wait else "System was right"

    insert_override(
        corridor="Silk Board-Koramangala / Route 500C",
        forecast=float(prediction),
        recommendation=f"Approve {chosen.bus_id}",
        operator_action=f"Override to {payload.bus_id}",
        outcome=outcome,
        notes=payload.reason,
    )

    return {
        "ok": True,
        "message": f"Override stored: {payload.bus_id}",
        "outcome": outcome,
        "override_log": load_logs("override_log", 10),
    }


@app.post("/api/sms")
def sms_mock(payload: SmsRequest) -> dict[str, Any]:
    insert_sms(
        payload.phone,
        payload.message,
        "queued",
        {
            "channel": "twilio-whatsapp-mock",
            "to": payload.phone,
            "message": payload.message,
            "origin": "dynamic-web-app",
        },
    )
    return {"ok": True, "message": "SMS queued", "sms_log": load_logs("sms_log", 10)}
