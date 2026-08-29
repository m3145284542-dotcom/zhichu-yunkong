"""Decision metrics and numerical constraint checks for Phase 5."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .model import BatteryConfig


def oracle_capture_ratio(no_battery_peak: float, controller_peak: float, oracle_peak: float, tolerance: float = 1e-9) -> float:
    available_gain = float(no_battery_peak) - float(oracle_peak)
    if abs(available_gain) <= tolerance:
        return float("nan")
    return (float(no_battery_peak) - float(controller_peak)) / available_gain


def daily_performance(original_load: np.ndarray, realized_grid_load: np.ndarray, charge: np.ndarray, discharge: np.ndarray) -> dict[str, float]:
    original = np.asarray(original_load, dtype=float)
    realized = np.asarray(realized_grid_load, dtype=float)
    original_peak = float(original.max())
    realized_peak = float(realized.max())
    reduction = original_peak - realized_peak
    return {
        "original_peak": original_peak,
        "realized_peak": realized_peak,
        "peak_reduction": reduction,
        "peak_reduction_pct": 100.0 * reduction / original_peak if abs(original_peak) > 1e-12 else np.nan,
        "total_charge": float(np.sum(charge)),
        "total_discharge": float(np.sum(discharge)),
        "throughput": float(np.sum(charge) + np.sum(discharge)),
    }


def aggregate_performance(hourly_grid_load: np.ndarray, daily_metrics: pd.DataFrame, capacity: float | None) -> dict[str, float]:
    grid = np.asarray(hourly_grid_load, dtype=float)
    total_charge = float(daily_metrics["total_charge"].sum())
    total_discharge = float(daily_metrics["total_discharge"].sum())
    return {
        "mean_daily_peak": float(daily_metrics["realized_peak"].mean()),
        "max_peak": float(grid.max()),
        "mean_peak_reduction": float(daily_metrics["peak_reduction"].mean()),
        "mean_peak_reduction_pct": float(daily_metrics["peak_reduction_pct"].mean()),
        "p95_grid_load": float(np.percentile(grid, 95)),
        "PAR": float(grid.max() / grid.mean()),
        "total_charge": total_charge,
        "total_discharge": total_discharge,
        "throughput": total_charge + total_discharge,
        # EFC is discharged energy divided by nominal capacity throughout Phase 5.
        "equivalent_full_cycles": total_discharge / capacity if capacity else 0.0,
    }


def constraint_counts(charge: np.ndarray, discharge: np.ndarray, soc: np.ndarray, config: BatteryConfig, tolerance: float = 1e-6) -> dict[str, int]:
    charge = np.asarray(charge, dtype=float)
    discharge = np.asarray(discharge, dtype=float)
    soc = np.asarray(soc, dtype=float)
    return {
        "soc_violations": int(np.sum((soc < config.soc_min - tolerance) | (soc > config.soc_max + tolerance))),
        "power_violations": int(
            np.sum((charge < -tolerance) | (charge > config.max_charge_power + tolerance))
            + np.sum((discharge < -tolerance) | (discharge > config.max_discharge_power + tolerance))
        ),
        "simultaneous_charge_discharge_violations": int(np.sum((charge > tolerance) & (discharge > tolerance))),
    }
