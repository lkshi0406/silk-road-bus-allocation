from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shap
import streamlit as st
from folium.plugins import HeatMap
from ortools.linear_solver import pywraplp
from streamlit.components.v1 import html
from xgboost import XGBRegressor


APP_TITLE = "BusIQ | Silk Board-Koramangala MVP"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "busiq_mvp.sqlite3"


st.set_page_config(page_title=APP_TITLE, page_icon="🚌", layout="wide")


CSS = """
<style>
  .stApp {
    background:
      radial-gradient(circle at 15% 10%, rgba(69,242,255,0.12), transparent 18%),
      radial-gradient(circle at 90% 0%, rgba(143,123,255,0.14), transparent 16%),
      linear-gradient(180deg, #050816 0%, #071120 100%);
    color: #edf4ff;
  }
  .block-container {
    padding-top: 1.1rem;
    padding-bottom: 1.5rem;
  }
  .card {
    background: rgba(12, 18, 36, 0.72);
    border: 1px solid rgba(148, 197, 255, 0.14);
    border-radius: 20px;
    padding: 1rem 1rem 0.9rem 1rem;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.25);
  }
  .title-wrap h1 {
    margin-bottom: 0.1rem;
    letter-spacing: -0.04em;
  }
  .title-wrap p {
    color: #9fb0d1;
    margin-top: 0.15rem;
  }
  .metric-label {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #89a0ca;
    margin-bottom: 0.25rem;
  }
  .metric-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: #eff6ff;
    line-height: 1.1;
  }
  .metric-note {
    font-size: 0.85rem;
    color: #9fb0d1;
    margin-top: 0.25rem;
  }
  .feature-tag {
    display: inline-block;
    margin: 0.15rem 0.3rem 0.15rem 0;
    padding: 0.28rem 0.6rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 197, 255, 0.16);
    background: rgba(255,255,255,0.04);
    color: #d8e7ff;
    font-size: 0.78rem;
  }
  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.28rem 0.6rem;
    border-radius: 999px;
    background: rgba(69, 242, 255, 0.08);
    border: 1px solid rgba(69, 242, 255, 0.15);
    color: #bff7ff;
    font-size: 0.77rem;
    margin-right: 0.4rem;
  }
  .dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: #45f2ff;
    box-shadow: 0 0 12px rgba(69, 242, 255, 0.8);
    display: inline-block;
  }
  .alert-box {
    background: linear-gradient(145deg, rgba(35, 11, 15, 0.96), rgba(13, 18, 35, 0.96));
    border: 1px solid rgba(255, 77, 103, 0.24);
    box-shadow: 0 0 28px rgba(255, 77, 103, 0.18);
  }
  .small-label {
    color: #9fb0d1;
    font-size: 0.8rem;
  }
  .footer-note {
    color: #8fa2c7;
    font-size: 0.82rem;
  }
  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(6, 10, 22, 0.98), rgba(9, 15, 30, 0.98));
    border-right: 1px solid rgba(148, 197, 255, 0.12);
  }
  .stDataFrame {
    border-radius: 16px;
    overflow: hidden;
  }
</style>
"""


@dataclass(frozen=True)
class BusCandidate:
    bus_id: str
    eta_min: int
    capacity: int
    utilization_pct: int
    shift_remaining_min: int
    route_fit: float


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS override_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                corridor TEXT NOT NULL,
                forecast REAL NOT NULL,
                recommendation TEXT NOT NULL,
                operator_action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                phone TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        override_count = conn.execute("SELECT COUNT(*) FROM override_log").fetchone()[0]
        if override_count == 0:
            conn.executemany(
                "INSERT INTO override_log (ts, corridor, forecast, recommendation, operator_action, outcome, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "2025-03-18 08:12:00",
                        "Silk Board-Koramangala / Route 500C",
                        487.0,
                        "Approve KA-01-F-2234",
                        "Approve KA-01-F-2234",
                        "System was right",
                        "Forecast hit; bus cleared the queue before overflow crossed the control threshold.",
                    ),
                    (
                        "2025-03-21 08:22:00",
                        "Silk Board-Koramangala / Route 500C",
                        533.0,
                        "Approve KA-01-F-2288",
                        "Override to KA-01-F-2299",
                        "Operator override better",
                        "Extra shift headroom and shorter approach time outperformed the default recommendation.",
                    ),
                ],
            )
        sms_count = conn.execute("SELECT COUNT(*) FROM sms_log").fetchone()[0]
        if sms_count == 0:
            conn.execute(
                "INSERT INTO sms_log (ts, phone, message, status, payload) VALUES (?, ?, ?, ?, ?)",
                (
                    "2025-03-18 08:13:00",
                    "+91 90000 00000",
                    "Bus KA-01-F-2234 dispatched to Silk Board in response to surge alert 487 passengers / 20 min.",
                    "demo-seeded",
                    json.dumps({"channel": "twilio-whatsapp", "demo": True}, ensure_ascii=True),
                ),
            )
        conn.commit()


@st.cache_data(show_spinner=False)
def build_demo_data() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2025-03-03", periods=30)
    records: list[dict[str, float | int | str]] = []
    for day_index, date in enumerate(dates):
        weekday_idx = int(date.weekday())
        rain_mm = float(max(0.0, rng.normal(1.6 + 0.03 * day_index, 2.1)))
        metro_delay_min = float(max(0.0, rng.normal(4.5 + 0.08 * day_index + rain_mm * 0.5, 2.0)))
        od_index = float(4200 + day_index * 34 + rng.normal(0, 65))
        weather_pressure = float(min(1.0, 0.25 + rain_mm / 20 + metro_delay_min / 35))
        traffic_index = float(0.7 + day_index * 0.015 + rain_mm * 0.03 + metro_delay_min * 0.018)

        for hour in [7, 8, 9, 10]:
            hour_wave = {7: 0.0, 8: 42.0, 9: 92.0, 10: 40.0}[hour]
            peak_flag = 1 if hour in (8, 9) else 0
            structural_signal = 112 + weekday_idx * 9 + (od_index - 4200) * 0.024 + traffic_index * 16
            trigger_signal = rain_mm * 22 + metro_delay_min * 11 + weather_pressure * 18 + peak_flag * 12
            actual_demand = structural_signal + hour_wave + trigger_signal + rng.normal(0, 15)
            actual_demand = float(max(220.0, actual_demand))

            base_wait = 7.0 + actual_demand * 0.024 + rain_mm * 0.45 + metro_delay_min * 0.18 + traffic_index * 1.7
            busiq_wait = max(5.0, base_wait - (8.4 + 0.012 * actual_demand - 0.2 * peak_flag))
            scheduled_headway = float(max(6.0, 11.5 - peak_flag * 1.3 + weekday_idx * 0.15))

            records.append(
                {
                    "date": date,
                    "day_index": day_index,
                    "weekday": date.day_name(),
                    "weekday_idx": weekday_idx,
                    "hour": hour,
                    "hour_label": f"{hour:02d}:00",
                    "route": "500C",
                    "corridor": "Silk Board-Koramangala",
                    "rain_mm": round(rain_mm, 2),
                    "metro_delay_min": round(metro_delay_min, 2),
                    "od_index": round(od_index, 1),
                    "weather_pressure": round(weather_pressure, 3),
                    "traffic_index": round(traffic_index, 3),
                    "scheduled_headway_min": round(scheduled_headway, 2),
                    "peak_flag": peak_flag,
                    "actual_demand": round(actual_demand, 1),
                    "baseline_wait_min": round(base_wait, 2),
                    "busiq_wait_min": round(busiq_wait, 2),
                }
            )

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def feature_groups() -> dict[str, list[str]]:
    return {
        "baseline": [
            "weekday_idx",
            "hour",
            "od_index",
            "traffic_index",
            "scheduled_headway_min",
        ],
        "trigger": [
            "rain_mm",
            "metro_delay_min",
            "weather_pressure",
            "peak_flag",
        ],
    }


def build_feature_matrix(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    matrix = df.loc[:, list(columns)].copy()
    for required in ["weekday_idx", "hour"]:
        if required not in matrix.columns:
            matrix[required] = df[required].values
    matrix["weekday_sin"] = np.sin(2 * np.pi * matrix["weekday_idx"] / 7.0)
    matrix["weekday_cos"] = np.cos(2 * np.pi * matrix["weekday_idx"] / 7.0)
    matrix["hour_sin"] = np.sin(2 * np.pi * (matrix["hour"] - 7) / 4.0)
    matrix["hour_cos"] = np.cos(2 * np.pi * (matrix["hour"] - 7) / 4.0)
    return matrix.drop(columns=[col for col in ["weekday_idx", "hour"] if col in matrix.columns])


@st.cache_resource(show_spinner=False)
def train_models(df: pd.DataFrame):
    groups = feature_groups()
    base_cols = groups["baseline"]
    trigger_cols = groups["trigger"]
    full_cols = list(dict.fromkeys(base_cols + trigger_cols))

    ordered = df.sort_values(["date", "hour"]).reset_index(drop=True)
    split_idx = ordered["date"].drop_duplicates().iloc[:-7]
    train_df = ordered[ordered["date"].isin(split_idx)]
    test_df = ordered[~ordered["date"].isin(split_idx)]

    def fit_for(cols: list[str]) -> tuple[XGBRegressor, pd.DataFrame, pd.Series, pd.Series]:
        x_train = build_feature_matrix(train_df, cols)
        x_test = build_feature_matrix(test_df, cols)
        model = XGBRegressor(
            n_estimators=250,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.92,
            reg_lambda=1.0,
            random_state=42,
            objective="reg:squarederror",
        )
        model.fit(x_train, train_df["actual_demand"])
        preds = pd.Series(model.predict(x_test), index=x_test.index)
        residuals = train_df["actual_demand"] - pd.Series(model.predict(x_train), index=x_train.index)
        return model, x_test, preds, residuals

    full_model, x_test_full, full_preds, full_residuals = fit_for(full_cols)
    baseline_model, _, baseline_preds, _ = fit_for(base_cols)
    trigger_model, _, trigger_preds, _ = fit_for(trigger_cols)

    test_actual = test_df["actual_demand"].reset_index(drop=True)
    full_mae = float(np.mean(np.abs(test_actual - full_preds.reset_index(drop=True))))
    baseline_mae = float(np.mean(np.abs(test_actual - baseline_preds.reset_index(drop=True))))
    trigger_mae = float(np.mean(np.abs(test_actual - trigger_preds.reset_index(drop=True))))

    rolling_mae = compute_rolling_mae(ordered, full_cols)

    return {
        "full_model": full_model,
        "baseline_model": baseline_model,
        "trigger_model": trigger_model,
        "full_cols": full_cols,
        "baseline_cols": base_cols,
        "trigger_cols": trigger_cols,
        "x_test_full": x_test_full,
        "test_df": test_df.reset_index(drop=True),
        "full_mae": full_mae,
        "baseline_mae": baseline_mae,
        "trigger_mae": trigger_mae,
        "full_residual_std": float(np.std(full_residuals, ddof=1)),
        "full_residuals": full_residuals,
        "rolling_mae": rolling_mae,
    }


def compute_rolling_mae(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    dates = list(df["date"].drop_duplicates())
    results = []
    for idx in range(7, len(dates)):
        train_dates = dates[max(0, idx - 7) : idx]
        test_date = dates[idx]
        train_df = df[df["date"].isin(train_dates)]
        test_df = df[df["date"] == test_date]
        model = XGBRegressor(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=idx,
            objective="reg:squarederror",
        )
        model.fit(build_feature_matrix(train_df, cols), train_df["actual_demand"])
        preds = model.predict(build_feature_matrix(test_df, cols))
        mae = float(np.mean(np.abs(test_df["actual_demand"].to_numpy() - preds)))
        results.append({"date": test_date, "mae": mae})
    return pd.DataFrame(results)


@st.cache_resource(show_spinner=False)
def build_explainer(_model):
    return shap.TreeExplainer(_model)


def predict_row(model: XGBRegressor, row: pd.Series, cols: list[str], residual_std: float):
    x_row = build_feature_matrix(pd.DataFrame([row]), cols)
    prediction = float(model.predict(x_row)[0])
    lower = max(0.0, prediction - 1.28 * residual_std)
    upper = prediction + 1.28 * residual_std
    return prediction, lower, upper, x_row


def compute_wait_time(prediction: float, row: pd.Series) -> tuple[float, float]:
    baseline_wait = float(row["baseline_wait_min"])
    improvement = 8.0 + 0.012 * prediction - 0.14 * float(row["metro_delay_min"]) + 0.2 * int(row["peak_flag"])
    busiq_wait = max(5.0, baseline_wait - improvement)
    return baseline_wait, busiq_wait


def build_fleet() -> list[BusCandidate]:
    return [
        BusCandidate("KA-01-F-2234", eta_min=12, capacity=88, utilization_pct=78, shift_remaining_min=160, route_fit=0.97),
        BusCandidate("KA-01-F-2288", eta_min=9, capacity=66, utilization_pct=91, shift_remaining_min=145, route_fit=0.84),
        BusCandidate("KA-01-F-2201", eta_min=15, capacity=72, utilization_pct=65, shift_remaining_min=220, route_fit=0.79),
        BusCandidate("KA-01-F-2299", eta_min=18, capacity=96, utilization_pct=74, shift_remaining_min=100, route_fit=0.72),
    ]


def optimize_dispatch(prediction: float, row: pd.Series) -> tuple[pd.DataFrame, BusCandidate]:
    fleet = build_fleet()
    solver = pywraplp.Solver.CreateSolver("CBC")
    variables = {bus.bus_id: solver.BoolVar(bus.bus_id) for bus in fleet}

    solver.Add(sum(variables.values()) == 1)
    for bus in fleet:
        if bus.utilization_pct > 95 or bus.shift_remaining_min < 90 or bus.route_fit < 0.7:
            solver.Add(variables[bus.bus_id] == 0)

    demand_pressure = prediction / 100.0
    objective_terms = []
    for bus in fleet:
        service_score = (
            bus.capacity * 0.09
            - bus.eta_min * 0.35
            + bus.route_fit * 8.5
            - bus.utilization_pct * 0.02
            + bus.shift_remaining_min * 0.006
            - demand_pressure * 0.2
        )
        objective_terms.append(service_score * variables[bus.bus_id])
    solver.Maximize(solver.Sum(objective_terms))
    solver.Solve()

    rows = []
    chosen = fleet[0]
    best_score = -1e9
    for bus in fleet:
        service_score = (
            bus.capacity * 0.09
            - bus.eta_min * 0.35
            + bus.route_fit * 8.5
            - bus.utilization_pct * 0.02
            + bus.shift_remaining_min * 0.006
            - demand_pressure * 0.2
        )
        busq_wait = max(5.0, float(row["baseline_wait_min"]) - (6.6 + service_score))
        rows.append(
            {
                "bus_id": bus.bus_id,
                "eta_min": bus.eta_min,
                "capacity": bus.capacity,
                "utilization_pct": bus.utilization_pct,
                "shift_remaining_min": bus.shift_remaining_min,
                "route_fit": round(bus.route_fit, 2),
                "score": round(service_score, 2),
                "estimated_wait_after_dispatch": round(busq_wait, 2),
                "feasible": "yes"
                if bus.utilization_pct <= 95 and bus.shift_remaining_min >= 90 and bus.route_fit >= 0.7
                else "no",
            }
        )
        if service_score > best_score and rows[-1]["feasible"] == "yes":
            best_score = service_score
            chosen = bus

    candidates = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return candidates, chosen


def make_map(row: pd.Series, prediction: float) -> str:
    center = [12.9156, 77.6235]
    map_obj = folium.Map(location=center, zoom_start=13, tiles=None, control_scale=False, zoom_control=False)
    heat = [
        [12.9168, 77.6237, 0.92],
        [12.9220, 77.6219, 0.70],
        [12.9075, 77.6320, 0.54],
        [12.9345, 77.6202, 0.42],
    ]
    HeatMap(heat, radius=34, blur=24, min_opacity=0.35).add_to(map_obj)

    corridor_points = [
        (12.9014, 77.6124),
        (12.9104, 77.6195),
        (12.9165, 77.6238),
        (12.9233, 77.6265),
        (12.9328, 77.6294),
    ]
    folium.PolyLine(corridor_points, weight=6, opacity=0.85, color="#45f2ff").add_to(map_obj)
    folium.PolyLine(corridor_points, weight=13, opacity=0.16, color="#ff5f7a").add_to(map_obj)

    peak_strength = min(1.0, prediction / 700.0)
    folium.Circle(
        location=(12.9165, 77.6238),
        radius=300 + peak_strength * 700,
        color="#ff4d67",
        fill=True,
        fill_opacity=0.28,
        opacity=0.7,
    ).add_to(map_obj)

    bus_positions = [
        (12.9102, 77.6186, "#45f2ff", "KA-01-F-2234"),
        (12.9169, 77.6240, "#61ff8f", "KA-01-F-2288"),
        (12.9249, 77.6278, "#ffba5c", "KA-01-F-2201"),
    ]
    for lat, lon, color, label in bus_positions:
        folium.Marker(
            location=(lat, lon),
            icon=folium.DivIcon(
                html=f"""
                <div style=\"color:{color};font-size:20px;filter:drop-shadow(0 0 8px {color});\">🚌</div>
                """
            ),
            tooltip=label,
        ).add_to(map_obj)

    folium.Marker(
        location=(12.9165, 77.6238),
        tooltip="Silk Board Junction",
        icon=folium.Icon(color="red", icon="warning-sign"),
    ).add_to(map_obj)
    folium.Marker(
        location=(12.9291, 77.6268),
        tooltip="Koramangala",
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(map_obj)

    return map_obj.get_root().render()


def style_metric(label: str, value: str, note: str) -> str:
    return f"""
    <div class=\"card\" style=\"height:100%;\">
      <div class=\"metric-label\">{label}</div>
      <div class=\"metric-value\">{value}</div>
      <div class=\"metric-note\">{note}</div>
    </div>
    """


def load_logs(table: str, limit: int = 12) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}",
            conn,
        )


def insert_override(corridor: str, forecast: float, recommendation: str, operator_action: str, outcome: str, notes: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO override_log (ts, corridor, forecast, recommendation, operator_action, outcome, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), corridor, forecast, recommendation, operator_action, outcome, notes),
        )
        conn.commit()


def insert_sms(phone: str, message: str, status: str, payload: dict) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO sms_log (ts, phone, message, status, payload) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone, message, status, json.dumps(payload, ensure_ascii=True)),
        )
        conn.commit()


def build_overview_figures(df: pd.DataFrame, selected_date: pd.Timestamp) -> tuple[go.Figure, go.Figure]:
    day_df = df[df["date"] == selected_date].sort_values("hour")
    wait_fig = go.Figure()
    wait_fig.add_trace(
        go.Scatter(
            x=day_df["hour_label"],
            y=day_df["baseline_wait_min"],
            mode="lines+markers",
            name="Baseline wait",
            line=dict(color="#66b8ff", width=3),
        )
    )
    wait_fig.add_trace(
        go.Scatter(
            x=day_df["hour_label"],
            y=day_df["busiq_wait_min"],
            mode="lines+markers",
            name="BusIQ predicted wait",
            line=dict(color="#61ff8f", width=3),
        )
    )
    wait_fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,13,25,0.9)",
        font=dict(color="#edf4ff"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        yaxis=dict(title="Wait time (min)", gridcolor="rgba(148,197,255,0.12)"),
        xaxis=dict(title="7-10 AM window"),
    )

    timeline_fig = go.Figure()
    timeline_steps = ["Ingestion", "Prediction", "Dispatch", "Outcome"]
    timeline_values = [1, 2, 3, 4]
    timeline_fig.add_trace(go.Scatter(x=timeline_steps, y=timeline_values, mode="lines+markers", line=dict(color="#45f2ff", width=4), marker=dict(size=14)))
    timeline_fig.update_layout(
        height=200,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,13,25,0.9)",
        font=dict(color="#edf4ff"),
        yaxis=dict(visible=False),
        xaxis=dict(title="Replay sequence"),
    )
    return wait_fig, timeline_fig


def build_shap_chart(explainer, model, row_df: pd.DataFrame, cols: list[str]) -> go.Figure:
    shap_values = explainer.shap_values(row_df)
    if isinstance(shap_values, list):
        shap_values = shap_values[0]
    contrib = pd.Series(shap_values[0], index=row_df.columns).sort_values(key=lambda s: np.abs(s), ascending=False).head(6)
    colors = ["#ff5f7a" if v > 0 else "#45f2ff" for v in contrib.values]
    fig = go.Figure(
        go.Bar(
            x=contrib.values[::-1],
            y=contrib.index[::-1],
            orientation="h",
            marker_color=colors[::-1],
            text=[f"{v:+.1f}" for v in contrib.values[::-1]],
            textposition="auto",
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,13,25,0.9)",
        font=dict(color="#edf4ff"),
        xaxis=dict(title="SHAP contribution"),
        yaxis=dict(title="Features"),
    )
    return fig


def learning_curve_fig(rolling_mae: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rolling_mae["date"],
            y=rolling_mae["mae"],
            mode="lines+markers",
            line=dict(color="#ffba5c", width=3),
            marker=dict(size=7),
            name="24h sliding retrain MAE",
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,13,25,0.9)",
        font=dict(color="#edf4ff"),
        yaxis=dict(title="MAE", gridcolor="rgba(148,197,255,0.12)"),
        xaxis=dict(title="Learning curve"),
    )
    return fig


def bootstrap_demo_assets(df: pd.DataFrame, models: dict):
    selected_day_count = st.sidebar.slider("Replay day index", 1, 30, 12)
    selected_hour = st.sidebar.select_slider("Replay hour", options=[7, 8, 9, 10], value=8)
    selected_date = df["date"].drop_duplicates().iloc[selected_day_count - 1]
    current_row = df[(df["date"] == selected_date) & (df["hour"] == selected_hour)].iloc[0]
    return selected_date, current_row


def main() -> None:
    init_db()
    st.markdown(CSS, unsafe_allow_html=True)

    df = build_demo_data()
    models = train_models(df)
    explainer = build_explainer(models["full_model"])

    with st.sidebar:
        st.markdown("### BusIQ MVP controls")
        st.caption("One corridor. One time window. Every layer wired.")
        selected_day_count = st.slider("Replay day index", 1, 30, 12)
        selected_hour = st.select_slider("Replay hour", options=[7, 8, 9, 10], value=8)
        st.divider()
        st.caption("Scope")
        st.write("Silk Board-Koramangala")
        st.write("Route 500C")
        st.write("Weekdays, 7-10 AM")
        st.write("30-day replay window")
        st.divider()
        st.caption("Data layers")
        st.write("BMTC GTFS historical (demo corpus)")
        st.write("Uber Movement baseline signal")
        st.write("Census OD and weather triggers")

    selected_date = df["date"].drop_duplicates().iloc[selected_day_count - 1]
    current_row = df[(df["date"] == selected_date) & (df["hour"] == selected_hour)].iloc[0]

    prediction, lower, upper, row_x = predict_row(models["full_model"], current_row, models["full_cols"], models["full_residual_std"])
    baseline_wait, busiq_wait = compute_wait_time(prediction, current_row)
    forecast_trigger = prediction > (df["actual_demand"].mean() + 2 * models["full_residual_std"])
    candidates, chosen_bus = optimize_dispatch(prediction, current_row)
    map_html = make_map(current_row, prediction)
    wait_fig, timeline_fig = build_overview_figures(df, selected_date)
    shap_fig = build_shap_chart(explainer, models["full_model"], row_x, models["full_cols"])
    learning_fig = learning_curve_fig(models["rolling_mae"])

    with st.container():
        st.markdown(
            f"""
            <div class=\"title-wrap\">
              <h1>BusIQ</h1>
              <p>AI-powered control room MVP for Silk Board-Koramangala on Route 500C, 7-10 AM weekdays.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(style_metric("Live status", "Online", "Map, model, and logs are active"), unsafe_allow_html=True)
    col2.markdown(style_metric("Forecast", f"{prediction:.0f}", "Passengers in the next 20 minutes"), unsafe_allow_html=True)
    col3.markdown(style_metric("Validation MAE", f"{models['full_mae']:.1f}", "Held-out week on 30-day replay"), unsafe_allow_html=True)
    col4.markdown(style_metric("Dispatch gain", f"{baseline_wait - busiq_wait:.1f} min", "Baseline wait improvement"), unsafe_allow_html=True)

    st.markdown("---")
    left, center, right = st.columns([1.15, 1.0, 0.95], gap="large")

    with left:
        st.markdown("<div class='card'><div class='metric-label'>Corridor map</div><div class='small-label'>Silk Board junction congestion field</div></div>", unsafe_allow_html=True)
        html(map_html, height=540)

    with center:
        st.markdown("<div class='card'><div class='metric-label'>Surge alert</div></div>", unsafe_allow_html=True)
        alert_class = "alert-box" if forecast_trigger else "card"
        st.markdown(
            f"""
            <div class=\"card {alert_class}\" style=\"margin-top:0.6rem;\">
              <div class=\"status-pill\"><span class=\"dot\"></span>Urgency: {'High' if forecast_trigger else 'Medium'}</div>
              <h2 style=\"margin:0.55rem 0 0.2rem 0;font-size:2.4rem;\">{prediction:.0f} passengers</h2>
              <div class=\"small-label\">Expected surge in the next 20 minutes</div>
              <p style=\"margin-top:0.8rem;color:#d7e4ff;line-height:1.5;\">The 2-sigma trigger is firing because weather, metro delay, and corridor pressure align on the replayed time slice.</p>
              <div style=\"margin-top:0.8rem;\">
                <span class=\"feature-tag\">Rain +{current_row['rain_mm']:.1f} mm</span>
                <span class=\"feature-tag\">Metro delay +{current_row['metro_delay_min']:.1f} min</span>
                <span class=\"feature-tag\">OD index {current_row['od_index']:.0f}</span>
              </div>
              <div style=\"margin-top:0.8rem;\">
                <div class=\"small-label\">Prediction band</div>
                <div style=\"height:14px;border-radius:999px;background:linear-gradient(90deg, rgba(255,77,103,0.12), rgba(255,186,92,0.48), rgba(97,255,143,0.18));border:1px solid rgba(255,255,255,0.08);position:relative;overflow:hidden;\">
                  <div style=\"position:absolute;left:18%;right:22%;top:2px;height:8px;border-radius:999px;background:rgba(255,255,255,0.6);box-shadow:0 0 16px rgba(255,255,255,0.35);\"></div>
                </div>
                <div style=\"display:flex;justify-content:space-between;margin-top:0.25rem;color:#9fb0d1;font-size:0.82rem;\">
                  <span>{lower:.0f}</span><strong style=\"color:#eff6ff;\">{prediction:.0f} ± {prediction - lower:.0f}</strong><span>{upper:.0f}</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.plotly_chart(shap_fig, use_container_width=True)
        st.caption("Top driver contributions for the selected replay slice.")

    with right:
        st.markdown("<div class='card'><div class='metric-label'>Dispatch recommendation</div></div>", unsafe_allow_html=True)
        top_choice = candidates.iloc[0]
        st.markdown(
            f"""
            <div class=\"card\" style=\"margin-top:0.6rem;\">
              <div class=\"metric-label\">Recommended bus</div>
              <div class=\"metric-value\" style=\"font-size:1.5rem;\">{chosen_bus.bus_id}</div>
              <div class=\"small-label\">ETA to stop: {chosen_bus.eta_min} min</div>
              <div style=\"margin-top:0.7rem;\">
                <div class=\"small-label\">Capacity utilization</div>
                <div style=\"height:12px;background:rgba(255,255,255,0.08);border-radius:999px;overflow:hidden;border:1px solid rgba(148,197,255,0.12);\">
                  <div style=\"width:{chosen_bus.utilization_pct}%;height:100%;background:linear-gradient(90deg,#45f2ff,#61ff8f,#ffba5c);\"></div>
                </div>
                <div style=\"display:flex;justify-content:space-between;color:#9fb0d1;font-size:0.8rem;margin-top:0.25rem;\"><span>0%</span><strong>{chosen_bus.utilization_pct}%</strong><span>100%</span></div>
              </div>
              <div style=\"margin-top:0.65rem;\"><span class=\"small-label\">Driver shift remaining</span><div style=\"font-weight:700;\">{chosen_bus.shift_remaining_min // 60}h {chosen_bus.shift_remaining_min % 60:02d}m</div></div>
              <div style=\"margin-top:0.65rem;\"><span class=\"small-label\">Expected wait after dispatch</span><div style=\"font-weight:700;color:#61ff8f;\">{top_choice['estimated_wait_after_dispatch']:.1f} min</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        approved = st.button("Approve Dispatch", type="primary", use_container_width=True)
        override_bus = st.selectbox("Override bus", candidates["bus_id"].tolist(), index=1)
        override_reason = st.text_input("Override reason", value="Operator used live judgement on crowd pattern and traffic feed.")
        overridden = st.button("Override and log outcome", use_container_width=True)

        if approved:
            insert_override(
                corridor="Silk Board-Koramangala / Route 500C",
                forecast=float(prediction),
                recommendation=f"Approve {chosen_bus.bus_id}",
                operator_action=f"Approve {chosen_bus.bus_id}",
                outcome="System was right",
                notes="Dispatch approved from the predicted surge alert.",
            )
            st.success("Dispatch approved and written to the override tracker.")

        if overridden:
            override_row = candidates[candidates["bus_id"] == override_bus].iloc[0]
            system_wait = float(top_choice["estimated_wait_after_dispatch"])
            override_wait = float(override_row["estimated_wait_after_dispatch"])
            outcome = "Operator override better" if override_wait < system_wait else "System was right"
            insert_override(
                corridor="Silk Board-Koramangala / Route 500C",
                forecast=float(prediction),
                recommendation=f"Approve {chosen_bus.bus_id}",
                operator_action=f"Override to {override_bus}",
                outcome=outcome,
                notes=override_reason,
            )
            st.success(f"Override saved. Outcome: {outcome}.")

        sms_phone = st.text_input("Twilio demo phone", value="+91 90000 00000")
        sms_message = st.text_area(
            "Twilio/WhatsApp mock message",
            value=f"BusIQ alert: {chosen_bus.bus_id} dispatched to Silk Board. Forecast {prediction:.0f} passengers in 20 min. Reply 1 to acknowledge.",
            height=96,
        )
        sms_sent = st.button("Send SMS mockup", use_container_width=True)
        if sms_sent:
            payload = {
                "channel": "twilio-whatsapp-mock",
                "to": sms_phone,
                "message": sms_message,
                "corridor": "Silk Board-Koramangala",
                "route": "500C",
            }
            insert_sms(sms_phone, sms_message, "queued", payload)
            st.success("Demo SMS queued and written to the message log.")

        st.markdown("<div class='card' style='margin-top:0.8rem;'><div class='metric-label'>Validation metrics</div></div>", unsafe_allow_html=True)
        metric_cols = st.columns(3)
        metric_cols[0].metric("Full model MAE", f"{models['full_mae']:.1f}")
        metric_cols[1].metric("Baseline-only MAE", f"{models['baseline_mae']:.1f}")
        metric_cols[2].metric("Trigger-only MAE", f"{models['trigger_mae']:.1f}")

    st.markdown("---")
    st.subheader("Replay simulation and learning curve")
    sim_left, sim_right = st.columns([1.2, 0.8], gap="large")
    with sim_left:
        st.plotly_chart(wait_fig, use_container_width=True)
        st.caption("Baseline wait time vs BusIQ predicted wait time across the selected 7-10 AM window.")
    with sim_right:
        st.plotly_chart(learning_fig, use_container_width=True)
        st.caption("24-hour sliding retrain curve, computed from the 30-day replay.")
        st.markdown(
            f"""
            <div class=\"card\" style=\"margin-top:0.4rem;\">
              <div class=\"metric-label\">Headline results</div>
              <p style=\"margin:0.2rem 0;color:#d8e7ff;\">Wait-time reduction: <strong>{baseline_wait - busiq_wait:.1f} min</strong></p>
              <p style=\"margin:0.2rem 0;color:#d8e7ff;\">Trigger condition: <strong>{'fired' if forecast_trigger else 'not fired'}</strong></p>
              <p style=\"margin:0.2rem 0;color:#d8e7ff;\">Confidence band: <strong>{lower:.0f} to {upper:.0f}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    log_left, log_right = st.columns(2, gap="large")
    with log_left:
        st.subheader("Override outcome tracker")
        override_logs = load_logs("override_log", 10)
        st.dataframe(override_logs, use_container_width=True, hide_index=True)
    with log_right:
        st.subheader("SMS mockup log")
        sms_logs = load_logs("sms_log", 10)
        st.dataframe(sms_logs, use_container_width=True, hide_index=True)

    with st.expander("Feature governance and two-layer signal architecture", expanded=False):
        st.write("Structural baseline features")
        for tag in ["weekday_idx", "hour", "od_index", "traffic_index", "scheduled_headway_min"]:
            st.markdown(f"<span class='feature-tag'>{tag}</span>", unsafe_allow_html=True)
        st.write("Trigger features")
        for tag in ["rain_mm", "metro_delay_min", "weather_pressure", "peak_flag"]:
            st.markdown(f"<span class='feature-tag'>{tag}</span>", unsafe_allow_html=True)
        st.write(
            "The MVP keeps the baseline and trigger layers separate so the judge can inspect which signal family pushed the dispatch decision."
        )

    with st.expander("Dispatch candidates", expanded=False):
        st.dataframe(candidates, use_container_width=True, hide_index=True)

    st.caption("Built for a hackathon demo with working controls, replayable metrics, and local persistence.")


if __name__ == "__main__":
    main()