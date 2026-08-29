"""Phase 5.5 robustness, sensitivity, and forecast-error propagation analysis.

The module consumes the frozen Phase 4 test predictions and directly reuses the
Phase 5 daily controller.  It never fits a forecasting model and never writes to
the Phase 4 or Phase 5 output directories.
"""

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
from scipy.stats import pearsonr, spearmanr

from scripts.run_phase5 import (
    CONTROLLERS,
    THROUGHPUT_PENALTY,
    load_inputs,
    no_battery_rows,
    run_controller,
    safe_prediction_metrics,
)
from src.battery.model import BatteryConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_START = pd.Timestamp("2017-12-02 00:00:00")
TEST_END = pd.Timestamp("2017-12-31 23:00:00")
BOOTSTRAP_SEED = 42
BOOTSTRAP_RESAMPLES = 10_000
TOLERANCE = 1e-6
CAPACITY_MULTIPLIERS = (0.50, 0.75, 1.00, 1.25, 1.50)
POWER_MULTIPLIERS = (0.50, 0.75, 1.00, 1.25, 1.50)
ROUND_TRIP_EFFICIENCIES = (0.85, 0.90, 0.95)
FORECAST_BIASES = (-0.10, -0.05, 0.00, 0.05, 0.10)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_output_hashes(project_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for phase in ("phase4", "phase5"):
        directory = project_root / "outputs" / phase
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            result[path.relative_to(project_root).as_posix()] = sha256(path)
    return result


def load_baseline_config(project_root: Path) -> tuple[BatteryConfig, dict[str, Any]]:
    phase5_config = json.loads(
        (project_root / "outputs" / "phase5" / "phase5_config.json").read_text(encoding="utf-8")
    )
    payload = phase5_config["battery_configs"]["Medium"]
    allowed = {field.name for field in fields(BatteryConfig)}
    config = BatteryConfig(**{key: value for key, value in payload.items() if key in allowed})
    return config, payload


def scaled_config(
    baseline: BatteryConfig,
    *,
    name: str,
    capacity_multiplier: float = 1.0,
    power_multiplier: float = 1.0,
    round_trip_efficiency: float | None = None,
) -> BatteryConfig:
    eta = baseline.eta_charge if round_trip_efficiency is None else math.sqrt(round_trip_efficiency)
    eta_discharge = baseline.eta_discharge if round_trip_efficiency is None else eta
    return BatteryConfig(
        name=name,
        capacity=baseline.capacity * capacity_multiplier,
        max_charge_power=baseline.max_charge_power * power_multiplier,
        max_discharge_power=baseline.max_discharge_power * power_multiplier,
        soc_min_fraction=baseline.soc_min_fraction,
        soc_max_fraction=baseline.soc_max_fraction,
        initial_soc_fraction=baseline.initial_soc_fraction,
        terminal_soc_fraction=baseline.terminal_soc_fraction,
        eta_charge=eta,
        eta_discharge=eta_discharge,
        throughput_penalty=baseline.throughput_penalty,
    )


def paired_bootstrap(
    paired_difference: np.ndarray, *, seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES
) -> dict[str, float | int]:
    values = np.asarray(paired_difference, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("paired_difference must be a finite non-empty vector")
    rng = np.random.default_rng(seed)
    sample_indices = rng.integers(0, values.size, size=(resamples, values.size))
    bootstrap_means = values[sample_indices].mean(axis=1)
    low, high = np.percentile(bootstrap_means, [2.5, 97.5])
    return {
        "metric": "Persistence decision regret - LightGBM decision regret (kW)",
        "resampling_unit": "day",
        "days": int(values.size),
        "seed": int(seed),
        "resamples": int(resamples),
        "mean_paired_difference": float(values.mean()),
        "median_paired_difference": float(np.median(values)),
        "bootstrap_95_ci_lower": float(low),
        "bootstrap_95_ci_upper": float(high),
        "lightgbm_win_days": int(np.sum(values > TOLERANCE)),
        "persistence_win_days": int(np.sum(values < -TOLERANCE)),
        "tie_days": int(np.sum(np.abs(values) <= TOLERANCE)),
    }


def _enrich_audit(audit: pd.DataFrame, experiment: str, setting: str) -> pd.DataFrame:
    result = audit.copy()
    result.insert(0, "experiment", experiment)
    result.insert(1, "setting", setting)
    result["initial_soc_violations"] = (result["initial_soc_error"].abs() > TOLERANCE).astype(int)
    result["terminal_soc_violations"] = (result["terminal_soc_error"].abs() > TOLERANCE).astype(int)
    return result


def run_setting(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecasts: dict[str, np.ndarray],
    config: BatteryConfig,
    *,
    experiment: str,
    setting: str,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    dispatches: dict[str, pd.DataFrame] = {}
    daily_parts: list[pd.DataFrame] = []
    audits: list[pd.DataFrame] = []
    for controller in CONTROLLERS:
        dispatch, daily, audit = run_controller(
            timestamps, actual, forecasts[controller], controller, config
        )
        dispatches[controller] = dispatch
        daily_parts.append(daily)
        audits.append(_enrich_audit(audit, experiment, setting))
    return dispatches, pd.concat(daily_parts, ignore_index=True), pd.concat(audits, ignore_index=True)


def _maximum_numeric_difference(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> float:
    merged = left.merge(right, on=keys, suffixes=("_new", "_saved"), validate="one_to_one")
    differences: list[float] = []
    for column in left.select_dtypes(include=[np.number]).columns:
        if column in keys or f"{column}_saved" not in merged:
            continue
        differences.append(float(np.max(np.abs(merged[f"{column}_new"] - merged[f"{column}_saved"]))))
    return max(differences, default=0.0)


def reproduce_phase5_baseline(
    project_root: Path,
    baseline_daily: pd.DataFrame,
    baseline_dispatch: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    saved_daily = pd.read_csv(project_root / "outputs" / "phase5" / "daily_metrics.csv")
    saved_daily = saved_daily.loc[saved_daily["battery_size"].eq("Medium")].copy()
    daily_diff = _maximum_numeric_difference(
        baseline_daily, saved_daily, ["date", "controller", "battery_size"]
    )
    dispatch_differences: dict[str, float] = {}
    for controller in CONTROLLERS:
        saved = pd.read_csv(
            project_root / "outputs" / "phase5" / f"dispatch_{controller.lower()}.csv"
        )
        new = baseline_dispatch[controller].copy()
        saved["timestamp"] = pd.to_datetime(saved["timestamp"])
        dispatch_differences[controller] = _maximum_numeric_difference(
            new, saved, ["timestamp", "date", "controller", "battery_size"]
        )
    maximum = max([daily_diff, *dispatch_differences.values()])
    return {
        "passed": bool(maximum <= 1e-8),
        "tolerance": 1e-8,
        "daily_metrics_maximum_absolute_difference": daily_diff,
        "dispatch_maximum_absolute_difference": dispatch_differences,
        "maximum_absolute_difference": maximum,
    }


def build_daily_diagnostics(
    predictions: pd.DataFrame,
    forecasts: dict[str, np.ndarray],
    baseline_daily: pd.DataFrame,
    baseline_dispatch: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dates = predictions["timestamp"].dt.normalize()
    actual = predictions["actual"].to_numpy(dtype=float)
    daily_index = baseline_daily.set_index(["date", "controller"])
    for date in dates.drop_duplicates():
        date_text = date.date().isoformat()
        mask = dates.eq(date).to_numpy()
        row: dict[str, Any] = {"date": date_text}
        for controller, prefix in (("LightGBM", "lgbm"), ("Persistence", "persistence"), ("Oracle", "oracle")):
            forecast_metrics = safe_prediction_metrics(actual[mask], forecasts[controller][mask])
            performance = daily_index.loc[(date_text, controller)]
            dispatch = baseline_dispatch[controller].loc[
                baseline_dispatch[controller]["date"].eq(date_text)
            ]
            row.update(
                {
                    f"{prefix}_forecast_mae": forecast_metrics["MAE"],
                    f"{prefix}_forecast_rmse": forecast_metrics["RMSE"],
                    f"{prefix}_forecast_mape": forecast_metrics["MAPE"],
                    f"{prefix}_realized_peak": float(performance["realized_peak"]),
                    f"{prefix}_peak_reduction": float(performance["peak_reduction"]),
                    f"{prefix}_peak_reduction_pct": float(performance["peak_reduction_pct"]),
                    f"{prefix}_charge_energy": float(performance["total_charge"]),
                    f"{prefix}_discharge_energy": float(performance["total_discharge"]),
                    f"{prefix}_soc_min": float(dispatch["soc_end"].min()),
                    f"{prefix}_soc_max": float(dispatch["soc_end"].max()),
                    f"{prefix}_objective_value": float(performance["forecast_peak"])
                    + THROUGHPUT_PENALTY * float(performance["throughput"]),
                }
            )
        row["baseline_peak"] = float(actual[mask].max())
        for prefix in ("lgbm", "persistence"):
            row[f"{prefix}_decision_regret"] = (
                row[f"{prefix}_realized_peak"] - row["oracle_realized_peak"]
            )
            row[f"{prefix}_peak_reduction_regret"] = (
                row["oracle_peak_reduction"] - row[f"{prefix}_peak_reduction"]
            )
        rows.append(row)
    result = pd.DataFrame(rows)
    aliases = {
        "lgbm_mae": result["lgbm_forecast_mae"],
        "lgbm_rmse": result["lgbm_forecast_rmse"],
        "persistence_mae": result["persistence_forecast_mae"],
        "persistence_rmse": result["persistence_forecast_rmse"],
        "persistence_peak_reduction": result["persistence_peak_reduction"],
        "lgbm_peak_reduction": result["lgbm_peak_reduction"],
        "oracle_peak_reduction": result["oracle_peak_reduction"],
    }
    for name, values in aliases.items():
        if name not in result:
            result[name] = values
    return result


def build_regret_table(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in daily.iterrows():
        for controller, prefix in (("LightGBM", "lgbm"), ("Persistence", "persistence")):
            rows.append(
                {
                    "date": row["date"],
                    "controller": controller,
                    "forecast_mae": row[f"{prefix}_forecast_mae"],
                    "forecast_rmse": row[f"{prefix}_forecast_rmse"],
                    "forecast_mape": row[f"{prefix}_forecast_mape"],
                    "realized_peak": row[f"{prefix}_realized_peak"],
                    "oracle_realized_peak": row["oracle_realized_peak"],
                    "decision_regret": row[f"{prefix}_decision_regret"],
                    "peak_reduction_regret": row[f"{prefix}_peak_reduction_regret"],
                }
            )
    return pd.DataFrame(rows)


def calculate_correlations(regret: pd.DataFrame) -> dict[str, dict[str, dict[str, float]]]:
    result: dict[str, dict[str, dict[str, float]]] = {}
    for controller in ("LightGBM", "Persistence"):
        group = regret.loc[regret["controller"].eq(controller)]
        result[controller] = {}
        for error_metric in ("forecast_mae", "forecast_rmse"):
            pearson = pearsonr(group[error_metric], group["decision_regret"])
            spearman = spearmanr(group[error_metric], group["decision_regret"])
            result[controller][error_metric] = {
                "pearson_correlation": float(pearson.statistic),
                "pearson_pvalue_descriptive_only": float(pearson.pvalue),
                "spearman_correlation": float(spearman.statistic),
                "spearman_pvalue_descriptive_only": float(spearman.pvalue),
                "days": int(len(group)),
            }
    return result


def build_consistency_table(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily[["date"]].copy()
    result["forecast_mae_improvement"] = daily["persistence_forecast_mae"] - daily["lgbm_forecast_mae"]
    result["decision_regret_improvement"] = daily["persistence_decision_regret"] - daily["lgbm_decision_regret"]
    result["lgbm_forecast_better"] = result["forecast_mae_improvement"] > TOLERANCE
    result["lgbm_decision_better"] = result["decision_regret_improvement"] > TOLERANCE
    result["category"] = np.select(
        [
            result["lgbm_forecast_better"] & result["lgbm_decision_better"],
            result["lgbm_forecast_better"] & ~result["lgbm_decision_better"],
            ~result["lgbm_forecast_better"] & result["lgbm_decision_better"],
        ],
        [
            "forecast better / decision better",
            "forecast better / decision worse",
            "forecast worse / decision better",
        ],
        default="forecast worse / decision worse",
    )
    return result


def summarize_setting(daily: pd.DataFrame, multiplier: float, config: BatteryConfig) -> pd.DataFrame:
    oracle = daily.loc[daily["controller"].eq("Oracle"), ["date", "realized_peak"]].rename(
        columns={"realized_peak": "oracle_realized_peak"}
    )
    merged = daily.merge(oracle, on="date", validate="many_to_one")
    merged["decision_regret"] = merged["realized_peak"] - merged["oracle_realized_peak"]
    rows: list[dict[str, Any]] = []
    for controller in CONTROLLERS:
        group = merged.loc[merged["controller"].eq(controller)]
        rows.append(
            {
                "multiplier": multiplier,
                "is_phase5_baseline": bool(np.isclose(multiplier, 1.0)),
                "controller": controller,
                "capacity_kwh": config.capacity,
                "max_charge_power_kw": config.max_charge_power,
                "max_discharge_power_kw": config.max_discharge_power,
                "round_trip_efficiency": config.round_trip_efficiency,
                "mean_realized_peak_kw": float(group["realized_peak"].mean()),
                "max_realized_peak_kw": float(group["realized_peak"].max()),
                "mean_peak_reduction_kw": float(group["peak_reduction"].mean()),
                "mean_peak_reduction_pct": float(group["peak_reduction_pct"].mean()),
                "mean_decision_regret_kw": float(group["decision_regret"].mean()),
                "total_charge_energy_kwh": float(group["total_charge"].sum()),
                "total_discharge_energy_kwh": float(group["total_discharge"].sum()),
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecasts: dict[str, np.ndarray],
    baseline: BatteryConfig,
    *,
    experiment: str,
    values: tuple[float, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: list[pd.DataFrame] = []
    audits: list[pd.DataFrame] = []
    for value in values:
        if experiment == "capacity":
            config = scaled_config(baseline, name=f"capacity_{value:.2f}x", capacity_multiplier=value)
            multiplier = value
        elif experiment == "power":
            config = scaled_config(baseline, name=f"power_{value:.2f}x", power_multiplier=value)
            multiplier = value
        elif experiment == "efficiency":
            config = scaled_config(baseline, name=f"rte_{value:.2f}", round_trip_efficiency=value)
            multiplier = value / baseline.round_trip_efficiency
        else:
            raise ValueError(experiment)
        _, daily, audit = run_setting(
            timestamps,
            actual,
            forecasts,
            config,
            experiment=f"{experiment}_sensitivity",
            setting=f"{value:.4f}",
        )
        summary = summarize_setting(daily, multiplier, config)
        if experiment == "efficiency":
            summary.insert(0, "round_trip_efficiency_setting", value)
        summaries.append(summary)
        audits.append(audit)
    result = pd.concat(summaries, ignore_index=True)
    baseline_reference = result.loc[
        np.isclose(result["multiplier"], 1.0), ["controller", "mean_realized_peak_kw"]
    ].set_index("controller")["mean_realized_peak_kw"]
    result["baseline_max_abs_difference"] = np.where(
        np.isclose(result["multiplier"], 1.0),
        np.abs(result["mean_realized_peak_kw"] - result["controller"].map(baseline_reference)),
        0.0,
    )
    return result, pd.concat(audits, ignore_index=True)


def run_bias_stress(
    timestamps: pd.Series,
    actual: np.ndarray,
    lgbm_forecast: np.ndarray,
    baseline: BatteryConfig,
    oracle_daily: pd.DataFrame,
    baseline_lgbm_daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    audits: list[pd.DataFrame] = []
    oracle_peaks = oracle_daily.set_index("date")["realized_peak"]
    baseline_mean_peak = float(baseline_lgbm_daily["realized_peak"].mean())
    for bias in FORECAST_BIASES:
        stressed = np.maximum(lgbm_forecast * (1.0 + bias), 0.0)
        dispatch, daily, audit = run_controller(
            timestamps, actual, stressed, f"LightGBM bias {bias:+.0%}", baseline
        )
        audits.append(_enrich_audit(audit, "forecast_bias_stress", f"{bias:+.2f}"))
        daily = daily.copy()
        daily["oracle_realized_peak"] = daily["date"].map(oracle_peaks)
        daily["decision_regret"] = daily["realized_peak"] - daily["oracle_realized_peak"]
        mean_peak = float(daily["realized_peak"].mean())
        rows.append(
            {
                "bias": bias,
                "bias_percent": 100.0 * bias,
                "prediction_clipped_at_zero": True,
                "clipped_value_count": int(np.sum(lgbm_forecast * (1.0 + bias) < 0.0)),
                "mean_realized_peak_kw": mean_peak,
                "max_realized_peak_kw": float(dispatch["realized_grid_load"].max()),
                "mean_peak_reduction_kw": float(daily["peak_reduction"].mean()),
                "mean_peak_reduction_pct": float(daily["peak_reduction_pct"].mean()),
                "mean_decision_regret_kw": float(daily["decision_regret"].mean()),
                "total_charge_energy_kwh": float(daily["total_charge"].sum()),
                "total_discharge_energy_kwh": float(daily["total_discharge"].sum()),
                "baseline_max_abs_difference": abs(mean_peak - baseline_mean_peak) if np.isclose(bias, 0.0) else 0.0,
            }
        )
    return pd.DataFrame(rows), pd.concat(audits, ignore_index=True)


def _plot_regret(regret: pd.DataFrame, path: Path) -> None:
    colors = {"LightGBM": "#4E79A7", "Persistence": "#F28E2B"}
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
    for ax, metric, label in zip(axes, ("forecast_mae", "forecast_rmse"), ("Daily MAE (kW)", "Daily RMSE (kW)")):
        for controller in ("LightGBM", "Persistence"):
            group = regret.loc[regret["controller"].eq(controller)]
            ax.scatter(group[metric], group["decision_regret"], s=38, alpha=0.78, color=colors[controller], label=controller)
        ax.axhline(0.0, color="#777777", linewidth=0.8)
        ax.set(xlabel=label, ylabel="Decision regret vs Oracle (kW)")
    axes[0].legend()
    fig.suptitle("Forecast Error and Realized Peak-Shaving Decision Regret (30 Days)")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_consistency(consistency: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.8, 6.2))
    ax.scatter(consistency["forecast_mae_improvement"], consistency["decision_regret_improvement"], color="#4E79A7", s=42, alpha=0.82)
    ax.axhline(0.0, color="#555555", linewidth=1)
    ax.axvline(0.0, color="#555555", linewidth=1)
    ax.set(
        title="Does Forecast MAE Improvement Translate to Decision Improvement?",
        xlabel="Persistence MAE − LightGBM MAE (kW; positive favors LightGBM)",
        ylabel="Persistence regret − LightGBM regret (kW; positive favors LightGBM)",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_sensitivity(frame: pd.DataFrame, path: Path, title: str, xlabel: str, xcolumn: str = "multiplier") -> None:
    colors = {"LightGBM": "#4E79A7", "Persistence": "#F28E2B", "Oracle": "#59A14F"}
    fig, ax = plt.subplots(figsize=(8.5, 5.3))
    for controller, marker in (("Persistence", "o"), ("LightGBM", "s"), ("Oracle", "^")):
        group = frame.loc[frame["controller"].eq(controller)].sort_values(xcolumn)
        ax.plot(group[xcolumn], group["mean_realized_peak_kw"], marker=marker, linewidth=2, color=colors[controller], label=controller)
    baseline_x = 1.0 if xcolumn == "multiplier" else 0.90
    ax.axvline(baseline_x, color="#777777", linestyle="--", linewidth=1.2, label="Phase 5 baseline")
    ax.set(title=title, xlabel=xlabel, ylabel="Mean daily realized peak (kW)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_bias(frame: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.plot(frame["bias_percent"], frame["mean_realized_peak_kw"], marker="o", linewidth=2, color="#4E79A7", label="LightGBM-driven")
    ax.axvline(0.0, color="#777777", linestyle="--", linewidth=1.2, label="Original forecast")
    ax.set(title="Robustness to Synthetic Systematic Forecast Bias", xlabel="Multiplicative forecast bias (%)", ylabel="Mean daily realized peak (kW)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def select_case_studies(daily: pd.DataFrame) -> list[dict[str, str]]:
    candidates = [
        (daily.sort_values("lgbm_decision_regret", ascending=False), "largest LightGBM decision regret"),
        (daily.assign(improvement=daily["persistence_decision_regret"] - daily["lgbm_decision_regret"]).sort_values("improvement", ascending=False), "largest LightGBM improvement over Persistence"),
        (daily.assign(improvement=daily["persistence_decision_regret"] - daily["lgbm_decision_regret"]).sort_values("improvement"), "largest LightGBM deterioration versus Persistence"),
    ]
    selected: list[dict[str, str]] = []
    used: set[str] = set()
    for frame, reason in candidates:
        for date in frame["date"].astype(str):
            if date not in used:
                selected.append({"date": date, "reason": reason})
                used.add(date)
                break
        if len(selected) == 3:
            break
    return selected


def build_anomalous_date_rankings(daily: pd.DataFrame) -> pd.DataFrame:
    improvement = daily["persistence_decision_regret"] - daily["lgbm_decision_regret"]
    specifications = (
        ("largest LightGBM decision regret", daily["lgbm_decision_regret"], False),
        ("largest Persistence decision regret", daily["persistence_decision_regret"], False),
        ("largest LightGBM improvement over Persistence", improvement, False),
        ("largest LightGBM deterioration versus Persistence", improvement, True),
    )
    rows: list[dict[str, Any]] = []
    for category, values, ascending in specifications:
        order = values.sort_values(ascending=ascending).index[:3]
        for rank, index in enumerate(order, start=1):
            rows.append(
                {
                    "category": category,
                    "rank": rank,
                    "date": daily.loc[index, "date"],
                    "lgbm_forecast_mae": daily.loc[index, "lgbm_forecast_mae"],
                    "persistence_forecast_mae": daily.loc[index, "persistence_forecast_mae"],
                    "lgbm_decision_regret": daily.loc[index, "lgbm_decision_regret"],
                    "persistence_decision_regret": daily.loc[index, "persistence_decision_regret"],
                    "decision_regret_improvement": improvement.loc[index],
                }
            )
    return pd.DataFrame(rows)


def _plot_case_study(
    date: str,
    reason: str,
    dispatches: dict[str, pd.DataFrame],
    path: Path,
) -> None:
    groups = {name: frame.loc[frame["date"].eq(date)] for name, frame in dispatches.items()}
    hours = groups["LightGBM"]["timestamp"].dt.hour
    fig, (ax_load, ax_power) = plt.subplots(2, 1, figsize=(10.8, 7.2), sharex=True, gridspec_kw={"height_ratios": [2.1, 1]})
    actual = groups["LightGBM"]["actual_load"]
    ax_load.plot(hours, actual, color="#222222", linewidth=2.2, label="Actual / No Battery")
    ax_load.plot(hours, groups["LightGBM"]["forecast_load"], color="#4E79A7", linestyle="--", linewidth=1.3, label="LightGBM forecast")
    ax_load.plot(hours, groups["Persistence"]["forecast_load"], color="#F28E2B", linestyle=":", linewidth=1.5, label="Persistence forecast")
    for controller, color in (("LightGBM", "#4E79A7"), ("Persistence", "#F28E2B"), ("Oracle", "#59A14F")):
        ax_load.plot(hours, groups[controller]["realized_grid_load"], color=color, linewidth=1.8, label=f"{controller} realized grid")
    ax_load.set(title=f"Case Study {date}: {reason}", ylabel="Load / grid power (kW)")
    ax_load.legend(ncol=3, fontsize=8)
    for controller, color in (("LightGBM", "#4E79A7"), ("Persistence", "#F28E2B")):
        net = groups[controller]["charge"] - groups[controller]["discharge"]
        ax_power.step(hours, net, where="mid", color=color, linewidth=1.8, label=f"{controller} charge (+) / discharge (−)")
    ax_power.axhline(0.0, color="#555555", linewidth=0.8)
    ax_power.set(xlabel="Hour of day", ylabel="Battery power (kW)")
    ax_power.set_xticks(np.arange(0, 24, 2))
    ax_power.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _category_counts(consistency: pd.DataFrame) -> dict[str, int]:
    counts = consistency["category"].value_counts()
    categories = (
        "forecast better / decision better",
        "forecast better / decision worse",
        "forecast worse / decision better",
        "forecast worse / decision worse",
    )
    return {category: int(counts.get(category, 0)) for category in categories}


def _assert_finite_csvs(output_dir: Path) -> None:
    for path in output_dir.glob("*.csv"):
        frame = pd.read_csv(path)
        numeric = frame.select_dtypes(include=[np.number]).to_numpy()
        if not np.isfinite(numeric).all():
            raise AssertionError(f"Non-finite numeric value in {path.name}")


def run(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    output_dir = project_root / "outputs" / "phase5_5"
    figure_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    hashes_before = frozen_output_hashes(project_root)
    predictions, forecasts, _, _ = load_inputs(project_root)
    if list(predictions.columns) != ["timestamp", "actual", "prediction", "error", "abs_error"]:
        raise AssertionError("Frozen Phase 4 prediction schema changed")
    timestamps = predictions["timestamp"]
    actual = predictions["actual"].to_numpy(dtype=float)
    baseline, baseline_payload = load_baseline_config(project_root)

    baseline_dispatch, baseline_daily, baseline_audit = run_setting(
        timestamps, actual, forecasts, baseline, experiment="baseline_reproduction", setting="1.0x"
    )
    reproduction = reproduce_phase5_baseline(project_root, baseline_daily, baseline_dispatch)
    if not reproduction["passed"]:
        raise AssertionError(f"Phase 5 baseline regression failed: {reproduction}")

    daily_no_battery, _ = no_battery_rows(timestamps, actual)
    if not np.allclose(daily_no_battery["original_peak"], daily_no_battery["realized_peak"]):
        raise AssertionError("No Battery baseline changed actual load")
    daily = build_daily_diagnostics(predictions, forecasts, baseline_daily, baseline_dispatch)
    regret = build_regret_table(daily)
    correlations = calculate_correlations(regret)
    consistency = build_consistency_table(daily)
    anomalous_dates = build_anomalous_date_rankings(daily)
    bootstrap = paired_bootstrap(
        daily["persistence_decision_regret"].to_numpy() - daily["lgbm_decision_regret"].to_numpy()
    )

    capacity, capacity_audit = run_sensitivity(
        timestamps, actual, forecasts, baseline, experiment="capacity", values=CAPACITY_MULTIPLIERS
    )
    power, power_audit = run_sensitivity(
        timestamps, actual, forecasts, baseline, experiment="power", values=POWER_MULTIPLIERS
    )
    efficiency, efficiency_audit = run_sensitivity(
        timestamps, actual, forecasts, baseline, experiment="efficiency", values=ROUND_TRIP_EFFICIENCIES
    )
    oracle_daily = baseline_daily.loc[baseline_daily["controller"].eq("Oracle")]
    lgbm_daily = baseline_daily.loc[baseline_daily["controller"].eq("LightGBM")]
    bias, bias_audit = run_bias_stress(
        timestamps, actual, forecasts["LightGBM"], baseline, oracle_daily, lgbm_daily
    )
    constraint_audit = pd.concat(
        [baseline_audit, capacity_audit, power_audit, efficiency_audit, bias_audit], ignore_index=True
    )

    daily.to_csv(output_dir / "daily_diagnostics.csv", index=False, float_format="%.10f")
    regret.to_csv(output_dir / "forecast_error_decision_regret.csv", index=False, float_format="%.10f")
    consistency.to_csv(output_dir / "forecast_vs_decision_consistency.csv", index=False, float_format="%.10f")
    anomalous_dates.to_csv(output_dir / "anomalous_date_rankings.csv", index=False, float_format="%.10f")
    capacity.to_csv(output_dir / "battery_capacity_sensitivity.csv", index=False, float_format="%.10f")
    power.to_csv(output_dir / "battery_power_sensitivity.csv", index=False, float_format="%.10f")
    efficiency.to_csv(output_dir / "battery_efficiency_sensitivity.csv", index=False, float_format="%.10f")
    bias.to_csv(output_dir / "forecast_bias_stress_test.csv", index=False, float_format="%.10f")
    constraint_audit.to_csv(output_dir / "constraint_audit.csv", index=False, float_format="%.10f")
    (output_dir / "bootstrap_decision_comparison.json").write_text(
        json.dumps(bootstrap, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )

    _plot_regret(regret, figure_dir / "forecast_error_vs_decision_regret.png")
    _plot_consistency(consistency, figure_dir / "forecast_improvement_vs_decision_improvement.png")
    _plot_sensitivity(capacity, figure_dir / "battery_capacity_sensitivity.png", "Battery Capacity Sensitivity", "Capacity multiplier (Phase 5 baseline = 1.0x)")
    _plot_sensitivity(power, figure_dir / "battery_power_sensitivity.png", "Battery Power Sensitivity", "Charge/discharge power multiplier (Phase 5 baseline = 1.0x)")
    _plot_sensitivity(efficiency, figure_dir / "battery_efficiency_sensitivity.png", "Round-Trip Efficiency Sensitivity", "Round-trip efficiency", xcolumn="round_trip_efficiency_setting")
    _plot_bias(bias, figure_dir / "forecast_bias_robustness.png")
    case_studies = select_case_studies(daily)
    for stale_case in figure_dir.glob("case_study_*.png"):
        stale_case.unlink()
    for case in case_studies:
        _plot_case_study(
            case["date"], case["reason"], baseline_dispatch, figure_dir / f"case_study_{case['date']}.png"
        )

    category_counts = _category_counts(consistency)
    core = daily[["lgbm_decision_regret", "persistence_decision_regret"]]
    capacity_conclusion = capacity.pivot(index="multiplier", columns="controller", values="mean_realized_peak_kw")
    power_conclusion = power.pivot(index="multiplier", columns="controller", values="mean_realized_peak_kw")
    summary: dict[str, Any] = {
        "status": "PASS",
        "phase": "Phase 5.5 robustness / sensitivity / error propagation analysis",
        "runtime_seconds": time.perf_counter() - started,
        "input_audit": {
            "prediction_file": "outputs/phase4/test_prediction.csv",
            "phase4_prediction_sha256": hashes_before["outputs/phase4/test_prediction.csv"],
            "frozen_output_sha256": hashes_before,
            "timestamp_semantics": "target timestamp t+24h, not feature timestamp",
            "test_start": str(TEST_START),
            "test_end": str(TEST_END),
            "hours": 720,
            "days": 30,
            "hours_per_day": 24,
            "actual_matches_raw_load": True,
        },
        "methodology": {
            "decision_regret_definition": "realized_peak_forecast_driven - realized_peak_oracle (kW)",
            "peak_reduction_regret_definition": "oracle_peak_reduction - forecast_driven_peak_reduction (kW)",
            "realized_evaluation_load": "actual",
            "oracle_role": "perfect-information hindsight benchmark; not deployable",
            "daily_optimization": "30 independent 24-hour optimizations with daily SOC reset",
            "economic_regret": "not applicable because Phase 5 has no price, cost, saving, or economic objective",
        },
        "battery_baseline_configuration": baseline_payload,
        "baseline_reproduction": reproduction,
        "daily_robustness": {
            "lightgbm_average_decision_regret_kw": float(core["lgbm_decision_regret"].mean()),
            "persistence_average_decision_regret_kw": float(core["persistence_decision_regret"].mean()),
            "oracle_average_realized_peak_kw": float(daily["oracle_realized_peak"].mean()),
            "lightgbm_win_days": int((core["lgbm_decision_regret"] < core["persistence_decision_regret"] - TOLERANCE).sum()),
            "persistence_win_days": int((core["persistence_decision_regret"] < core["lgbm_decision_regret"] - TOLERANCE).sum()),
            "lightgbm_worst_regret_date": str(daily.loc[daily["lgbm_decision_regret"].idxmax(), "date"]),
            "persistence_worst_regret_date": str(daily.loc[daily["persistence_decision_regret"].idxmax(), "date"]),
        },
        "error_to_decision_relationship": correlations,
        "forecast_to_decision_consistency": {
            "lightgbm_forecast_mae_win_days": int(consistency["lgbm_forecast_better"].sum()),
            "lightgbm_decision_regret_win_days": int(consistency["lgbm_decision_better"].sum()),
            **category_counts,
        },
        "battery_sensitivity": {
            "capacity_mean_realized_peak_kw": {str(index): {key: float(value) for key, value in row.items()} for index, row in capacity_conclusion.to_dict(orient="index").items()},
            "power_mean_realized_peak_kw": {str(index): {key: float(value) for key, value in row.items()} for index, row in power_conclusion.to_dict(orient="index").items()},
            "efficiency_round_trip_values": list(ROUND_TRIP_EFFICIENCIES),
        },
        "forecast_bias_stress": bias.to_dict(orient="records"),
        "bootstrap": bootstrap,
        "case_studies": case_studies,
        "anomalous_date_top3": anomalous_dates.to_dict(orient="records"),
        "constraint_totals": {
            "solver_failures": int((~constraint_audit["solver_success"]).sum()),
            "soc_violations": int(constraint_audit["soc_violations"].sum()),
            "power_violations": int(constraint_audit["power_violations"].sum()),
            "simultaneous_charge_discharge_violations": int(constraint_audit["simultaneous_charge_discharge_violations"].sum()),
            "initial_soc_violations": int(constraint_audit["initial_soc_violations"].sum()),
            "terminal_soc_violations": int(constraint_audit["terminal_soc_violations"].sum()),
        },
    }
    if frozen_output_hashes(project_root) != hashes_before:
        raise AssertionError("A frozen Phase 4 or Phase 5 output was modified")
    _assert_finite_csvs(output_dir)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return summary
