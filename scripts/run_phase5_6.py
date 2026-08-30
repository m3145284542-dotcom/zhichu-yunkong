"""Run Phase 5.6: repair forecast lineage and recompute peak-shaving results.

Phase 5 and Phase 5.5 are preserved as historical artifacts. This corrective
stage switches the deployable LightGBM controller from the original Phase 4
prediction file to the leakage-audited Phase 4.5 final Test forecast, while
holding battery assumptions and optimization logic fixed.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from scripts.run_phase5 import CONTROLLERS, TOLERANCE, no_battery_rows, run_controller, safe_prediction_metrics
from src.battery.metrics import aggregate_performance, oracle_capture_ratio
from src.battery.model import BatteryConfig
from src.forecast_artifacts import (
    BUILDING,
    HISTORICAL_PHASE4_PREDICTION_RELATIVE_PATH,
    TEST_TARGET_END,
    TEST_TARGET_START,
    load_canonical_test_forecast,
    sha256,
)


SIZE_ORDER = ("Medium", "Small", "Large")


def _load_raw_series(project_root: Path) -> pd.Series:
    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    raw = pd.read_csv(raw_path, usecols=["timestamp", BUILDING])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="raise")
    raw = raw.sort_values("timestamp")
    if raw["timestamp"].duplicated().any():
        raise AssertionError("Raw load contains duplicate timestamps")
    return raw.set_index("timestamp")[BUILDING].astype(float)


def _load_phase5_battery_configs(project_root: Path) -> tuple[dict[str, BatteryConfig], dict[str, Any]]:
    path = project_root / "outputs" / "phase5" / "phase5_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(BatteryConfig)}
    configs: dict[str, BatteryConfig] = {}
    for name in SIZE_ORDER:
        source = payload["battery_configs"][name]
        configs[name] = BatteryConfig(**{key: value for key, value in source.items() if key in allowed})
    return configs, payload


def _load_historical_phase4_forecast(project_root: Path) -> pd.DataFrame:
    path = project_root / HISTORICAL_PHASE4_PREDICTION_RELATIVE_PATH
    frame = pd.read_csv(path)
    required = {"timestamp", "actual", "prediction"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Historical Phase 4 prediction columns missing: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def _build_forecasts(
    predictions: pd.DataFrame,
    raw_series: pd.Series,
) -> dict[str, np.ndarray]:
    timestamps = predictions["timestamp"]
    expected = pd.date_range(TEST_TARGET_START, TEST_TARGET_END, freq="h")
    if not timestamps.equals(pd.Series(expected, name="timestamp")):
        raise AssertionError("Canonical target timestamps changed")

    actual_from_raw = raw_series.reindex(expected)
    if actual_from_raw.isna().any():
        raise AssertionError("Raw actual load is missing inside the Test target window")
    if not np.allclose(actual_from_raw.to_numpy(), predictions["actual"].to_numpy(), atol=1e-10, rtol=0.0):
        raise AssertionError("Phase 4.5 y_true does not match raw Test load")

    persistence_source = expected - pd.Timedelta(hours=24)
    persistence = raw_series.reindex(persistence_source)
    if persistence.isna().any():
        raise AssertionError("Persistence source has missing raw load")
    target_days = pd.Series(expected).dt.normalize().to_numpy()
    if not np.all(persistence_source.to_numpy() < target_days):
        raise AssertionError("Persistence uses information unavailable at target-day start")

    return {
        "Persistence": persistence.to_numpy(dtype=float),
        "LightGBM": predictions["prediction"].to_numpy(dtype=float),
        "Oracle": predictions["actual"].to_numpy(dtype=float),
    }


def _aggregate_rows(
    predictions: pd.DataFrame,
    forecasts: dict[str, np.ndarray],
    configs: dict[str, BatteryConfig],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    timestamps = predictions["timestamp"]
    actual = predictions["actual"].to_numpy(dtype=float)
    daily_no_battery, no_battery_aggregate = no_battery_rows(timestamps, actual)
    metric_rows: list[dict[str, Any]] = [no_battery_aggregate]
    daily_parts: list[pd.DataFrame] = [daily_no_battery]
    audit_parts: list[pd.DataFrame] = []
    dispatches: dict[tuple[str, str], pd.DataFrame] = {}

    for size in SIZE_ORDER:
        config = configs[size]
        for controller in CONTROLLERS:
            dispatch, daily, audit = run_controller(
                timestamps,
                actual,
                forecasts[controller],
                controller,
                config,
            )
            dispatches[(size, controller)] = dispatch
            daily_parts.append(daily)
            audit_parts.append(audit)
            metric_rows.append(
                {
                    "controller": controller,
                    "battery_size": size,
                    **aggregate_performance(dispatch["realized_grid_load"], daily, config.capacity),
                    "soc_violations": int(audit["soc_violations"].sum()),
                    "power_violations": int(audit["power_violations"].sum()),
                    "simultaneous_charge_discharge_violations": int(audit["simultaneous_charge_discharge_violations"].sum()),
                    "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
                    "solver_failures": int((~audit["solver_success"]).sum()),
                    "oracle_capture_ratio": np.nan,
                }
            )

    daily = pd.concat(daily_parts, ignore_index=True)
    audit = pd.concat(audit_parts, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    no_peak = float(metrics.loc[metrics["controller"].eq("No Battery"), "mean_daily_peak"].iloc[0])
    for size in SIZE_ORDER:
        mask = metrics["battery_size"].eq(size)
        peaks = metrics.loc[mask].set_index("controller")["mean_daily_peak"]
        oracle_peak = float(peaks["Oracle"])
        for controller in CONTROLLERS:
            row_mask = mask & metrics["controller"].eq(controller)
            metrics.loc[row_mask, "oracle_capture_ratio"] = oracle_capture_ratio(
                no_peak,
                float(peaks[controller]),
                oracle_peak,
            )
    return metrics, daily, audit, dispatches


def _forecast_source_comparison(
    historical: pd.DataFrame,
    corrected: pd.DataFrame,
    forecasts: dict[str, np.ndarray],
) -> pd.DataFrame:
    if not historical["timestamp"].equals(corrected["timestamp"]):
        raise AssertionError("Phase 4 and Phase 4.5 Test target timestamps differ")
    if not np.allclose(historical["actual"], corrected["actual"], atol=1e-10, rtol=0.0):
        raise AssertionError("Phase 4 and Phase 4.5 Test actual values differ")

    actual = corrected["actual"].to_numpy(dtype=float)
    rows = [
        {
            "source": "Phase 4 historical",
            **safe_prediction_metrics(actual, historical["prediction"].to_numpy(dtype=float)),
        },
        {
            "source": "Phase 4.5 canonical",
            **safe_prediction_metrics(actual, corrected["prediction"].to_numpy(dtype=float)),
        },
        {
            "source": "Persistence",
            **safe_prediction_metrics(actual, forecasts["Persistence"]),
        },
        {
            "source": "Oracle",
            **safe_prediction_metrics(actual, forecasts["Oracle"]),
        },
    ]
    result = pd.DataFrame(rows)
    result["prediction_changed_vs_phase4"] = [False, True, True, True]
    return result


def _compare_with_historical_phase5(project_root: Path, corrected_metrics: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(project_root / "outputs" / "phase5" / "phase5_metrics.csv")
    metric_columns = [
        "mean_daily_peak",
        "max_peak",
        "mean_peak_reduction",
        "mean_peak_reduction_pct",
        "p95_grid_load",
        "PAR",
        "total_charge",
        "total_discharge",
        "throughput",
        "equivalent_full_cycles",
        "oracle_capture_ratio",
    ]
    merged = corrected_metrics.merge(
        old[["controller", "battery_size", *metric_columns]],
        on=["controller", "battery_size"],
        how="left",
        suffixes=("_phase5_6", "_phase5"),
        validate="one_to_one",
    )
    for column in metric_columns:
        merged[f"delta_{column}"] = merged[f"{column}_phase5_6"] - merged[f"{column}_phase5"]
    return merged


def _assert_correction_is_isolated(comparison: pd.DataFrame) -> None:
    unchanged = comparison.loc[comparison["controller"].isin(["No Battery", "Persistence", "Oracle"])]
    delta_columns = [column for column in comparison.columns if column.startswith("delta_")]
    finite = unchanged[delta_columns].select_dtypes(include=[np.number])
    if not finite.empty and float(np.nanmax(np.abs(finite.to_numpy(dtype=float)))) > 1e-8:
        raise AssertionError("Non-LightGBM Phase 5 results changed; correction is not isolated to forecast lineage")


def run(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    output_dir = project_root / "outputs" / "phase5_6"
    output_dir.mkdir(parents=True, exist_ok=True)

    corrected, lineage = load_canonical_test_forecast(project_root)
    historical = _load_historical_phase4_forecast(project_root)
    raw_series = _load_raw_series(project_root)
    forecasts = _build_forecasts(corrected, raw_series)
    configs, phase5_config = _load_phase5_battery_configs(project_root)

    metrics, daily, audit, dispatches = _aggregate_rows(corrected, forecasts, configs)
    forecast_comparison = _forecast_source_comparison(historical, corrected, forecasts)
    phase5_comparison = _compare_with_historical_phase5(project_root, metrics)
    _assert_correction_is_isolated(phase5_comparison)

    if audit["solver_success"].all() is not True:
        raise AssertionError("At least one Phase 5.6 optimization failed")
    if int(audit[["soc_violations", "power_violations", "simultaneous_charge_discharge_violations"]].to_numpy().sum()) != 0:
        raise AssertionError("Phase 5.6 battery constraint violation")
    if not (audit["initial_soc_error"].abs() <= TOLERANCE).all():
        raise AssertionError("Phase 5.6 initial SOC mismatch")
    if not (audit["terminal_soc_error"].abs() <= TOLERANCE).all():
        raise AssertionError("Phase 5.6 terminal SOC mismatch")

    metrics.to_csv(output_dir / "phase5_6_metrics.csv", index=False, float_format="%.10f")
    daily.to_csv(output_dir / "daily_metrics.csv", index=False, float_format="%.10f")
    audit.to_csv(output_dir / "constraint_audit.csv", index=False, float_format="%.10f")
    forecast_comparison.to_csv(output_dir / "forecast_source_comparison.csv", index=False, float_format="%.10f")
    phase5_comparison.to_csv(output_dir / "comparison_vs_phase5.csv", index=False, float_format="%.10f")
    for controller, filename in (
        ("LightGBM", "dispatch_lightgbm.csv"),
        ("Persistence", "dispatch_persistence.csv"),
        ("Oracle", "dispatch_oracle.csv"),
    ):
        dispatches[("Medium", controller)].to_csv(
            output_dir / filename,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
            float_format="%.10f",
        )

    lightgbm_change = phase5_comparison.loc[phase5_comparison["controller"].eq("LightGBM")].copy()
    summary: dict[str, Any] = {
        "status": "PASS",
        "phase": "Phase 5.6 forecast-lineage repair and downstream regression audit",
        "runtime_seconds": time.perf_counter() - started,
        "finding": "Phase 5 consumed the historical Phase 4 prediction artifact instead of the leakage-audited Phase 4.5 final Test forecast.",
        "resolution": "Phase 4 remains historical; Phase 4.5 final_predictions.csv is the canonical downstream forecast artifact.",
        "lineage": lineage,
        "historical_phase4_prediction_file": HISTORICAL_PHASE4_PREDICTION_RELATIVE_PATH.as_posix(),
        "historical_phase4_prediction_sha256": sha256(project_root / HISTORICAL_PHASE4_PREDICTION_RELATIVE_PATH),
        "battery_assumption_policy": "Reuse the exact saved Phase 5 battery configurations so the audit isolates the forecast-source correction.",
        "phase5_battery_config_source": "outputs/phase5/phase5_config.json",
        "phase5_original_input_prediction_file": phase5_config.get("input_prediction_file"),
        "forecast_source_comparison": forecast_comparison.to_dict(orient="records"),
        "lightgbm_downstream_changes": lightgbm_change.to_dict(orient="records"),
        "invariants": {
            "test_hours": 720,
            "test_days": 30,
            "actual_matches_raw": True,
            "persistence_oracle_no_battery_reproduce_phase5_within_1e_8": True,
            "solver_failures": int((~audit["solver_success"]).sum()),
            "soc_violations": int(audit["soc_violations"].sum()),
            "power_violations": int(audit["power_violations"].sum()),
            "simultaneous_charge_discharge_violations": int(audit["simultaneous_charge_discharge_violations"].sum()),
        },
        "supersession": {
            "historical_phase5": "keep for provenance; do not use its LightGBM result as the final competition result",
            "historical_phase5_5": "keep for provenance; its LightGBM robustness conclusions are conditional on the old Phase 4 forecast source",
            "future_downstream_source": "use src.forecast_artifacts.load_canonical_test_forecast or Phase 5.6 outputs",
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return summary


if __name__ == "__main__":
    run()
