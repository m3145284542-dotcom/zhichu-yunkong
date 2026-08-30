"""Phase 6 helpers for decision-oriented, peak-aware load forecasting.

The stage keeps the Phase 4.5 causal feature set and fixed 24-hour-ahead task,
but changes model selection from pure forecast error to downstream battery
peak-shaving value on Validation. Test is evaluated only after all candidate
choices are frozen.
"""

from __future__ import annotations

from dataclasses import asdict
from math import ceil
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.battery.metrics import constraint_counts, daily_performance
from src.battery.model import BatteryConfig
from src.battery.optimizer import optimize_day


WEEKLY_BLEND_WEIGHTS: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 1.0)
PEAK_SAMPLE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
PEAK_QUANTILE = 0.75
TOLERANCE = 1e-6


def safe_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = np.abs(actual) > 1e-12
    if not mask.any():
        return 0.0
    return float(100.0 * np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])))


def forecast_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    timestamps: Iterable[pd.Timestamp] | pd.Series | None = None,
) -> dict[str, float]:
    """Return whole-period and peak-focused forecast diagnostics."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.shape != predicted.shape:
        raise ValueError("actual and predicted must have identical shape")
    if actual.ndim != 1 or not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("actual and predicted must be finite one-dimensional arrays")

    error = predicted - actual
    p75 = float(np.quantile(actual, PEAK_QUANTILE))
    peak_mask = actual >= p75
    metrics = {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(np.square(error)))),
        "MAPE": safe_mape(actual, predicted),
        "bias": float(np.mean(error)),
        "actual_p75": p75,
        "peak_quartile_MAE": float(np.mean(np.abs(error[peak_mask]))),
        "peak_quartile_bias": float(np.mean(error[peak_mask])),
    }
    if timestamps is not None:
        metrics.update(daily_peak_timing_metrics(timestamps, actual, predicted))
    return metrics


def daily_peak_timing_metrics(
    timestamps: Iterable[pd.Timestamp] | pd.Series,
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:
    """Measure whether a forecast ranks the hours around each daily peak correctly."""
    ts = pd.Series(pd.to_datetime(list(timestamps), errors="raise"), name="timestamp")
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if len(ts) != len(actual) or len(actual) != len(predicted):
        raise ValueError("timestamps, actual and predicted must have equal length")

    frame = pd.DataFrame({"timestamp": ts, "actual": actual, "prediction": predicted})
    frame["date"] = frame["timestamp"].dt.normalize()
    hour_errors: list[float] = []
    top3_overlaps: list[float] = []
    exact_hits = 0
    days = 0
    for _, part in frame.groupby("date", sort=True):
        if len(part) != 24:
            continue
        days += 1
        actual_values = part["actual"].to_numpy(float)
        predicted_values = part["prediction"].to_numpy(float)
        actual_peak_idx = int(np.argmax(actual_values))
        predicted_peak_idx = int(np.argmax(predicted_values))
        hour_errors.append(float(abs(predicted_peak_idx - actual_peak_idx)))
        exact_hits += int(actual_peak_idx == predicted_peak_idx)
        actual_top3 = set(np.argsort(actual_values)[-3:].tolist())
        predicted_top3 = set(np.argsort(predicted_values)[-3:].tolist())
        top3_overlaps.append(len(actual_top3 & predicted_top3) / 3.0)
    if days == 0:
        return {
            "daily_peak_hour_MAE": float("nan"),
            "daily_peak_hour_exact_rate": float("nan"),
            "daily_top3_overlap": float("nan"),
        }
    return {
        "daily_peak_hour_MAE": float(np.mean(hour_errors)),
        "daily_peak_hour_exact_rate": float(exact_hits / days),
        "daily_top3_overlap": float(np.mean(top3_overlaps)),
    }


def day_week_blend(frame: pd.DataFrame, weekly_weight: float) -> np.ndarray:
    """Blend yesterday and same-hour-last-week forecasts.

    ``weekly_weight=0`` is yesterday persistence and ``weekly_weight=1`` is the
    last-week baseline. Both source columns are causal outputs of the Phase 4
    feature builder.
    """
    if not 0.0 <= float(weekly_weight) <= 1.0:
        raise ValueError("weekly_weight must lie in [0, 1]")
    required = {"yesterday_pred", "last_week_pred"}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing blend columns: {sorted(missing)}")
    yesterday = frame["yesterday_pred"].to_numpy(dtype=float)
    last_week = frame["last_week_pred"].to_numpy(dtype=float)
    prediction = (1.0 - float(weekly_weight)) * yesterday + float(weekly_weight) * last_week
    return np.maximum(prediction, 0.0)


def peak_sample_weights(target: np.ndarray, threshold: float, multiplier: float) -> np.ndarray:
    """Upweight training labels in the high-load region using a frozen threshold."""
    target = np.asarray(target, dtype=float)
    if target.ndim != 1 or not np.isfinite(target).all():
        raise ValueError("target must be a finite one-dimensional array")
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    if float(multiplier) < 1.0:
        raise ValueError("multiplier must be >= 1")
    weights = np.ones_like(target, dtype=float)
    weights[target >= float(threshold)] = float(multiplier)
    return weights


def load_medium_battery(project_root: Path) -> BatteryConfig:
    """Load the frozen Phase 5 Medium battery without changing its physics."""
    import json

    path = Path(project_root) / "outputs" / "phase5" / "phase5_config.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    config = json.loads(path.read_text(encoding="utf-8"))["battery_configs"]["Medium"]
    allowed = {
        "name",
        "capacity",
        "max_charge_power",
        "max_discharge_power",
        "soc_min_fraction",
        "soc_max_fraction",
        "initial_soc_fraction",
        "terminal_soc_fraction",
        "eta_charge",
        "eta_discharge",
        "throughput_penalty",
    }
    return BatteryConfig(**{key: value for key, value in config.items() if key in allowed})


def worst_fraction_mean(values: np.ndarray, fraction: float = 0.10) -> float:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("values must be a non-empty one-dimensional array")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must lie in (0, 1]")
    count = max(1, ceil(len(values) * fraction))
    return float(np.sort(values)[-count:].mean())


def run_dispatch(
    timestamps: Iterable[pd.Timestamp] | pd.Series,
    actual: np.ndarray,
    forecast: np.ndarray,
    method: str,
    config: BatteryConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run the frozen Phase 5 deterministic daily MILP on one forecast method."""
    ts = pd.Series(pd.to_datetime(list(timestamps), errors="raise"), name="timestamp")
    actual = np.asarray(actual, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    if len(ts) != len(actual) or len(actual) != len(forecast):
        raise ValueError("timestamps, actual and forecast must have equal length")
    if not np.isfinite(actual).all() or not np.isfinite(forecast).all():
        raise ValueError("actual and forecast must be finite")

    dates = ts.dt.normalize()
    day_counts = dates.value_counts()
    if not day_counts.eq(24).all():
        raise ValueError("dispatch evaluation requires complete 24-hour natural days")

    dispatch_parts: list[pd.DataFrame] = []
    daily_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for date in dates.drop_duplicates():
        mask = dates.eq(date).to_numpy()
        day_actual = actual[mask]
        day_forecast = forecast[mask]
        result = optimize_day(day_forecast, config)
        realized = day_actual + result.charge - result.discharge
        perf = daily_performance(day_actual, realized, result.charge, result.discharge)
        counts = constraint_counts(result.charge, result.discharge, result.soc, config, TOLERANCE)
        transition = (
            result.soc[:-1]
            + config.eta_charge * result.charge
            - result.discharge / config.eta_discharge
        )
        transition_error = result.soc[1:] - transition
        daily_rows.append(
            {
                "date": date.date().isoformat(),
                "method": method,
                **perf,
                "forecast_peak": float(day_forecast.max()),
                "solver_success": bool(result.success),
            }
        )
        audit_rows.append(
            {
                "date": date.date().isoformat(),
                "method": method,
                "solver_success": bool(result.success),
                **counts,
                "soc_transition_violations": int(np.sum(np.abs(transition_error) > TOLERANCE)),
                "max_abs_soc_transition_error": float(np.max(np.abs(transition_error))),
                "initial_soc_error": float(result.soc[0] - config.initial_soc),
                "terminal_soc_error": float(result.soc[-1] - config.terminal_soc),
                "nan_or_inf_count": int(
                    np.sum(
                        ~np.isfinite(
                            np.concatenate(
                                [result.charge, result.discharge, result.soc, realized]
                            )
                        )
                    )
                ),
            }
        )
        dispatch_parts.append(
            pd.DataFrame(
                {
                    "timestamp": ts.loc[mask].to_numpy(),
                    "date": date.date().isoformat(),
                    "method": method,
                    "actual_load": day_actual,
                    "forecast_load": day_forecast,
                    "charge": result.charge,
                    "discharge": result.discharge,
                    "soc_start": result.soc[:-1],
                    "soc_end": result.soc[1:],
                    "realized_grid_load": realized,
                    "optimized_forecast_grid_load": result.optimized_forecast_grid_load,
                }
            )
        )
    return (
        pd.concat(dispatch_parts, ignore_index=True),
        pd.DataFrame(daily_rows),
        pd.DataFrame(audit_rows),
    )


def summarize_dispatch(daily: pd.DataFrame, dispatch: pd.DataFrame) -> dict[str, float]:
    if daily.empty or dispatch.empty:
        raise ValueError("daily and dispatch must be non-empty")
    return {
        "mean_daily_peak": float(daily["realized_peak"].mean()),
        "worst_10pct_daily_peak": worst_fraction_mean(daily["realized_peak"].to_numpy(float), 0.10),
        "max_realized_peak": float(dispatch["realized_grid_load"].max()),
        "mean_peak_reduction": float(daily["peak_reduction"].mean()),
        "mean_peak_reduction_pct": float(daily["peak_reduction_pct"].mean()),
        "throughput": float(daily["throughput"].sum()),
    }


def select_validation_candidate(
    table: pd.DataFrame,
    parameter_column: str,
) -> dict[str, object]:
    """Freeze one candidate using downstream Validation decision value.

    Primary criterion is lower mean daily realized peak; worst-10% daily peak,
    forecast MAE, and then the smaller parameter value are deterministic tie
    breakers. No Test quantity belongs in ``table``.
    """
    required = {
        parameter_column,
        "validation_mean_daily_peak",
        "validation_worst_10pct_daily_peak",
        "validation_MAE",
    }
    missing = required - set(table.columns)
    if missing:
        raise KeyError(f"Candidate table missing columns: {sorted(missing)}")
    ordered = table.sort_values(
        [
            "validation_mean_daily_peak",
            "validation_worst_10pct_daily_peak",
            "validation_MAE",
            parameter_column,
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    return ordered.iloc[0].to_dict()


def battery_config_dict(config: BatteryConfig) -> dict[str, object]:
    values = asdict(config)
    values.update(
        {
            "soc_min": config.soc_min,
            "soc_max": config.soc_max,
            "initial_soc": config.initial_soc,
            "terminal_soc": config.terminal_soc,
            "round_trip_efficiency": config.round_trip_efficiency,
        }
    )
    return values
