from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from ortools.linear_solver import pywraplp
from xgboost import XGBRegressor

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "busiq_mvp.sqlite3"


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
        if conn.execute("SELECT COUNT(*) FROM override_log").fetchone()[0] == 0:
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
                        "Forecast hit; bus cleared queue before overflow threshold.",
                    ),
                    (
                        "2025-03-21 08:22:00",
                        "Silk Board-Koramangala / Route 500C",
                        533.0,
                        "Approve KA-01-F-2288",
                        "Override to KA-01-F-2299",
                        "Operator override better",
                        "Extra shift headroom and shorter approach time outperformed default.",
                    ),
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM sms_log").fetchone()[0] == 0:
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


def build_demo_data() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2025-03-03", periods=30)
    rows: list[dict[str, Any]] = []
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
            actual_demand = max(220.0, structural_signal + hour_wave + trigger_signal + rng.normal(0, 15))

            base_wait = 7.0 + actual_demand * 0.024 + rain_mm * 0.45 + metro_delay_min * 0.18 + traffic_index * 1.7
            busiq_wait = max(5.0, base_wait - (8.4 + 0.012 * actual_demand - 0.2 * peak_flag))
            scheduled_headway = max(6.0, 11.5 - peak_flag * 1.3 + weekday_idx * 0.15)

            rows.append(
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
                    "actual_demand": round(float(actual_demand), 1),
                    "baseline_wait_min": round(float(base_wait), 2),
                    "busiq_wait_min": round(float(busiq_wait), 2),
                }
            )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def feature_groups() -> dict[str, list[str]]:
    return {
        "baseline": ["weekday_idx", "hour", "od_index", "traffic_index", "scheduled_headway_min"],
        "trigger": ["rain_mm", "metro_delay_min", "weather_pressure", "peak_flag"],
    }


def build_feature_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    matrix = df.loc[:, columns].copy()
    for required in ["weekday_idx", "hour"]:
        if required not in matrix.columns:
            matrix[required] = df[required].values
    matrix["weekday_sin"] = np.sin(2 * np.pi * matrix["weekday_idx"] / 7.0)
    matrix["weekday_cos"] = np.cos(2 * np.pi * matrix["weekday_idx"] / 7.0)
    matrix["hour_sin"] = np.sin(2 * np.pi * (matrix["hour"] - 7) / 4.0)
    matrix["hour_cos"] = np.cos(2 * np.pi * (matrix["hour"] - 7) / 4.0)
    return matrix.drop(columns=[c for c in ["weekday_idx", "hour"] if c in matrix.columns])


def compute_rolling_mae(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    dates = list(df["date"].drop_duplicates())
    out = []
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
        out.append({"date": test_date.strftime("%Y-%m-%d"), "mae": round(mae, 3)})
    return pd.DataFrame(out)


def train_models(df: pd.DataFrame) -> dict[str, Any]:
    groups = feature_groups()
    base_cols = groups["baseline"]
    trigger_cols = groups["trigger"]
    full_cols = list(dict.fromkeys(base_cols + trigger_cols))

    ordered = df.sort_values(["date", "hour"]).reset_index(drop=True)
    split_idx = ordered["date"].drop_duplicates().iloc[:-7]
    train_df = ordered[ordered["date"].isin(split_idx)]
    test_df = ordered[~ordered["date"].isin(split_idx)]

    def fit_for(cols: list[str]):
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
        return model, preds, residuals

    full_model, full_preds, full_residuals = fit_for(full_cols)
    baseline_model, baseline_preds, _ = fit_for(base_cols)
    trigger_model, trigger_preds, _ = fit_for(trigger_cols)

    test_actual = test_df["actual_demand"].reset_index(drop=True)
    full_mae = float(np.mean(np.abs(test_actual - full_preds.reset_index(drop=True))))
    baseline_mae = float(np.mean(np.abs(test_actual - baseline_preds.reset_index(drop=True))))
    trigger_mae = float(np.mean(np.abs(test_actual - trigger_preds.reset_index(drop=True))))

    return {
        "full_model": full_model,
        "full_cols": full_cols,
        "full_residual_std": float(np.std(full_residuals, ddof=1)),
        "full_mae": round(full_mae, 2),
        "baseline_mae": round(baseline_mae, 2),
        "trigger_mae": round(trigger_mae, 2),
        "rolling_mae": compute_rolling_mae(ordered, full_cols),
    }


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
        score = (
            bus.capacity * 0.09
            - bus.eta_min * 0.35
            + bus.route_fit * 8.5
            - bus.utilization_pct * 0.02
            + bus.shift_remaining_min * 0.006
            - demand_pressure * 0.2
        )
        objective_terms.append(score * variables[bus.bus_id])
    solver.Maximize(solver.Sum(objective_terms))
    solver.Solve()

    rows: list[dict[str, Any]] = []
    chosen = fleet[0]
    best_score = -1e9
    for bus in fleet:
        score = (
            bus.capacity * 0.09
            - bus.eta_min * 0.35
            + bus.route_fit * 8.5
            - bus.utilization_pct * 0.02
            + bus.shift_remaining_min * 0.006
            - demand_pressure * 0.2
        )
        est_wait = max(5.0, float(row["baseline_wait_min"]) - (6.6 + score))
        feasible = bus.utilization_pct <= 95 and bus.shift_remaining_min >= 90 and bus.route_fit >= 0.7
        rows.append(
            {
                "bus_id": bus.bus_id,
                "eta_min": bus.eta_min,
                "capacity": bus.capacity,
                "utilization_pct": bus.utilization_pct,
                "shift_remaining_min": bus.shift_remaining_min,
                "route_fit": round(bus.route_fit, 2),
                "score": round(score, 2),
                "estimated_wait_after_dispatch": round(est_wait, 2),
                "feasible": "yes" if feasible else "no",
            }
        )
        if feasible and score > best_score:
            best_score = score
            chosen = bus

    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True), chosen


def predict_row(models: dict[str, Any], row: pd.Series) -> tuple[float, float, float, pd.DataFrame]:
    x_row = build_feature_matrix(pd.DataFrame([row]), models["full_cols"])
    prediction = float(models["full_model"].predict(x_row)[0])
    lower = max(0.0, prediction - 1.28 * models["full_residual_std"])
    upper = prediction + 1.28 * models["full_residual_std"]
    return prediction, lower, upper, x_row


def load_logs(table: str, limit: int = 10) -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}", conn)
    return df.to_dict(orient="records")


def insert_override(corridor: str, forecast: float, recommendation: str, operator_action: str, outcome: str, notes: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO override_log (ts, corridor, forecast, recommendation, operator_action, outcome, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), corridor, forecast, recommendation, operator_action, outcome, notes),
        )
        conn.commit()


def insert_sms(phone: str, message: str, status: str, payload: dict[str, Any]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO sms_log (ts, phone, message, status, payload) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), phone, message, status, json.dumps(payload, ensure_ascii=True)),
        )
        conn.commit()


def build_series_for_day(df: pd.DataFrame, date_value: pd.Timestamp) -> dict[str, Any]:
    day_df = df[df["date"] == date_value].sort_values("hour")
    return {
        "hours": day_df["hour_label"].tolist(),
        "baseline": day_df["baseline_wait_min"].round(2).tolist(),
        "busiq": day_df["busiq_wait_min"].round(2).tolist(),
    }


def map_payload() -> dict[str, Any]:
    return {
        "corridor": [
            {"x": 12, "y": 68},
            {"x": 28, "y": 57},
            {"x": 49, "y": 49},
            {"x": 70, "y": 43},
            {"x": 88, "y": 37},
        ],
        "heat": [
            {"x": 49, "y": 49, "r": 16},
            {"x": 63, "y": 44, "r": 12},
            {"x": 39, "y": 55, "r": 10},
        ],
        "buses": [
            {"id": "KA-01-F-2234", "x": 29, "y": 57, "color": "#45f2ff"},
            {"id": "KA-01-F-2288", "x": 51, "y": 48, "color": "#61ff8f"},
            {"id": "KA-01-F-2201", "x": 71, "y": 43, "color": "#ffba5c"},
        ],
    }


def get_top_features(row: pd.Series) -> list[dict[str, Any]]:
    # Lightweight interpretable proxy for UI tags and bars.
    scores = {
        "rain_mm": float(row["rain_mm"] * 6.8),
        "metro_delay_min": float(row["metro_delay_min"] * 4.1),
        "od_index": float((row["od_index"] - 4200) / 28.0),
        "traffic_index": float(row["traffic_index"] * 15.0),
        "scheduled_headway_min": float((12.0 - row["scheduled_headway_min"]) * 3.6),
        "peak_flag": float(row["peak_flag"] * 10.0),
    }
    ordered = sorted(scores.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [{"name": k, "value": round(v, 2)} for k, v in ordered[:6]]


def bootstrap_engine() -> dict[str, Any]:
    init_db()
    df = build_demo_data()
    models = train_models(df)
    return {"df": df, "models": models}
