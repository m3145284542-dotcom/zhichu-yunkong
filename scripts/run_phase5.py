"""Run Phase 5: forecast-driven day-ahead battery peak shaving and value audit."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.battery.metrics import (
    aggregate_performance,
    constraint_counts,
    daily_performance,
    oracle_capture_ratio,
)
from src.battery.model import BatteryConfig
from src.battery.optimizer import optimize_day
from src.features.load_features import build_phase4_features
from src.models.train_lgbm import split_by_feature_time


BUILDING = "Hog_office_Rolando"
RANDOM_SEED = 42
TOLERANCE = 1e-6
THROUGHPUT_PENALTY = 1e-6
TEST_START = pd.Timestamp("2017-12-02 00:00:00")
TEST_END = pd.Timestamp("2017-12-31 23:00:00")
TRAIN_START = pd.Timestamp("2016-01-15 00:00:00")
TRAIN_END = pd.Timestamp("2017-10-31 23:00:00")
CONTROLLERS = ("Persistence", "LightGBM", "Oracle")
SIZE_FRACTIONS = {"Small": 0.05, "Medium": 0.10, "Large": 0.20}
DISPLAY_NAMES = {
    "No Battery": "No Battery",
    "Persistence": "Persistence + Battery",
    "LightGBM": "LightGBM + Battery",
    "Oracle": "Perfect Foresight + Battery\n(Oracle / Not Deployable)",
}


def safe_prediction_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    error = prediction - actual
    nonzero = np.abs(actual) > 1e-12
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error**2))),
        "MAPE": float(100.0 * np.mean(np.abs(error[nonzero] / actual[nonzero]))),
    }


def load_inputs(project_root: Path) -> tuple[pd.DataFrame, dict[str, np.ndarray], float, pd.DataFrame]:
    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    prediction_path = project_root / "outputs" / "phase4" / "test_prediction.csv"
    config_path = project_root / "outputs" / "phase4" / "run_config.json"
    for path in (raw_path, prediction_path, config_path):
        if not path.exists():
            raise FileNotFoundError(path)

    phase4_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert phase4_config["building"] == BUILDING
    assert phase4_config["forecast_horizon_hours"] == 24
    assert phase4_config["test_period"]["target_time_start"] == str(TEST_START)
    assert phase4_config["test_period"]["target_time_end"] == str(TEST_END)
    assert phase4_config["test_period"]["samples"] == 720

    raw = pd.read_csv(raw_path, usecols=["timestamp", BUILDING])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="raise")
    raw = raw.sort_values("timestamp")
    assert not raw["timestamp"].duplicated().any()
    raw_series = raw.set_index("timestamp")[BUILDING].astype(float)

    predictions = pd.read_csv(prediction_path)
    required_columns = {"timestamp", "actual", "prediction"}
    if not required_columns.issubset(predictions.columns):
        raise ValueError(f"Phase 4 prediction columns missing: {required_columns - set(predictions.columns)}")
    predictions["timestamp"] = pd.to_datetime(predictions["timestamp"], errors="raise")
    predictions = predictions.sort_values("timestamp").reset_index(drop=True)

    expected_index = pd.date_range(TEST_START, TEST_END, freq="h")
    assert len(predictions) == 720
    assert predictions["timestamp"].equals(pd.Series(expected_index, name="timestamp"))
    assert predictions["timestamp"].diff().dropna().eq(pd.Timedelta("1h")).all()
    assert predictions["timestamp"].dt.normalize().nunique() == 30
    assert predictions.groupby(predictions["timestamp"].dt.normalize()).size().eq(24).all()
    assert predictions[["actual", "prediction"]].notna().all().all()

    actual_from_raw = raw_series.reindex(expected_index)
    assert actual_from_raw.notna().all()
    assert np.allclose(predictions["actual"], actual_from_raw.to_numpy(), atol=1e-10, rtol=0.0)

    # Reconstruct features only to identify the exact Phase 4 train rows; no model is fit.
    phase4_load = raw.rename(columns={BUILDING: "load"})[["timestamp", "load"]]
    phase4_train = split_by_feature_time(build_phase4_features(phase4_load))["train"]
    assert len(phase4_train) == phase4_config["train_period"]["samples"] == 15573
    assert phase4_train["timestamp"].min() == TRAIN_START
    assert phase4_train["timestamp"].max() == TRAIN_END
    assert phase4_train["current_load"].notna().all()
    mean_train_load = float(phase4_train["current_load"].mean())

    persistence_source = expected_index - pd.Timedelta("24h")
    persistence = raw_series.reindex(persistence_source)
    assert persistence.notna().all()
    # For every target day, the entire source day ends before the target day begins.
    target_days = pd.Series(expected_index).dt.normalize().to_numpy()
    assert np.all(persistence_source.to_numpy() < target_days)
    assert np.all(expected_index - persistence_source == pd.Timedelta("24h"))

    forecast_by_controller = {
        "Persistence": persistence.to_numpy(dtype=float),
        "LightGBM": predictions["prediction"].to_numpy(dtype=float),
        "Oracle": predictions["actual"].to_numpy(dtype=float),
    }
    actual = predictions["actual"].to_numpy(dtype=float)
    forecast_metrics = pd.DataFrame(
        [
            {"controller": name, **safe_prediction_metrics(actual, forecast)}
            for name, forecast in forecast_by_controller.items()
        ]
    )
    return predictions, forecast_by_controller, mean_train_load, forecast_metrics


def run_controller(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecast: np.ndarray,
    controller: str,
    config: BatteryConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dispatch_parts: list[pd.DataFrame] = []
    daily_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    dates = timestamps.dt.normalize()
    for date in dates.drop_duplicates():
        mask = dates.eq(date).to_numpy()
        day_timestamp = timestamps.loc[mask].reset_index(drop=True)
        day_actual = actual[mask]
        # This is the only array passed to the optimizer. Actual is used below only after solve.
        day_forecast = forecast[mask]
        result = optimize_day(day_forecast, config)
        realized = day_actual + result.charge - result.discharge
        counts = constraint_counts(result.charge, result.discharge, result.soc, config, TOLERANCE)
        initial_error = float(result.soc[0] - config.initial_soc)
        terminal_error = float(result.soc[-1] - config.terminal_soc)
        performance = daily_performance(day_actual, realized, result.charge, result.discharge)
        daily_rows.append(
            {
                "date": date.date().isoformat(),
                "controller": controller,
                "battery_size": config.name,
                **performance,
                "initial_soc": result.soc[0],
                "initial_soc_error": initial_error,
                "terminal_soc": result.soc[-1],
                "terminal_soc_error": terminal_error,
                "forecast_peak": result.forecast_peak,
                "solver_status": result.solver_status,
            }
        )
        audit_rows.append(
            {
                "date": date.date().isoformat(),
                "controller": controller,
                "battery_size": config.name,
                "solver_success": result.success,
                **counts,
                "initial_soc_error": initial_error,
                "terminal_soc_error": terminal_error,
            }
        )
        dispatch_parts.append(
            pd.DataFrame(
                {
                    "timestamp": day_timestamp,
                    "date": date.date().isoformat(),
                    "controller": controller,
                    "actual_load": day_actual,
                    "forecast_load": day_forecast,
                    "charge": result.charge,
                    "discharge": result.discharge,
                    "soc": result.soc[1:],
                    "soc_start": result.soc[:-1],
                    "soc_end": result.soc[1:],
                    "realized_grid_load": realized,
                    "optimized_forecast_grid_load": result.optimized_forecast_grid_load,
                    "battery_size": config.name,
                    "solver_status": result.solver_status,
                }
            )
        )
    return pd.concat(dispatch_parts, ignore_index=True), pd.DataFrame(daily_rows), pd.DataFrame(audit_rows)


def no_battery_rows(timestamps: pd.Series, actual: np.ndarray) -> tuple[pd.DataFrame, dict[str, object]]:
    rows = []
    dates = timestamps.dt.normalize()
    for date in dates.drop_duplicates():
        mask = dates.eq(date).to_numpy()
        day_actual = actual[mask]
        rows.append(
            {
                "date": date.date().isoformat(),
                "controller": "No Battery",
                "battery_size": "None",
                **daily_performance(day_actual, day_actual, np.zeros(24), np.zeros(24)),
                "initial_soc": np.nan,
                "initial_soc_error": np.nan,
                "terminal_soc": np.nan,
                "terminal_soc_error": np.nan,
                "forecast_peak": np.nan,
                "solver_status": "not_applicable",
            }
        )
    daily = pd.DataFrame(rows)
    aggregate = {
        "controller": "No Battery",
        "battery_size": "None",
        **aggregate_performance(actual, daily, capacity=None),
        "soc_violations": 0,
        "power_violations": 0,
        "simultaneous_charge_discharge_violations": 0,
        "terminal_soc_violations": 0,
        "solver_failures": 0,
        "oracle_capture_ratio": np.nan,
    }
    return daily, aggregate


# Phase 5 orchestration and plotting are defined below.


def select_example_day(daily: pd.DataFrame) -> tuple[str, str]:
    medium = daily.loc[daily["battery_size"].eq("Medium")]
    pivot = medium.pivot(index="date", columns="controller", values="realized_peak")
    advantage = pivot["Persistence"] - pivot["LightGBM"]
    if advantage.max() > TOLERANCE:
        return str(advantage.idxmax()), "maximum LightGBM realized-peak advantage over Persistence"
    no_battery = daily.loc[daily["controller"].eq("No Battery")].set_index("date")["original_peak"]
    distance = (no_battery - no_battery.median()).abs()
    return str(distance.idxmin()), "original daily peak closest to the test-period median"


def make_plots(
    output_dir: Path,
    metrics: pd.DataFrame,
    daily: pd.DataFrame,
    medium_dispatch: dict[str, pd.DataFrame],
    example_date: str,
    configs: dict[str, BatteryConfig],
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {"No Battery": "#7F7F7F", "Persistence": "#F28E2B", "LightGBM": "#4E79A7", "Oracle": "#59A14F"}

    medium_rows = pd.concat(
        [metrics.loc[metrics["controller"].eq("No Battery")], metrics.loc[metrics["battery_size"].eq("Medium")]],
        ignore_index=True,
    ).set_index("controller").loc[["No Battery", "Persistence", "LightGBM", "Oracle"]]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(4)
    values = medium_rows["mean_daily_peak"].to_numpy()
    bars = ax.bar(x, values, color=[colors[name] for name in medium_rows.index])
    ax.set_xticks(x, [DISPLAY_NAMES[name] for name in medium_rows.index])
    ax.set_ylabel("Mean daily realized peak (kW)")
    ax.set_title("Medium Battery: Realized Peak Comparison")
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.set_ylim(0, values.max() * 1.16)
    fig.tight_layout()
    fig.savefig(output_dir / "peak_comparison.png", dpi=200)
    plt.close(fig)

    selected = pd.concat(
        [daily.loc[daily["controller"].eq("No Battery")], daily.loc[daily["battery_size"].eq("Medium")]],
        ignore_index=True,
    )
    pivot = selected.pivot(index="date", columns="controller", values="realized_peak")
    fig, ax = plt.subplots(figsize=(13, 5.8))
    for controller in ("No Battery", "Persistence", "LightGBM", "Oracle"):
        ax.plot(
            pd.to_datetime(pivot.index),
            pivot[controller],
            marker="o",
            markersize=3,
            linewidth=1.5,
            label=DISPLAY_NAMES[controller].replace("\n", " "),
            color=colors[controller],
        )
    ax.set(title="Daily Realized Peaks on Actual Test Load (Medium Battery)", xlabel="Target date", ylabel="Daily realized peak (kW)")
    ax.legend(ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "daily_peak_reduction.png", dpi=200)
    plt.close(fig)

    example = medium_dispatch["LightGBM"].loc[medium_dispatch["LightGBM"]["date"].eq(example_date)].copy()
    hours = example["timestamp"].dt.hour.to_numpy()
    fig, (ax_load, ax_power) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True, gridspec_kw={"height_ratios": [2.1, 1]})
    ax_load.plot(hours, example["actual_load"], label="Actual Load", color="#222222", linewidth=2)
    ax_load.plot(hours, example["forecast_load"], label="LightGBM Forecast", color=colors["LightGBM"], linestyle="--", linewidth=1.7)
    ax_load.plot(hours, example["realized_grid_load"], label="Realized Grid Load", color="#E15759", linewidth=1.8)
    ax_load.set(title=f"Representative Dispatch: {example_date} (Medium Battery)", ylabel="Load / grid power (kW)")
    ax_load.legend(ncol=3)
    ax_power.bar(hours, example["charge"], label="Charge", color="#76B7B2", alpha=0.85)
    ax_power.bar(hours, -example["discharge"], label="Discharge", color="#EDC948", alpha=0.9)
    ax_power.axhline(0, color="black", linewidth=0.8)
    ax_power.set(xlabel="Hour of day", ylabel="Battery power (kW)")
    ax_power.set_xticks(np.arange(0, 24, 2))
    ax_power.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / "example_day_dispatch.png", dpi=200)
    plt.close(fig)

    config = configs["Medium"]
    soc = np.r_[example["soc_start"].iloc[0], example["soc_end"].to_numpy()]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.step(np.arange(25), soc, where="post", label="SOC", color="#4E79A7", linewidth=2)
    ax.axhline(config.soc_min, color="#E15759", linestyle="--", label=f"SOC min ({config.soc_min_fraction:.0%})")
    ax.axhline(config.soc_max, color="#59A14F", linestyle="--", label=f"SOC max ({config.soc_max_fraction:.0%})")
    ax.set(title=f"Battery SOC: {example_date} (Medium Battery)", xlabel="Hour boundary", ylabel="Stored energy (kWh)", xlim=(0, 24))
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "example_day_soc.png", dpi=200)
    plt.close(fig)

    sensitivity = metrics.loc[metrics["battery_size"].isin(SIZE_FRACTIONS) & metrics["controller"].isin(CONTROLLERS)]
    sensitivity_pivot = sensitivity.pivot(index="battery_size", columns="controller", values="mean_daily_peak").reindex(SIZE_FRACTIONS)
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    x = np.arange(3)
    for controller, marker in (("Persistence", "o"), ("LightGBM", "s"), ("Oracle", "^")):
        ax.plot(
            x,
            sensitivity_pivot[controller],
            marker=marker,
            markersize=7,
            linewidth=2,
            color=colors[controller],
            label=DISPLAY_NAMES[controller].replace("\n", " "),
        )
    ax.set_xticks(x, sensitivity_pivot.index)
    ax.set(title="Battery Size Sensitivity", xlabel="Battery size", ylabel="Mean daily realized peak (kW)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "battery_size_sensitivity.png", dpi=200)
    plt.close(fig)


def run(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    output_dir = project_root / "outputs" / "phase5"
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions, forecasts, mean_train_load, forecast_metrics = load_inputs(project_root)
    timestamps = predictions["timestamp"]
    actual = predictions["actual"].to_numpy(dtype=float)
    configs = {
        name: BatteryConfig.from_mean_train_load(name, mean_train_load, fraction, THROUGHPUT_PENALTY)
        for name, fraction in SIZE_FRACTIONS.items()
    }

    daily_no_battery, no_battery_aggregate = no_battery_rows(timestamps, actual)
    daily_parts = [daily_no_battery]
    metric_rows: list[dict[str, object]] = [no_battery_aggregate]
    audit_parts: list[pd.DataFrame] = []
    all_dispatch: dict[tuple[str, str], pd.DataFrame] = {}

    # Medium is the primary experiment. Small/Large are run only afterwards.
    for size in ("Medium", "Small", "Large"):
        config = configs[size]
        for controller in CONTROLLERS:
            dispatch, daily, audit = run_controller(timestamps, actual, forecasts[controller], controller, config)
            all_dispatch[(size, controller)] = dispatch
            daily_parts.append(daily)
            audit_parts.append(audit)
            aggregate = aggregate_performance(dispatch["realized_grid_load"], daily, config.capacity)
            metric_rows.append(
                {
                    "controller": controller,
                    "battery_size": size,
                    **aggregate,
                    "soc_violations": int(audit["soc_violations"].sum()),
                    "power_violations": int(audit["power_violations"].sum()),
                    "simultaneous_charge_discharge_violations": int(audit["simultaneous_charge_discharge_violations"].sum()),
                    "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
                    "solver_failures": int((~audit["solver_success"]).sum()),
                    "oracle_capture_ratio": np.nan,
                }
            )

    daily_metrics = pd.concat(daily_parts, ignore_index=True)
    constraint_audit = pd.concat(audit_parts, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    no_peak = float(metrics.loc[metrics["controller"].eq("No Battery"), "mean_daily_peak"].iloc[0])
    decision_value: dict[str, dict[str, float]] = {}
    for size in SIZE_FRACTIONS:
        size_mask = metrics["battery_size"].eq(size)
        peaks = metrics.loc[size_mask].set_index("controller")["mean_daily_peak"]
        oracle_peak = float(peaks["Oracle"])
        for controller in CONTROLLERS:
            row_mask = size_mask & metrics["controller"].eq(controller)
            metrics.loc[row_mask, "oracle_capture_ratio"] = oracle_capture_ratio(no_peak, float(peaks[controller]), oracle_peak)
        persistence_improvement = float(peaks["Persistence"] - peaks["LightGBM"])
        decision_value[size] = {
            "oracle_gain": no_peak - oracle_peak,
            "persistence_oracle_capture": oracle_capture_ratio(no_peak, float(peaks["Persistence"]), oracle_peak),
            "lightgbm_oracle_capture": oracle_capture_ratio(no_peak, float(peaks["LightGBM"]), oracle_peak),
            "lightgbm_absolute_improvement_over_persistence": persistence_improvement,
            "lightgbm_relative_improvement_over_persistence_pct": 100.0 * persistence_improvement / float(peaks["Persistence"]),
            "lightgbm_gap_to_oracle": float(peaks["LightGBM"] - oracle_peak),
        }

    daily_metrics.to_csv(output_dir / "daily_metrics.csv", index=False, float_format="%.10f")
    metrics.to_csv(output_dir / "phase5_metrics.csv", index=False, float_format="%.10f")
    constraint_audit.to_csv(output_dir / "constraint_audit.csv", index=False, float_format="%.10f")
    forecast_metrics.to_csv(output_dir / "forecast_metrics.csv", index=False, float_format="%.10f")
    for controller, filename in (
        ("LightGBM", "dispatch_lightgbm.csv"),
        ("Persistence", "dispatch_persistence.csv"),
        ("Oracle", "dispatch_oracle.csv"),
    ):
        all_dispatch[("Medium", controller)].to_csv(
            output_dir / filename,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
            float_format="%.10f",
        )
    sensitivity = metrics.loc[metrics["battery_size"].isin(SIZE_FRACTIONS)].copy()
    sensitivity.to_csv(output_dir / "battery_size_sensitivity.csv", index=False, float_format="%.10f")

    example_date, example_rule = select_example_day(daily_metrics)
    make_plots(
        output_dir,
        metrics,
        daily_metrics,
        {name: all_dispatch[("Medium", name)] for name in CONTROLLERS},
        example_date,
        configs,
    )

    config_payload = {
        "building": BUILDING,
        "random_seed": RANDOM_SEED,
        "input_prediction_file": "outputs/phase4/test_prediction.csv",
        "prediction_columns": ["timestamp", "actual", "prediction", "error", "abs_error"],
        "prediction_timestamp_definition": "target timestamp t+24h",
        "test_target_period": {"start": str(TEST_START), "end": str(TEST_END), "hours": 720, "days": 30},
        "train_load_period_for_sizing": {
            "start": str(TRAIN_START),
            "end": str(TRAIN_END),
            "samples": 15573,
            "selection_rule": "mean current_load across the exact Phase 4 train feature rows; no imputation",
            "mean_hourly_load": mean_train_load,
            "mean_daily_energy": 24.0 * mean_train_load,
        },
        "units": {
            "load_charge_discharge": "kWh per one-hour interval; numerically equal to average kW",
            "soc_capacity": "kWh",
        },
        "solver": "scipy.optimize.milp with HiGHS backend",
        "objective": "min peak + 1e-6 * sum(charge + discharge)",
        "equivalent_full_cycles_definition": "total discharge energy / nominal capacity",
        "battery_configs": {
            name: vars(config)
            | {
                "soc_min": config.soc_min,
                "soc_max": config.soc_max,
                "initial_soc": config.initial_soc,
                "terminal_soc": config.terminal_soc,
                "round_trip_efficiency": config.round_trip_efficiency,
            }
            for name, config in configs.items()
        },
        "example_day": example_date,
        "example_day_selection_rule": example_rule,
    }
    (output_dir / "phase5_config.json").write_text(
        json.dumps(config_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    required_outputs = [
        "phase5_metrics.csv",
        "daily_metrics.csv",
        "dispatch_lightgbm.csv",
        "dispatch_persistence.csv",
        "dispatch_oracle.csv",
        "battery_size_sensitivity.csv",
        "peak_comparison.png",
        "daily_peak_reduction.png",
        "example_day_dispatch.png",
        "example_day_soc.png",
        "battery_size_sensitivity.png",
        "phase5_config.json",
        "constraint_audit.csv",
        "forecast_metrics.csv",
    ]
    # End-to-end acceptance checks.
    assert len(daily_no_battery) == 30
    assert len(daily_metrics) == 30 * 10
    assert len(constraint_audit) == 30 * 3 * 3
    assert constraint_audit["solver_success"].all()
    assert constraint_audit[["soc_violations", "power_violations", "simultaneous_charge_discharge_violations"]].to_numpy().sum() == 0
    assert (constraint_audit["initial_soc_error"].abs() <= TOLERANCE).all()
    assert (constraint_audit["terminal_soc_error"].abs() <= TOLERANCE).all()
    for controller in CONTROLLERS:
        dispatch = all_dispatch[("Medium", controller)]
        assert len(dispatch) == 720
        assert dispatch["timestamp"].equals(timestamps)
        assert dispatch.notna().all().all()
    assert all((output_dir / name).exists() and (output_dir / name).stat().st_size > 0 for name in required_outputs)

    summary = {
        "status": "PASS",
        "runtime_seconds": time.perf_counter() - started,
        "forecast_metrics": forecast_metrics.to_dict(orient="records"),
        "decision_value": decision_value,
        "example_day": {"date": example_date, "selection_rule": example_rule},
        "constraint_totals": {
            "solver_failures": int((~constraint_audit["solver_success"]).sum()),
            "soc_violations": int(constraint_audit["soc_violations"].sum()),
            "power_violations": int(constraint_audit["power_violations"].sum()),
            "simultaneous_charge_discharge_violations": int(constraint_audit["simultaneous_charge_discharge_violations"].sum()),
            "initial_soc_violations": int((constraint_audit["initial_soc_error"].abs() > TOLERANCE).sum()),
            "terminal_soc_violations": int((constraint_audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
        },
        "required_outputs": required_outputs,
    }
    (output_dir / "phase5_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert (output_dir / "phase5_summary.json").stat().st_size > 0
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    run()
