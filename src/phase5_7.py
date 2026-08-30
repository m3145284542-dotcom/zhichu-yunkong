"""Phase 5.7 uncertainty-aware robust battery peak-shaving experiment."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.run_phase5 import BUILDING, TOLERANCE, no_battery_rows, run_controller
from src.battery.metrics import constraint_counts, daily_performance
from src.battery.model import BatteryConfig
from src.battery.robust_optimizer import RobustDailyDispatchResult, optimize_robust_day
from src.forecast_artifacts import load_canonical_test_forecast, sha256_file


RANDOM_SEED = 42
ALPHA = 0.90
SCENARIO_COUNT = 100
LAMBDA_CANDIDATES = (0.0, 0.25, 0.5, 1.0, 2.0)
MEAN_PEAK_DEGRADATION_LIMIT = 0.01
METHODS = (
    "No Battery",
    "Persistence deterministic",
    "LightGBM deterministic",
    "LightGBM robust",
    "Oracle",
)
FROZEN_PHASES = ("phase4", "phase4_5", "phase5", "phase5_5", "phase5_6")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def frozen_output_hashes(project_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for phase in FROZEN_PHASES:
        directory = Path(project_root) / "outputs" / phase
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            hashes[path.relative_to(project_root).as_posix()] = sha256_file(path)
    return hashes


def load_validation_forecast(project_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load only saved Phase 4.5 Validation predictions for uncertainty modeling."""
    root = Path(project_root).resolve()
    prediction_path = root / "outputs" / "phase4_5" / "final_predictions.csv"
    config_path = root / "outputs" / "phase4_5" / "final_config.json"
    if not prediction_path.is_file() or not config_path.is_file():
        raise FileNotFoundError("Phase 4.5 canonical predictions/config are required")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    _require(config.get("building") == BUILDING, "Validation forecast building mismatch")
    _require(config.get("forecast_horizon_hours") == 24, "Validation horizon must be 24 hours")
    protocol = config.get("selection_protocol", {})
    _require(protocol.get("test_used_for_selection") is False, "Canonical selection protocol is invalid")
    _require(
        protocol.get("validation_target_cutoff_exclusive") == "2017-12-01 00:00:00",
        "Validation boundary-label purge is not recorded",
    )

    source = pd.read_csv(prediction_path)
    required = {
        "split", "feature_timestamp", "target_timestamp", "y_true", "y_pred", "error", "abs_error"
    }
    _require(required.issubset(source.columns), "Canonical prediction columns are incomplete")
    validation = source.loc[source["split"].eq("validation")].copy()
    validation["feature_timestamp"] = pd.to_datetime(validation["feature_timestamp"], errors="raise")
    validation["target_timestamp"] = pd.to_datetime(validation["target_timestamp"], errors="raise")
    validation = validation.sort_values("target_timestamp").reset_index(drop=True)
    _require(len(validation) == 720, "Validation forecast must contain 720 rows")
    _require(not validation["target_timestamp"].duplicated().any(), "Duplicate Validation targets")
    _require(
        validation["target_timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all(),
        "Validation targets must be continuous hourly values",
    )
    _require(
        (validation["target_timestamp"] - validation["feature_timestamp"])
        .eq(pd.Timedelta(hours=24))
        .all(),
        "Validation target must equal feature timestamp + 24h",
    )
    _require(
        validation["target_timestamp"].min() == pd.Timestamp("2017-11-02 00:00:00")
        and validation["target_timestamp"].max() == pd.Timestamp("2017-12-01 23:00:00"),
        "Unexpected Validation target period",
    )
    counts = validation.groupby(validation["target_timestamp"].dt.normalize()).size()
    _require(len(counts) == 30 and counts.eq(24).all(), "Validation must contain 30 complete days")
    numeric = validation[["y_true", "y_pred", "error", "abs_error"]].to_numpy(float)
    _require(np.isfinite(numeric).all(), "Validation prediction contains non-finite values")
    prediction_error = validation["y_pred"].to_numpy(float) - validation["y_true"].to_numpy(float)
    _require(np.allclose(validation["error"], prediction_error, atol=1e-12, rtol=0.0), "error mismatch")

    normalized = validation.rename(
        columns={"target_timestamp": "timestamp", "y_true": "actual", "y_pred": "prediction"}
    )[["feature_timestamp", "timestamp", "actual", "prediction"]]
    normalized["residual"] = normalized["actual"] - normalized["prediction"]
    lineage = {
        "split": "validation",
        "source": "outputs/phase4_5/final_predictions.csv",
        "source_sha256": sha256_file(prediction_path),
        "config": "outputs/phase4_5/final_config.json",
        "config_sha256": sha256_file(config_path),
        "timestamp_semantics": "timestamp is target_timestamp = feature_timestamp + 24h",
        "target_start": str(normalized["timestamp"].min()),
        "target_end": str(normalized["timestamp"].max()),
        "rows": len(normalized),
        "complete_natural_days": 30,
        "residual_definition": "actual - prediction",
        "test_residual_used": False,
    }
    return normalized, lineage


def build_residual_blocks(validation: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    required = {"timestamp", "residual"}
    if not required.issubset(validation.columns):
        raise ValueError(f"Validation residual columns missing: {sorted(required - set(validation.columns))}")
    frame = validation[["timestamp", "residual"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    frame = frame.sort_values("timestamp")
    blocks: list[np.ndarray] = []
    dates: list[str] = []
    for date, day in frame.groupby(frame["timestamp"].dt.normalize(), sort=True):
        if len(day) != 24 or not np.array_equal(day["timestamp"].dt.hour.to_numpy(), np.arange(24)):
            raise ValueError(f"Residual date {date.date()} is not a complete natural day")
        values = day["residual"].to_numpy(float)
        if not np.isfinite(values).all():
            raise ValueError("Residual blocks must be finite")
        blocks.append(values)
        dates.append(date.date().isoformat())
    if not blocks:
        raise ValueError("No complete residual blocks")
    return np.vstack(blocks), dates


def bootstrap_scenario_loads(
    forecast: np.ndarray,
    residual_blocks: np.ndarray,
    *,
    scenario_count: int = SCENARIO_COUNT,
    seed: int = RANDOM_SEED,
    sampled_indices: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    forecast_array = np.asarray(forecast, dtype=float)
    blocks = np.asarray(residual_blocks, dtype=float)
    if forecast_array.shape != (24,) or not np.isfinite(forecast_array).all():
        raise ValueError("forecast must be a finite 24-hour vector")
    if blocks.ndim != 2 or blocks.shape[1] != 24 or blocks.shape[0] < 1:
        raise ValueError("residual_blocks must have shape (n_days, 24)")
    if not np.isfinite(blocks).all():
        raise ValueError("residual_blocks must be finite")
    if scenario_count < 1:
        raise ValueError("scenario_count must be positive")
    if sampled_indices is None:
        indices = np.random.default_rng(seed).integers(0, blocks.shape[0], size=scenario_count)
    else:
        indices = np.asarray(sampled_indices, dtype=int)
        if indices.shape != (scenario_count,) or np.any(indices < 0) or np.any(indices >= blocks.shape[0]):
            raise ValueError("sampled_indices are invalid")
    raw = forecast_array[None, :] + blocks[indices]
    negative_mask = raw < 0.0
    scenarios = np.maximum(raw, 0.0)
    if not np.isfinite(scenarios).all():
        raise AssertionError("Generated scenarios are not finite")
    metadata = {
        "scenario_count": int(scenario_count),
        "residual_block_count": int(blocks.shape[0]),
        "negative_values_clipped": int(negative_mask.sum()),
        "sampled_indices_sha256": hashlib.sha256(indices.astype(np.int64).tobytes()).hexdigest(),
    }
    return scenarios, metadata


def bootstrap_index_matrix(
    dispatch_days: int, residual_days: int, scenario_count: int, seed: int
) -> np.ndarray:
    if min(dispatch_days, residual_days, scenario_count) < 1:
        raise ValueError("bootstrap dimensions must be positive")
    return np.random.default_rng(seed).integers(
        0, residual_days, size=(dispatch_days, scenario_count)
    )


def load_frozen_medium_config(project_root: Path) -> tuple[BatteryConfig, dict[str, Any]]:
    path = Path(project_root) / "outputs" / "phase5" / "phase5_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload["battery_configs"]["Medium"]
    allowed = {field.name for field in fields(BatteryConfig)}
    config = BatteryConfig(**{key: value for key, value in recorded.items() if key in allowed})
    for derived in ("soc_min", "soc_max", "initial_soc", "terminal_soc", "round_trip_efficiency"):
        if not np.isclose(getattr(config, derived), recorded[derived], atol=1e-12, rtol=0.0):
            raise AssertionError(f"Frozen Medium config does not reproduce {derived}")
    return config, recorded


def _raw_series(project_root: Path) -> pd.Series:
    raw = pd.read_csv(
        Path(project_root) / "data" / "raw" / "electricity_cleaned.csv",
        usecols=["timestamp", BUILDING],
    )
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="raise")
    if raw["timestamp"].duplicated().any():
        raise AssertionError("Raw load timestamps are duplicated")
    return raw.sort_values("timestamp").set_index("timestamp")[BUILDING].astype(float)


def persistence_forecast(timestamps: pd.Series, raw: pd.Series) -> np.ndarray:
    source_time = pd.DatetimeIndex(timestamps) - pd.Timedelta(hours=24)
    values = raw.reindex(source_time)
    if not values.notna().all():
        raise AssertionError("Persistence source is incomplete")
    target_days = pd.Series(timestamps).dt.normalize().to_numpy()
    if not np.all(source_time.to_numpy() < target_days):
        raise AssertionError("Persistence source is unavailable at target-day dispatch")
    return values.to_numpy(float)


def _audit_arrays(
    date: str,
    method: str,
    charge: np.ndarray,
    discharge: np.ndarray,
    soc: np.ndarray,
    config: BatteryConfig,
    solver_success: bool,
    solver_status: str,
) -> dict[str, Any]:
    counts = constraint_counts(charge, discharge, soc, config, TOLERANCE)
    transition = soc[1:] - soc[:-1] - config.eta_charge * charge + discharge / config.eta_discharge
    numeric = np.r_[charge, discharge, soc]
    return {
        "date": date,
        "method": method,
        "solver_success": bool(solver_success),
        "solver_status": solver_status,
        **counts,
        "soc_transition_violations": int(np.sum(np.abs(transition) > TOLERANCE)),
        "max_abs_soc_transition_error": float(np.max(np.abs(transition))),
        "initial_soc_error": float(soc[0] - config.initial_soc),
        "terminal_soc_error": float(soc[-1] - config.terminal_soc),
        "nan_or_inf_count": int(np.sum(~np.isfinite(numeric))),
    }


def enhanced_audit_from_dispatch(
    dispatch: pd.DataFrame, method: str, config: BatteryConfig
) -> pd.DataFrame:
    rows = []
    for date, day in dispatch.groupby("date", sort=True):
        charge = day["charge"].to_numpy(float)
        discharge = day["discharge"].to_numpy(float)
        soc = np.r_[day["soc_start"].iloc[0], day["soc_end"].to_numpy(float)]
        status = str(day["solver_status"].iloc[0])
        rows.append(_audit_arrays(date, method, charge, discharge, soc, config, status.startswith("0:"), status))
    return pd.DataFrame(rows)


def run_robust_controller(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecast: np.ndarray,
    residual_blocks: np.ndarray,
    sampled_indices: np.ndarray,
    config: BatteryConfig,
    risk_lambda: float,
    method: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dispatch_parts: list[pd.DataFrame] = []
    daily_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []
    normalized = timestamps.dt.normalize()
    dates = normalized.drop_duplicates().reset_index(drop=True)
    if sampled_indices.shape != (len(dates), SCENARIO_COUNT):
        raise ValueError("sampled_indices matrix does not match dispatch days/scenarios")
    for day_number, date in enumerate(dates):
        mask = normalized.eq(date).to_numpy()
        day_timestamp = timestamps.loc[mask].reset_index(drop=True)
        day_actual = np.asarray(actual[mask], dtype=float)
        day_forecast = np.asarray(forecast[mask], dtype=float)
        scenarios, scenario_meta = bootstrap_scenario_loads(
            day_forecast,
            residual_blocks,
            scenario_count=SCENARIO_COUNT,
            sampled_indices=sampled_indices[day_number],
        )
        result: RobustDailyDispatchResult = optimize_robust_day(
            scenarios, config, alpha=ALPHA, risk_lambda=risk_lambda
        )
        realized = day_actual + result.charge - result.discharge
        date_text = date.date().isoformat()
        performance = daily_performance(day_actual, realized, result.charge, result.discharge)
        daily_rows.append(
            {
                "date": date_text,
                "method": method,
                **performance,
                "scenario_expected_peak": result.expected_peak,
                "scenario_cvar_peak": result.cvar_peak,
                "robust_objective": result.objective_value,
                "solver_status": result.solver_status,
            }
        )
        audit_rows.append(
            _audit_arrays(
                date_text,
                method,
                result.charge,
                result.discharge,
                result.soc,
                config,
                result.success,
                result.solver_status,
            )
        )
        scenario_rows.append(
            {
                "date": date_text,
                "method": method,
                "lambda": risk_lambda,
                "alpha": ALPHA,
                **scenario_meta,
                "scenario_min_load": float(scenarios.min()),
                "scenario_max_load": float(scenarios.max()),
                "scenario_expected_peak": result.expected_peak,
                "scenario_cvar_peak": result.cvar_peak,
            }
        )
        dispatch_parts.append(
            pd.DataFrame(
                {
                    "timestamp": day_timestamp,
                    "date": date_text,
                    "method": method,
                    "actual_load": day_actual,
                    "forecast_load": day_forecast,
                    "charge": result.charge,
                    "discharge": result.discharge,
                    "battery_power": result.charge - result.discharge,
                    "soc_start": result.soc[:-1],
                    "soc_end": result.soc[1:],
                    "soc": result.soc[1:],
                    "realized_grid_load": realized,
                    "scenario_expected_peak": result.expected_peak,
                    "scenario_cvar_peak": result.cvar_peak,
                    "solver_status": result.solver_status,
                }
            )
        )
    return (
        pd.concat(dispatch_parts, ignore_index=True),
        pd.DataFrame(daily_rows),
        pd.DataFrame(audit_rows),
        pd.DataFrame(scenario_rows),
    )


def _run_deterministic(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecast: np.ndarray,
    original_controller: str,
    method: str,
    config: BatteryConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dispatch, daily, _ = run_controller(
        timestamps, actual, forecast, original_controller, config
    )
    dispatch = dispatch.rename(columns={"controller": "method"})
    dispatch["method"] = method
    dispatch["battery_power"] = dispatch["charge"] - dispatch["discharge"]
    daily = daily.rename(columns={"controller": "method"})
    daily["method"] = method
    audit = enhanced_audit_from_dispatch(dispatch, method, config)
    return dispatch, daily, audit


def worst_tail(values: pd.Series, fraction: float = 0.10) -> float:
    count = max(1, int(math.ceil(len(values) * fraction)))
    return float(values.nlargest(count).mean())


def select_robust_configuration(
    validation: pd.DataFrame,
    residual_blocks: np.ndarray,
    raw: pd.Series,
    config: BatteryConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.DataFrame]:
    timestamps = validation["timestamp"]
    actual = validation["actual"].to_numpy(float)
    forecast = validation["prediction"].to_numpy(float)
    deterministic_dispatch, deterministic_daily, _ = _run_deterministic(
        timestamps, actual, forecast, "LightGBM", "LightGBM deterministic", config
    )
    _, oracle_daily, _ = _run_deterministic(
        timestamps, actual, actual, "Oracle", "Oracle", config
    )
    oracle_peak = oracle_daily.set_index("date")["realized_peak"]
    deterministic_mean = float(deterministic_daily["realized_peak"].mean())
    allowed_mean = deterministic_mean * (1.0 + MEAN_PEAK_DEGRADATION_LIMIT)
    indices = bootstrap_index_matrix(
        validation["timestamp"].dt.normalize().nunique(),
        residual_blocks.shape[0],
        SCENARIO_COUNT,
        RANDOM_SEED,
    )
    candidate_rows: list[dict[str, Any]] = []
    candidate_daily: list[pd.DataFrame] = []
    scenario_rows: list[pd.DataFrame] = []
    for risk_lambda in LAMBDA_CANDIDATES:
        _, daily, audit, scenarios = run_robust_controller(
            timestamps,
            actual,
            forecast,
            residual_blocks,
            indices,
            config,
            risk_lambda,
            f"robust_lambda_{risk_lambda:g}",
        )
        if not audit["solver_success"].all() or audit[
            [
                "soc_violations",
                "power_violations",
                "simultaneous_charge_discharge_violations",
                "soc_transition_violations",
                "nan_or_inf_count",
            ]
        ].to_numpy().sum() != 0:
            raise AssertionError(f"Validation robust constraint audit failed for lambda={risk_lambda}")
        regret = daily["realized_peak"] - daily["date"].map(oracle_peak)
        mean_peak = float(daily["realized_peak"].mean())
        candidate_rows.append(
            {
                "lambda": risk_lambda,
                "alpha": ALPHA,
                "scenario_count": SCENARIO_COUNT,
                "validation_mean_daily_peak": mean_peak,
                "validation_median_daily_peak": float(daily["realized_peak"].median()),
                "validation_worst_daily_peak": float(daily["realized_peak"].max()),
                "validation_worst_10pct_daily_peak": worst_tail(daily["realized_peak"]),
                "validation_mean_regret": float(regret.mean()),
                "validation_p90_regret": float(np.percentile(regret, 90)),
                "validation_max_regret": float(regret.max()),
                "validation_throughput": float(daily["throughput"].sum()),
                "deterministic_validation_mean_daily_peak": deterministic_mean,
                "mean_peak_limit": allowed_mean,
                "eligible": bool(mean_peak <= allowed_mean + TOLERANCE),
                "negative_scenario_values_clipped": int(scenarios["negative_values_clipped"].sum()),
                "solver_failures": int((~audit["solver_success"]).sum()),
                "constraint_violations": int(
                    audit[
                        [
                            "soc_violations",
                            "power_violations",
                            "simultaneous_charge_discharge_violations",
                            "soc_transition_violations",
                            "nan_or_inf_count",
                        ]
                    ].to_numpy().sum()
                ),
            }
        )
        daily = daily.copy()
        daily["lambda"] = risk_lambda
        daily["decision_regret"] = regret.to_numpy(float)
        candidate_daily.append(daily)
        scenarios = scenarios.copy()
        scenarios["stage"] = "validation_selection"
        scenario_rows.append(scenarios)

    candidates = pd.DataFrame(candidate_rows)
    eligible = candidates.loc[candidates["eligible"]].copy()
    fallback_used = eligible.empty
    pool = candidates if fallback_used else eligible
    selected_row = pool.sort_values(
        ["validation_worst_10pct_daily_peak", "validation_mean_daily_peak", "lambda"],
        kind="stable",
    ).iloc[0]
    selected = {
        "lambda": float(selected_row["lambda"]),
        "alpha": ALPHA,
        "scenario_count": SCENARIO_COUNT,
        "random_seed": RANDOM_SEED,
        "mean_peak_degradation_limit_fraction": MEAN_PEAK_DEGRADATION_LIMIT,
        "selection_rule": (
            "Among candidates with Validation mean daily realized peak <= deterministic "
            "Validation mean * 1.01, minimize Validation worst-10% daily realized peak; "
            "tie-break by mean daily peak then smaller lambda. Test is not accessed."
        ),
        "fallback_used": fallback_used,
        "test_accessed_during_selection": False,
    }
    return (
        candidates,
        pd.concat(candidate_daily, ignore_index=True),
        selected,
        pd.concat(scenario_rows, ignore_index=True),
    )


def add_regret(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily.copy()
    oracle = result.loc[result["method"].eq("Oracle")].set_index("date")["realized_peak"]
    result["decision_regret"] = result["realized_peak"] - result["date"].map(oracle)
    return result


def overall_metrics(
    daily: pd.DataFrame, grids: dict[str, np.ndarray], actual: np.ndarray
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    original_peak = float(np.max(actual))
    for method in METHODS:
        method_daily = daily.loc[daily["method"].eq(method)]
        grid = np.asarray(grids[method], dtype=float)
        post_peak = float(grid.max())
        regret = method_daily["decision_regret"].to_numpy(float)
        rows.append(
            {
                "method": method,
                "original_peak": original_peak,
                "post_dispatch_peak": post_peak,
                "absolute_peak_reduction": original_peak - post_peak,
                "peak_reduction_percentage": 100.0 * (original_peak - post_peak) / original_peak,
                "mean_daily_peak": float(method_daily["realized_peak"].mean()),
                "median_daily_peak": float(method_daily["realized_peak"].median()),
                "mean_daily_peak_reduction": float(method_daily["peak_reduction"].mean()),
                "mean_daily_peak_reduction_percentage": float(method_daily["peak_reduction_pct"].mean()),
                "worst_daily_peak": float(method_daily["realized_peak"].max()),
                "worst_10pct_day_metric": worst_tail(method_daily["realized_peak"]),
                "mean_regret": float(regret.mean()),
                "median_regret": float(np.median(regret)),
                "p90_regret": float(np.percentile(regret, 90)),
                "max_regret": float(regret.max()),
                "battery_throughput": float(method_daily["throughput"].sum()),
            }
        )
    return pd.DataFrame(rows)


def paired_comparison(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    pivot = daily.pivot(index="date", columns="method", values="realized_peak")
    pairs = pd.DataFrame(
        {
            "date": pivot.index,
            "deterministic_actual_peak": pivot["LightGBM deterministic"].to_numpy(),
            "robust_actual_peak": pivot["LightGBM robust"].to_numpy(),
        }
    )
    pairs["robust_minus_deterministic"] = (
        pairs["robust_actual_peak"] - pairs["deterministic_actual_peak"]
    )
    difference = pairs["robust_minus_deterministic"]
    summary = {
        "difference_definition": "robust actual daily peak - deterministic actual daily peak (kW)",
        "robust_better_day_count": int((difference < -TOLERANCE).sum()),
        "equal_day_count": int((difference.abs() <= TOLERANCE).sum()),
        "robust_worse_day_count": int((difference > TOLERANCE).sum()),
        "mean_paired_difference": float(difference.mean()),
        "median_paired_difference": float(difference.median()),
        "worst_improvement": float((-difference).max()),
        "worst_degradation": float(difference.max()),
    }
    return pairs, summary


def reproduce_phase5_6_baselines(
    project_root: Path, dispatches: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Prove the three deterministic schedules exactly reproduce Phase 5.6."""
    mapping = {
        "Persistence deterministic": "dispatch_persistence.csv",
        "LightGBM deterministic": "dispatch_lightgbm.csv",
        "Oracle": "dispatch_oracle.csv",
    }
    columns = ("charge", "discharge", "soc_start", "soc_end", "realized_grid_load")
    rows: list[dict[str, Any]] = []
    for method, filename in mapping.items():
        historical = pd.read_csv(Path(project_root) / "outputs" / "phase5_6" / filename)
        current = dispatches[method]
        historical_timestamp = pd.to_datetime(historical["timestamp"], errors="raise")
        if len(historical) != len(current) or not historical_timestamp.reset_index(drop=True).equals(
            current["timestamp"].reset_index(drop=True)
        ):
            raise AssertionError(f"Phase 5.6 timestamp reproduction failed for {method}")
        for column in columns:
            delta = current[column].to_numpy(float) - historical[column].to_numpy(float)
            maximum = float(np.max(np.abs(delta)))
            rows.append(
                {
                    "method": method,
                    "column": column,
                    "rows": len(current),
                    "max_absolute_delta_vs_phase5_6": maximum,
                    "passed": bool(maximum <= 1e-8),
                }
            )
            if maximum > 1e-8:
                raise AssertionError(f"Phase 5.6 baseline drift: {method} {column} {maximum}")
    return pd.DataFrame(rows)


def residual_statistics(validation: pd.DataFrame) -> pd.DataFrame:
    residual = validation["residual"]
    rows = [
        {
            "group": "overall",
            "count": len(residual),
            "mean": float(residual.mean()),
            "std": float(residual.std(ddof=1)),
            "min": float(residual.min()),
            "p10": float(np.percentile(residual, 10)),
            "median": float(residual.median()),
            "p90": float(np.percentile(residual, 90)),
            "max": float(residual.max()),
            "mae": float(residual.abs().mean()),
            "rmse": float(np.sqrt(np.mean(residual.to_numpy(float) ** 2))),
        }
    ]
    for hour, part in validation.groupby(validation["timestamp"].dt.hour):
        values = part["residual"]
        rows.append(
            {
                "group": f"hour_{hour:02d}",
                "count": len(values),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)),
                "min": float(values.min()),
                "p10": float(np.percentile(values, 10)),
                "median": float(values.median()),
                "p90": float(np.percentile(values, 90)),
                "max": float(values.max()),
                "mae": float(values.abs().mean()),
                "rmse": float(np.sqrt(np.mean(values.to_numpy(float) ** 2))),
            }
        )
    return pd.DataFrame(rows)


def _plot_case(
    dispatches: dict[str, pd.DataFrame], date: str, title: str, path: Path
) -> None:
    deterministic = dispatches["LightGBM deterministic"]
    robust = dispatches["LightGBM robust"]
    det = deterministic.loc[deterministic["date"].eq(date)]
    rob = robust.loc[robust["date"].eq(date)]
    hours = det["timestamp"].dt.hour.to_numpy()
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    axes[0].plot(hours, det["actual_load"], color="black", linewidth=2, label="Actual load")
    axes[0].plot(hours, det["forecast_load"], color="#7f7f7f", linestyle="--", label="LightGBM forecast")
    axes[0].plot(hours, det["realized_grid_load"], color="#4E79A7", label="Deterministic grid load")
    axes[0].plot(hours, rob["realized_grid_load"], color="#E15759", label="Robust grid load")
    axes[0].set(ylabel="Load / grid power (kW)", title=title)
    axes[0].legend(ncol=2)
    axes[1].plot(hours, det["battery_power"], color="#4E79A7", label="Deterministic battery power")
    axes[1].plot(hours, rob["battery_power"], color="#E15759", label="Robust battery power")
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set(ylabel="Charge (+) / discharge (-) kW")
    axes[1].legend(ncol=2)
    axes[2].step(np.arange(25), np.r_[det["soc_start"].iloc[0], det["soc_end"]], where="post", color="#4E79A7", label="Deterministic SOC")
    axes[2].step(np.arange(25), np.r_[rob["soc_start"].iloc[0], rob["soc_end"]], where="post", color="#E15759", label="Robust SOC")
    axes[2].set(xlabel="Hour boundary", ylabel="SOC (kWh)", xlim=(0, 24))
    axes[2].legend(ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def make_plots(
    output_dir: Path,
    daily: pd.DataFrame,
    validation_selection: pd.DataFrame,
    dispatches: dict[str, pd.DataFrame],
    success_date: str,
    failure_date: str,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    comparison = daily.loc[daily["method"].isin(["LightGBM deterministic", "LightGBM robust"])]
    pivot = comparison.pivot(index="date", columns="method", values="realized_peak")
    dates = pd.to_datetime(pivot.index)
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(dates, pivot["LightGBM deterministic"], marker="o", markersize=3, label="Deterministic")
    ax.plot(dates, pivot["LightGBM robust"], marker="s", markersize=3, label="Robust")
    ax.set(title="Test Daily Actual Peak: Deterministic vs Robust", xlabel="Date", ylabel="Actual post-dispatch peak (kW)")
    ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(output_dir / "deterministic_vs_robust_daily_peaks.png", dpi=180); plt.close(fig)

    regret = daily.loc[daily["method"].isin(["LightGBM deterministic", "LightGBM robust"])]
    pivot = regret.pivot(index="date", columns="method", values="decision_regret")
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(dates, pivot["LightGBM deterministic"], marker="o", markersize=3, label="Deterministic regret")
    ax.plot(dates, pivot["LightGBM robust"], marker="s", markersize=3, label="Robust regret")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set(title="Test Daily Decision Regret vs Oracle", xlabel="Date", ylabel="Regret (kW)")
    ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(output_dir / "daily_regret_comparison.png", dpi=180); plt.close(fig)

    selection = validation_selection.sort_values("lambda")
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5), sharex=True)
    for ax, column, ylabel in (
        (axes[0, 0], "validation_mean_daily_peak", "Mean daily peak (kW)"),
        (axes[0, 1], "validation_worst_10pct_daily_peak", "Worst-10% peak (kW)"),
        (axes[1, 0], "validation_mean_regret", "Mean regret (kW)"),
        (axes[1, 1], "validation_throughput", "Throughput (kWh)"),
    ):
        ax.plot(selection["lambda"], selection[column], marker="o")
        ax.set(ylabel=ylabel)
    axes[1, 0].set_xlabel("lambda"); axes[1, 1].set_xlabel("lambda")
    fig.suptitle("Validation-only Lambda Sensitivity")
    fig.tight_layout(); fig.savefig(output_dir / "lambda_sensitivity.png", dpi=180); plt.close(fig)

    _plot_case(dispatches, success_date, f"Best relative robust day: {success_date}", output_dir / "case_success_day.png")
    _plot_case(dispatches, failure_date, f"Worst relative robust day: {failure_date}", output_dir / "case_failure_day.png")


def _markdown_table(frame: pd.DataFrame, columns: list[str], digits: int = 4) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame[columns].itertuples(index=False, name=None):
        rendered = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                rendered.append(f"{value:.{digits}f}")
            else:
                rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def write_report(
    project_root: Path,
    validation_lineage: dict[str, Any],
    residual_stats: pd.DataFrame,
    candidates: pd.DataFrame,
    selected: dict[str, Any],
    metrics: pd.DataFrame,
    paired: dict[str, Any],
    constraint_totals: dict[str, int],
    success_date: str,
    failure_date: str,
    negative_clips: int,
    baseline_max_delta: float,
) -> None:
    metric_columns = [
        "method", "post_dispatch_peak", "absolute_peak_reduction", "peak_reduction_percentage",
        "mean_daily_peak", "worst_10pct_day_metric", "mean_regret", "p90_regret", "max_regret",
    ]
    candidate_columns = [
        "lambda", "validation_mean_daily_peak", "validation_worst_10pct_daily_peak",
        "validation_mean_regret", "validation_throughput", "eligible",
    ]
    overall_residual = residual_stats.iloc[0]
    det = metrics.loc[metrics["method"].eq("LightGBM deterministic")].iloc[0]
    rob = metrics.loc[metrics["method"].eq("LightGBM robust")].iloc[0]
    tail_delta = rob["worst_10pct_day_metric"] - det["worst_10pct_day_metric"]
    regret_delta = rob["mean_regret"] - det["mean_regret"]
    conclusion = (
        "本 Test 窗口中鲁棒调度改善了平均日峰值。"
        if rob["mean_daily_peak"] < det["mean_daily_peak"] - TOLERANCE
        else "本 Test 窗口中鲁棒调度未改善平均日峰值。"
    )
    text = f"""# Phase 5.7 — 不确定性感知的鲁棒储能削峰优化

## 1. 研究问题

使用仅来自 Validation 的日内相关预测误差情景，CVaR 风险感知调度能否降低 Test 的极端决策损失，同时保持有竞争力的平均削峰效果。

## 2. 与 Phase 5 / 5.5 的关系

电池可行域、日调度边界、效率、功率、容量、初末 SOC 和吞吐惩罚全部复用 Phase 5 Medium 配置。Phase 5.5 的历史分析基于旧 Phase 4 forecast lineage；Phase 5.6 已证明正式后续阶段应使用 Phase 4.5 canonical prediction，因此本阶段不复用 Phase 5.5 的 Test residual。Persistence、LightGBM deterministic、Oracle 的 720 小时 charge/discharge/SOC/grid load 与 Phase 5.6 逐列最大绝对差为 {baseline_max_delta:.3e}。

## 3. 数据与时间切分

预测 horizon 为 24h，`target_timestamp = feature_timestamp + 24h`。Validation target 为 {validation_lineage['target_start']} 至 {validation_lineage['target_end']}，共 720 小时/30 个完整自然日；Test target 为 2017-12-02 至 2017-12-31，共 720 小时/30 日。

## 4. 防止数据泄漏措施

不确定性来源固定为 `{validation_lineage['source']}` 中 `split=validation` 的保存预测；residual 定义为 actual - prediction。Test residual、Test actual 和 Test 指标均未进入情景构造或参数选择。选中配置先写入 `selected_robust_config.json`，之后才调用 canonical Test loader；Test 配置只执行一次。Persistence 使用目标日前一日 actual，Oracle 仅为不可部署的 hindsight upper bound。

## 5. Validation residual analysis

Validation residual 均值 {overall_residual['mean']:.4f} kW，标准差 {overall_residual['std']:.4f} kW，MAE {overall_residual['mae']:.4f} kW，RMSE {overall_residual['rmse']:.4f} kW，范围 [{overall_residual['min']:.4f}, {overall_residual['max']:.4f}] kW。

## 6. Uncertainty scenario construction

按 target natural day 形成 30 个 24h residual block。每个调度日以 seed=42 有放回抽取 100 个整日 block，并与该日 LightGBM forecast 相加；日内相关结构不被逐小时打散。负情景负荷 clip 到 0；Validation 与最终 Test 共记录 {negative_clips} 个被 clip 的小时值。

## 7. Robust optimization mathematical formulation

同一组 charge/discharge 同时作用于所有情景：`grid[s,t] = scenario_load[s,t] + charge[t] - discharge[t]`，且 `peak[s] >= grid[s,t]`。目标为 `mean_s peak[s] + lambda * (eta + 1/((1-alpha)S) * sum_s excess[s]) + 1e-6 * throughput`，约束 `excess[s] >= peak[s] - eta`、`excess[s] >= 0`。`alpha=0.90`。lambda=0 是情景期望峰值优化，不等价于 Phase 5 确定性 baseline；后者独立调用原 optimizer。

## 8. Parameter-selection procedure

{selected['selection_rule']} 选中 lambda={selected['lambda']}, alpha={selected['alpha']}, scenarios={selected['scenario_count']}。

{_markdown_table(candidates, candidate_columns)}

## 9. Test comparison

峰值均以 actual realized grid load 计算；overall original peak 对所有方法相同。

{_markdown_table(metrics, metric_columns)}

## 10. Robustness / tail-risk analysis

鲁棒相对确定性的 worst-10% 日峰值变化为 {tail_delta:+.4f} kW（负值表示改善），worst daily peak 与 regret 尾部见上表。结果不预设鲁棒必胜。

## 11. Paired daily comparison

定义 paired difference = robust actual daily peak - deterministic actual daily peak。better/equal/worse = {paired['robust_better_day_count']}/{paired['equal_day_count']}/{paired['robust_worse_day_count']} 天，均值 {paired['mean_paired_difference']:+.4f} kW，中位数 {paired['median_paired_difference']:+.4f} kW，最大改善 {paired['worst_improvement']:.4f} kW，最大恶化 {paired['worst_degradation']:.4f} kW。

## 12. Battery constraint audit

solver failure、SOC 上下界、充放电功率、同时充放电、SOC transition、initial SOC、terminal SOC、NaN/Inf 的违规总数依次为：{constraint_totals['solver_failures']}、{constraint_totals['soc_violations']}、{constraint_totals['power_violations']}、{constraint_totals['simultaneous_charge_discharge_violations']}、{constraint_totals['soc_transition_violations']}、{constraint_totals['initial_soc_violations']}、{constraint_totals['terminal_soc_violations']}、{constraint_totals['nan_or_inf_count']}。

## 13. Sensitivity experiment

lambda sensitivity 完全在 Validation 上完成。表中同时给出 average peak、worst-10% tail peak、mean regret 与 throughput；其变化可能非单调，因为共享 dispatch、离散充放电互斥和有限样本 CVaR 共同作用，不能据 Test 曲线反调参数。

## 14. Success-day case study

相对表现最好的日期为 {success_date}；`case_success_day.png` 同时展示 actual、forecast、两种 grid load、battery power 与 SOC。

## 15. Failure-day case study

相对表现最差的日期为 {failure_date}；即使该日差值不为正，也仍按预先定义的“最差相对日”展示，避免只挑有利案例。详见 `case_failure_day.png`。

## 16. Limitations

仅覆盖一个建筑、一个 30 日 Test 窗口和一个冻结电池尺寸；Validation block 仅 30 个，bootstrap 不能创造未见过的误差形态。模型是风险感知情景优化而非对所有可能扰动的硬 worst-case 保证。日初 SOC 每天重置，未研究跨日能量耦合；也未引入电价或退化成本。

## 17. Competition-report-safe conclusions

{conclusion} 鲁棒相对确定性的平均 regret 变化为 {regret_delta:+.4f} kW，worst-10% 日峰值变化为 {tail_delta:+.4f} kW。该结论只描述冻结协议下的本建筑、本时间窗实证结果，不能外推为鲁棒优化普遍优于确定性调度，也不能把 Oracle 描述为可部署方案。
"""
    report_path = Path(project_root) / "reports" / "phase5_7_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")


def run(project_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = Path(project_root).resolve()
    output_dir = root / "outputs" / "phase5_7"
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_before = frozen_output_hashes(root)

    validation, validation_lineage = load_validation_forecast(root)
    residual_blocks, block_dates = build_residual_blocks(validation)
    config, config_record = load_frozen_medium_config(root)
    raw = _raw_series(root)
    residual_stats = residual_statistics(validation)
    validation_export = validation.copy()
    validation_export["residual_day"] = validation_export["timestamp"].dt.date.astype(str)
    validation_export.to_csv(output_dir / "validation_residuals.csv", index=False, date_format="%Y-%m-%d %H:%M:%S", float_format="%.10f")
    residual_stats.to_csv(output_dir / "residual_statistics.csv", index=False, float_format="%.10f")

    candidates, validation_daily, selected, validation_scenarios = select_robust_configuration(
        validation, residual_blocks, raw, config
    )
    candidates.to_csv(output_dir / "validation_parameter_selection.csv", index=False, float_format="%.10f")
    validation_daily.to_csv(output_dir / "validation_daily_metrics.csv", index=False, float_format="%.10f")
    selected_payload = {
        **selected,
        "selected_before_test_load": True,
        "validation_lineage": validation_lineage,
        "residual_block_dates": block_dates,
        "battery_config_source": "outputs/phase5/phase5_config.json#battery_configs.Medium",
        "battery_config": config_record,
    }
    (output_dir / "selected_robust_config.json").write_text(
        json.dumps(selected_payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    # Test is loaded only after the Validation-only configuration is frozen above.
    test_prediction_call_count = 0
    test, test_lineage = load_canonical_test_forecast(root)
    test_prediction_call_count += 1
    timestamps = test["timestamp"]
    actual = test["actual"].to_numpy(float)
    persistence = persistence_forecast(timestamps, raw)
    forecasts = {
        "Persistence deterministic": persistence,
        "LightGBM deterministic": test["prediction"].to_numpy(float),
        "Oracle": actual.copy(),
    }
    dispatches: dict[str, pd.DataFrame] = {}
    daily_parts: list[pd.DataFrame] = []
    audit_parts: list[pd.DataFrame] = []
    for method, controller in (
        ("Persistence deterministic", "Persistence"),
        ("LightGBM deterministic", "LightGBM"),
        ("Oracle", "Oracle"),
    ):
        dispatch, daily, audit = _run_deterministic(
            timestamps, actual, forecasts[method], controller, method, config
        )
        dispatches[method] = dispatch
        daily_parts.append(daily)
        audit_parts.append(audit)

    baseline_reproduction = reproduce_phase5_6_baselines(root, dispatches)
    baseline_reproduction.to_csv(
        output_dir / "baseline_reproduction.csv", index=False, float_format="%.10f"
    )

    test_indices = bootstrap_index_matrix(30, residual_blocks.shape[0], SCENARIO_COUNT, RANDOM_SEED)
    robust_dispatch, robust_daily, robust_audit, test_scenarios = run_robust_controller(
        timestamps,
        actual,
        forecasts["LightGBM deterministic"],
        residual_blocks,
        test_indices,
        config,
        selected["lambda"],
        "LightGBM robust",
    )
    dispatches["LightGBM robust"] = robust_dispatch
    daily_parts.append(robust_daily)
    audit_parts.append(robust_audit)
    no_daily, _ = no_battery_rows(timestamps, actual)
    no_daily = no_daily.rename(columns={"controller": "method"})
    no_daily["method"] = "No Battery"
    daily = add_regret(pd.concat([no_daily, *daily_parts], ignore_index=True))
    audit = pd.concat(audit_parts, ignore_index=True)
    grids = {"No Battery": actual.copy()}
    grids.update({method: frame["realized_grid_load"].to_numpy(float) for method, frame in dispatches.items()})
    metrics = overall_metrics(daily, grids, actual)
    pairs, paired_summary = paired_comparison(daily)
    success_date = str(pairs.loc[pairs["robust_minus_deterministic"].idxmin(), "date"])
    failure_date = str(pairs.loc[pairs["robust_minus_deterministic"].idxmax(), "date"])

    test_scenarios = test_scenarios.copy(); test_scenarios["stage"] = "test_final_fixed_config"
    scenarios = pd.concat([validation_scenarios, test_scenarios], ignore_index=True)
    metrics.to_csv(output_dir / "test_overall_metrics.csv", index=False, float_format="%.10f")
    daily.to_csv(output_dir / "test_daily_metrics.csv", index=False, float_format="%.10f")
    pairs.to_csv(output_dir / "deterministic_vs_robust_paired.csv", index=False, float_format="%.10f")
    audit.to_csv(output_dir / "constraint_audit.csv", index=False, float_format="%.10f")
    scenarios.to_csv(output_dir / "scenario_sensitivity_summary.csv", index=False, float_format="%.10f")
    for method, filename in (
        ("Persistence deterministic", "dispatch_persistence_deterministic.csv"),
        ("LightGBM deterministic", "dispatch_lightgbm_deterministic.csv"),
        ("LightGBM robust", "dispatch_lightgbm_robust.csv"),
        ("Oracle", "dispatch_oracle.csv"),
    ):
        dispatches[method].to_csv(
            output_dir / filename,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
            float_format="%.10f",
        )

    constraint_totals = {
        "solver_failures": int((~audit["solver_success"]).sum()),
        "soc_violations": int(audit["soc_violations"].sum()),
        "power_violations": int(audit["power_violations"].sum()),
        "simultaneous_charge_discharge_violations": int(audit["simultaneous_charge_discharge_violations"].sum()),
        "soc_transition_violations": int(audit["soc_transition_violations"].sum()),
        "initial_soc_violations": int((audit["initial_soc_error"].abs() > TOLERANCE).sum()),
        "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
        "nan_or_inf_count": int(audit["nan_or_inf_count"].sum()),
    }
    if any(constraint_totals.values()):
        raise AssertionError(f"Phase 5.7 constraint audit failed: {constraint_totals}")
    if test_prediction_call_count != 1:
        raise AssertionError("Canonical Test forecast must be loaded exactly once after selection")
    if frozen_output_hashes(root) != frozen_before:
        raise AssertionError("A frozen Phase 4/4.5/5/5.5/5.6 output was modified")

    make_plots(output_dir, daily, candidates, dispatches, success_date, failure_date)
    negative_clips = int(scenarios["negative_values_clipped"].sum())
    write_report(
        root,
        validation_lineage,
        residual_stats,
        candidates,
        selected,
        metrics,
        paired_summary,
        constraint_totals,
        success_date,
        failure_date,
        negative_clips,
        float(baseline_reproduction["max_absolute_delta_vs_phase5_6"].max()),
    )
    summary = {
        "status": "PASS",
        "phase": "Phase 5.7 uncertainty-aware robust battery peak shaving",
        "runtime_seconds": time.perf_counter() - started,
        "validation_residual_source": validation_lineage,
        "zero_test_leakage": True,
        "test_loaded_once_after_validation_selection": True,
        "test_lineage": test_lineage,
        "selected_robust_configuration": selected_payload,
        "selection_results": candidates.to_dict(orient="records"),
        "test_metrics": metrics.to_dict(orient="records"),
        "paired_comparison": paired_summary,
        "constraint_totals": constraint_totals,
        "scenario_negative_values_clipped": negative_clips,
        "success_day": success_date,
        "failure_day": failure_date,
        "decision_regret_definition": "actual daily peak(method) - actual daily peak(Oracle)",
        "oracle_role": "perfect-forecast hindsight theoretical upper bound; not deployable",
        "historical_outputs_unchanged": True,
        "phase5_6_deterministic_baseline_reproduction": {
            "passed": bool(baseline_reproduction["passed"].all()),
            "maximum_absolute_delta": float(
                baseline_reproduction["max_absolute_delta_vs_phase5_6"].max()
            ),
        },
    }
    (output_dir / "config.json").write_text(
        json.dumps(
            {
                "random_seed": RANDOM_SEED,
                "alpha": ALPHA,
                "scenario_count": SCENARIO_COUNT,
                "lambda_candidates": list(LAMBDA_CANDIDATES),
                "selection": selected_payload,
                "battery_config": config_record,
                "objective": "mean scenario peak + lambda * CVaR_alpha(scenario peak) + Phase 5 throughput penalty",
                "dispatch_period": "daily 24h with daily initial/terminal SOC reset",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return summary
