"""
FastAPI backend for BusIQ - Bus Dispatch Optimization System
Provides REST API endpoints for the dispatch engine
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from web.engine import (
    bootstrap_engine,
    build_demo_data,
    build_fleet,
    build_series_for_day,
    get_top_features,
    init_db,
    insert_override,
    insert_sms,
    load_logs,
    map_payload,
    optimize_dispatch,
    predict_row,
)

# Initialize API
app = FastAPI(
    title="BusIQ API",
    description="AI-powered bus dispatch optimization API",
    version="0.1.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
init_db()


# Request/Response Models
class OverrideLogEntry(BaseModel):
    corridor: str
    forecast: float
    recommendation: str
    operator_action: str
    outcome: str
    notes: str


class SMSLogEntry(BaseModel):
    phone: str
    message: str
    status: str
    payload: dict[str, Any]


# API Routes


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "BusIQ API",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/dashboard")
def get_dashboard():
    """Get complete dashboard data with predictions and optimization"""
    try:
        engine_data = bootstrap_engine()
        return {
            "status": "success",
            "data": engine_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/payload")
def get_payload():
    """Get map visualization payload"""
    try:
        payload = map_payload()
        return {
            "status": "success",
            "payload": payload,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fleet")
def get_fleet():
    """Get available bus fleet"""
    try:
        fleet = build_fleet()
        return {
            "status": "success",
            "fleet": [
                {
                    "bus_id": bus.bus_id,
                    "eta_min": bus.eta_min,
                    "capacity": bus.capacity,
                    "utilization_pct": bus.utilization_pct,
                    "shift_remaining_min": bus.shift_remaining_min,
                    "route_fit": bus.route_fit,
                }
                for bus in fleet
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/logs/override")
def log_override(entry: OverrideLogEntry):
    """Log an override decision"""
    try:
        insert_override(
            corridor=entry.corridor,
            forecast=entry.forecast,
            recommendation=entry.recommendation,
            operator_action=entry.operator_action,
            outcome=entry.outcome,
            notes=entry.notes,
        )
        return {"status": "success", "message": "Override logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/logs/sms")
def log_sms(entry: SMSLogEntry):
    """Log an SMS notification"""
    try:
        insert_sms(
            phone=entry.phone,
            message=entry.message,
            status=entry.status,
            payload=entry.payload,
        )
        return {"status": "success", "message": "SMS logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/override")
def get_override_logs(limit: int = 10):
    """Get override logs"""
    try:
        logs = load_logs("override_log", limit=limit)
        return {
            "status": "success",
            "logs": logs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/sms")
def get_sms_logs(limit: int = 10):
    """Get SMS logs"""
    try:
        logs = load_logs("sms_log", limit=limit)
        return {
            "status": "success",
            "logs": logs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
