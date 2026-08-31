"""Normalized forecast metrics and frozen Phase 6 decision evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.battery.model import BatteryConfig
from src.phase6 import forecast_metrics, run_dispatch, worst_fraction_mean


def normalized_forecast_metrics(timestamps: pd.Series, actual: np.ndarray, prediction: np.ndarray, train_mean: float) -> dict[str, float]:
    result = forecast_metrics(actual, prediction, timestamps)
    result["normalized_MAE"] = result["MAE"] / train_mean
    result["normalized_RMSE"] = result["RMSE"] / train_mean
    return result


def evaluate_method(building: str, split: str, method: str, timestamps: pd.Series, actual: np.ndarray,
                    prediction: np.ndarray, battery: BatteryConfig, oracle_daily: pd.DataFrame | None = None):
    dispatch, daily, audit = run_dispatch(timestamps, actual, prediction, method, battery)
    for frame in (dispatch, daily, audit):
        frame.insert(0, "building", building); frame.insert(1, "split", split)
    if oracle_daily is None:
        regret = np.zeros(len(daily)); oracle_peaks = daily["realized_peak"].to_numpy(float)
    else:
        oracle_map = oracle_daily.set_index("date")["realized_peak"]
        oracle_peaks = daily["date"].map(oracle_map).to_numpy(float)
        if not np.isfinite(oracle_peaks).all(): raise AssertionError("Oracle date mismatch")
        regret = daily["realized_peak"].to_numpy(float) - oracle_peaks
    daily["regret_vs_oracle"] = regret
    original = daily["original_peak"].to_numpy(float)
    realized = daily["realized_peak"].to_numpy(float)
    available, captured = original - oracle_peaks, original - realized
    valid = np.abs(available) > 1e-9
    original_overall, realized_overall = float(np.max(actual)), float(dispatch["realized_grid_load"].max())
    metric = {
        "building": building, "split": split, "method": method,
        "no_battery_peak": original_overall, "post_dispatch_peak": realized_overall,
        "absolute_peak_reduction": original_overall - realized_overall,
        "peak_reduction_percentage": 100 * (original_overall - realized_overall) / original_overall,
        "mean_daily_peak": float(np.mean(realized)),
        "worst_10pct_daily_peak": worst_fraction_mean(realized),
        "mean_regret_vs_oracle": float(np.mean(regret)), "p90_regret": float(np.quantile(regret, .9)),
        "max_regret": float(np.max(regret)),
        "oracle_capture_ratio": float(np.mean(captured[valid] / available[valid])) if valid.any() else np.nan,
        "battery_throughput": float(daily["throughput"].sum()),
        "equivalent_full_cycles": float(daily["total_discharge"].sum() / battery.capacity),
    }
    return metric, daily, audit, dispatch


def audit_totals(audit: pd.DataFrame, dispatch: pd.DataFrame, tolerance: float = 1e-6) -> dict[str, int]:
    return {
        "solver_failures": int((~audit["solver_success"]).sum()),
        "soc_lower_upper_violations": int(audit["soc_violations"].sum()),
        "charge_discharge_limit_violations": int(audit["power_violations"].sum()),
        "simultaneous_charge_discharge_violations": int(audit["simultaneous_charge_discharge_violations"].sum()),
        "soc_transition_violations": int(audit["soc_transition_violations"].sum()),
        "initial_soc_violations": int((audit["initial_soc_error"].abs() > tolerance).sum()),
        "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > tolerance).sum()),
        "nan_inf_violations": int(audit["nan_or_inf_count"].sum()),
        "negative_forecast_violations": int((dispatch["forecast_load"] < -tolerance).sum()),
        "timestamp_alignment_violations": int(sum(
            part["timestamp"].duplicated().sum()
            + (0 if len(part) < 2 or pd.Series(pd.to_datetime(part["timestamp"])).diff().dropna().eq(pd.Timedelta(hours=1)).all() else 1)
            for _, part in dispatch.groupby(["building", "split", "method"], sort=False)
        )),
    }
