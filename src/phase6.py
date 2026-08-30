"""Phase 6: decision-aware forecasting and stronger baselines for battery peak shaving.

The candidate grids and selection rules are frozen in docs/PHASE6_PROTOCOL.md. This
stage never overwrites Phase 3--5.7 artifacts and does not tune on Test results.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from scripts.run_phase4 import BASE_PARAMETERS, BUILDING, EXPECTED_RAW_SHA256, load_building, sha256
from src.battery.model import BatteryConfig
from src.battery.optimizer import optimize_day
from src.features.load_features import ALL_FEATURES, build_phase4_features
from src.forecast_artifacts import load_canonical_test_forecast
from src.models.train_lgbm import fit_lgbm, purge_unavailable_targets, split_by_feature_time


VALIDATION_START = pd.Timestamp("2017-11-01 00:00:00")
TEST_START = pd.Timestamp("2017-12-01 00:00:00")
PEAK_WEIGHT_CANDIDATES = (
    ("uniform", None, 1.0),
    ("q80_x1_5", 0.80, 1.5),
    ("q80_x2", 0.80, 2.0),
    ("q90_x2", 0.90, 2.0),
    ("q90_x3", 0.90, 3.0),
)
BASELINE_WEEKLY_WEIGHTS = (0.0, 0.25, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if value is None or (isinstance(value, (float, np.floating)) and np.isnan(value)):
            cleaned[key] = None
        elif isinstance(value, np.integer):
            cleaned[key] = int(value)
        elif isinstance(value, np.floating):
            cleaned[key] = float(value)
        elif isinstance(value, np.bool_):
            cleaned[key] = bool(value)
        else:
            cleaned[key] = value
    return cleaned


def make_peak_sample_weights(
    target: pd.Series | np.ndarray,
    peak_quantile: float | None,
    peak_multiplier: float,
    threshold: float | None = None,
) -> tuple[np.ndarray, float | None]:
    values = np.asarray(target, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("target must be a finite one-dimensional array")
    if peak_multiplier < 1.0:
        raise ValueError("peak_multiplier must be at least 1")
    if peak_quantile is None:
        return np.ones(len(values), dtype=float), None
    if not 0.0 < peak_quantile < 1.0:
        raise ValueError("peak_quantile must lie in (0, 1)")
    cutoff = float(np.quantile(values, peak_quantile)) if threshold is None else float(threshold)
    weights = np.ones(len(values), dtype=float)
    weights[values >= cutoff] = float(peak_multiplier)
    return weights, cutoff


def _safe_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = np.abs(actual) > 1e-12
    if not mask.any():
        return 0.0
    return float(100.0 * np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])))


def forecast_metrics(timestamps: pd.Series, actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    ts = pd.to_datetime(pd.Series(timestamps)).reset_index(drop=True)
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    _require(len(ts) == len(actual) == len(predicted), "forecast metric lengths differ")
    _require(np.isfinite(actual).all() and np.isfinite(predicted).all(), "non-finite forecast values")

    q75 = float(np.quantile(actual, 0.75))
    high = actual >= q75
    daily_peak_errors: list[float] = []
    peak_hour_errors: list[float] = []
    peak_hour_hits: list[float] = []
    frame = pd.DataFrame({"timestamp": ts, "actual": actual, "predicted": predicted})
    for _, day in frame.groupby(frame["timestamp"].dt.normalize(), sort=True):
        if len(day) != 24:
            continue
        a = day["actual"].to_numpy(float)
        p = day["predicted"].to_numpy(float)
        actual_peak_hour = int(np.argmax(a))
        predicted_peak_hour = int(np.argmax(p))
        hour_delta = abs(actual_peak_hour - predicted_peak_hour)
        hour_delta = min(hour_delta, 24 - hour_delta)
        daily_peak_errors.append(abs(float(a.max() - p.max())))
        peak_hour_errors.append(abs(float(a[actual_peak_hour] - p[actual_peak_hour])))
        peak_hour_hits.append(float(hour_delta <= 1))

    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "MAPE": _safe_mape(actual, predicted),
        "top_quartile_load_MAE": float(mean_absolute_error(actual[high], predicted[high])),
        "daily_peak_MAE": float(np.mean(daily_peak_errors)) if daily_peak_errors else math.nan,
        "peak_hour_MAE": float(np.mean(peak_hour_errors)) if peak_hour_errors else math.nan,
        "peak_hour_hit_within_1h": float(np.mean(peak_hour_hits)) if peak_hour_hits else math.nan,
    }


def _load_medium_battery(project_root: Path) -> BatteryConfig:
    payload = json.loads((project_root / "outputs" / "phase5" / "phase5_config.json").read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(BatteryConfig)}
    recorded = payload["battery_configs"]["Medium"]
    return BatteryConfig(**{key: value for key, value in recorded.items() if key in allowed})


def evaluate_dispatch(
    timestamps: pd.Series,
    actual: np.ndarray,
    forecast: np.ndarray,
    config: BatteryConfig,
    method: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.Series(timestamps)).to_numpy(),
            "actual": np.asarray(actual, dtype=float),
            "forecast": np.asarray(forecast, dtype=float),
        }
    )
    hourly_parts: list[pd.DataFrame] = []
    daily_rows: list[dict[str, float | str]] = []
    for day_key, day in frame.groupby(frame["timestamp"].dt.normalize(), sort=True):
        if len(day) != 24:
            raise ValueError(f"{method}: incomplete day {day_key}")
        result = optimize_day(day["forecast"].to_numpy(float), config)
        charge = result.charge
        discharge = result.discharge
        realized = day["actual"].to_numpy(float) + charge - discharge
        original_peak = float(day["actual"].max())
        realized_peak = float(realized.max())
        hourly_parts.append(
            pd.DataFrame(
                {
                    "method": method,
                    "timestamp": day["timestamp"].to_numpy(),
                    "actual": day["actual"].to_numpy(float),
                    "forecast": day["forecast"].to_numpy(float),
                    "charge": charge,
                    "discharge": discharge,
                    "soc_start": result.soc[:-1],
                    "soc_end": result.soc[1:],
                    "realized_grid_load": realized,
                }
            )
        )
        daily_rows.append(
            {
                "method": method,
                "date": str(pd.Timestamp(day_key).date()),
                "original_peak": original_peak,
                "realized_peak": realized_peak,
                "peak_reduction": original_peak - realized_peak,
                "throughput": float(charge.sum() + discharge.sum()),
            }
        )
    return pd.concat(hourly_parts, ignore_index=True), pd.DataFrame(daily_rows)


def _tail_mean(values: pd.Series | np.ndarray, fraction: float = 0.10) -> float:
    array = np.sort(np.asarray(values, dtype=float))[::-1]
    count = max(1, int(math.ceil(len(array) * fraction)))
    return float(array[:count].mean())


def _dispatch_summary(daily: pd.DataFrame, oracle_daily: pd.DataFrame | None = None) -> dict[str, float]:
    result = {
        "mean_daily_peak": float(daily["realized_peak"].mean()),
        "worst_10pct_daily_peak": _tail_mean(daily["realized_peak"]),
        "max_daily_peak": float(daily["realized_peak"].max()),
        "mean_peak_reduction": float(daily["peak_reduction"].mean()),
        "total_throughput": float(daily["throughput"].sum()),
    }
    if oracle_daily is not None:
        merged = daily.merge(
            oracle_daily[["date", "realized_peak"]],
            on="date",
            suffixes=("", "_oracle"),
            validate="one_to_one",
        )
        regret = merged["realized_peak"] - merged["realized_peak_oracle"]
        result.update(
            {
                "mean_regret": float(regret.mean()),
                "p90_regret": float(np.quantile(regret, 0.90)),
                "max_regret": float(regret.max()),
            }
        )
    return result


def _write_report(report_path: Path, summary: dict[str, Any], test_forecast: pd.DataFrame, test_dispatch: pd.DataFrame) -> None:
    selected_model = summary["selected_peak_aware_model"]
    selected_baseline = summary["selected_blended_baseline"]
    canonical = test_dispatch.loc[test_dispatch["method"].eq("Phase 4.5 canonical LightGBM")].iloc[0]
    phase6 = test_dispatch.loc[test_dispatch["method"].eq("Phase 6 peak-aware LightGBM")].iloc[0]
    strong = test_dispatch.loc[test_dispatch["method"].eq("Selected blended persistence")].iloc[0]
    delta = float(phase6["mean_daily_peak"] - canonical["mean_daily_peak"])
    improved = delta < 0

    def table(frame: pd.DataFrame, columns: list[str]) -> str:
        lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
        for row in frame[columns].itertuples(index=False, name=None):
            rendered = []
            for value in row:
                if isinstance(value, (float, np.floating)):
                    rendered.append("" if np.isnan(value) else f"{value:.6f}")
                else:
                    rendered.append(str(value))
            lines.append("| " + " | ".join(rendered) + " |")
        return "\n".join(lines)

    forecast_cols = [
        "method", "MAE", "RMSE", "MAPE", "top_quartile_load_MAE",
        "daily_peak_MAE", "peak_hour_MAE", "peak_hour_hit_within_1h",
    ]
    dispatch_cols = [
        "method", "mean_daily_peak", "worst_10pct_daily_peak", "max_daily_peak",
        "mean_peak_reduction", "mean_regret", "p90_regret", "max_regret", "total_throughput",
    ]
    conclusion = (
        "Phase 6 peak-aware LightGBM 在本 Test 的主削峰指标上优于 Phase 4.5 canonical LightGBM。"
        if improved
        else "Phase 6 peak-aware LightGBM 在本 Test 的主削峰指标上未优于 Phase 4.5 canonical LightGBM，因此不能声称决策感知训练带来了削峰改善。"
    )
    text = f"""# Phase 6 — 决策感知预测与项目级优化

## 1. 阶段定位

Phase 6 不覆盖 Phase 3–5.7，而是针对前序复盘暴露出的核心问题进行项目级优化：预测 MAE/RMSE 与储能削峰价值并不完全一致；同时使用更强的日/周组合 baseline，避免只与单一 yesterday persistence 比较。

本阶段候选集合与选择规则已预先冻结在 `docs/PHASE6_PROTOCOL.md`。由于 2017-12 Test 在历史阶段已被观察过，本阶段不把它描述为全新 blind Test；但 Phase 6 不使用 Test 指标选择候选或反调参数。

## 2. Validation 选择结果

选中的峰值感知模型：`{selected_model['candidate']}`；训练峰值阈值={selected_model['training_peak_threshold']}，峰值样本权重={selected_model['peak_multiplier']}，best_iteration={selected_model['best_iteration']}。

选中的组合 baseline：周权重 `w={selected_baseline['weekly_weight']}`，即 `(1-w)*yesterday + w*last_week`。

## 3. Test 预测指标

{table(test_forecast, forecast_cols)}

## 4. Test 储能削峰指标

{table(test_dispatch, dispatch_cols)}

## 5. 核心比较

Phase 6 peak-aware LightGBM 相对 Phase 4.5 canonical LightGBM 的 mean daily realized peak 变化为 `{delta:+.6f} kW`（负值表示改善）。强组合 baseline 的 mean daily realized peak 为 `{float(strong['mean_daily_peak']):.6f} kW`，Phase 6 模型为 `{float(phase6['mean_daily_peak']):.6f} kW`。

{conclusion}

Phase 5.7 的鲁棒优化负结果仍然保留：显式不确定性建模在当时冻结的 residual-block/CVaR 设置下没有改善 Test，Phase 6 不改写该历史结论。

## 6. 竞赛可用表述

本项目从“只优化平均预测误差”进一步转向“面向储能削峰任务的决策感知预测与验证”。模型选择直接以 Validation 上的实际削峰峰值为首要指标，并通过更强的日/周组合基线约束结论强度。最终是否改善由独立于候选选择的固定 Test 评估决定；若削峰未改善，则保留负结果。
"""
    report_path.write_text(text, encoding="utf-8")


def run(project_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    root = Path(project_root).resolve()
    output_dir = root / "outputs" / "phase6"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = root / "reports" / "phase6_report.md"
    raw_path = root / "data" / "raw" / "electricity_cleaned.csv"
    _require(raw_path.is_file(), f"missing raw data: {raw_path}")
    _require(sha256(raw_path) == EXPECTED_RAW_SHA256, "raw electricity CSV hash mismatch")

    load = load_building(raw_path)
    supervised = build_phase4_features(load)
    splits = split_by_feature_time(supervised)
    train = purge_unavailable_targets(splits["train"], VALIDATION_START)
    validation = purge_unavailable_targets(splits["validation"], TEST_START)
    test_features = splits["test"].copy()
    _require(len(validation) % 24 == 0, "Validation selection window must contain full days")
    _require(len(test_features) == 720, "Test feature set must contain 720 rows")

    battery = _load_medium_battery(root)

    baseline_rows: list[dict[str, Any]] = []
    for weekly_weight in BASELINE_WEEKLY_WEIGHTS:
        prediction = (
            (1.0 - weekly_weight) * validation["yesterday_pred"].to_numpy(float)
            + weekly_weight * validation["last_week_pred"].to_numpy(float)
        )
        _, daily = evaluate_dispatch(
            validation["target_timestamp"], validation["target"].to_numpy(float), prediction,
            battery, f"blend_w{weekly_weight:.2f}",
        )
        fm = forecast_metrics(validation["target_timestamp"], validation["target"].to_numpy(float), prediction)
        dm = _dispatch_summary(daily)
        baseline_rows.append(
            {
                "candidate": f"blend_w{weekly_weight:.2f}",
                "weekly_weight": weekly_weight,
                "validation_mean_daily_peak": dm["mean_daily_peak"],
                "validation_worst_10pct_daily_peak": dm["worst_10pct_daily_peak"],
                "validation_top_quartile_load_MAE": fm["top_quartile_load_MAE"],
                **{f"validation_{key}": value for key, value in fm.items() if key != "top_quartile_load_MAE"},
            }
        )
    baseline_table = pd.DataFrame(baseline_rows).sort_values(
        ["validation_mean_daily_peak", "validation_worst_10pct_daily_peak", "validation_top_quartile_load_MAE", "candidate"]
    ).reset_index(drop=True)
    selected_baseline = _clean_record(baseline_table.iloc[0].to_dict())
    baseline_table.to_csv(output_dir / "baseline_selection.csv", index=False)

    model_rows: list[dict[str, Any]] = []
    for name, quantile, multiplier in PEAK_WEIGHT_CANDIDATES:
        weights, threshold = make_peak_sample_weights(train["target"], quantile, multiplier)
        model, validation_prediction = fit_lgbm(
            train, validation, ALL_FEATURES, BASE_PARAMETERS, train_sample_weight=weights
        )
        _, daily = evaluate_dispatch(
            validation["target_timestamp"], validation["target"].to_numpy(float), validation_prediction,
            battery, name,
        )
        fm = forecast_metrics(
            validation["target_timestamp"], validation["target"].to_numpy(float), validation_prediction
        )
        dm = _dispatch_summary(daily)
        model_rows.append(
            {
                "candidate": name,
                "peak_quantile": quantile,
                "peak_multiplier": multiplier,
                "training_peak_threshold": threshold,
                "best_iteration": int(model.best_iteration_),
                "validation_mean_daily_peak": dm["mean_daily_peak"],
                "validation_worst_10pct_daily_peak": dm["worst_10pct_daily_peak"],
                "validation_top_quartile_load_MAE": fm["top_quartile_load_MAE"],
                **{f"validation_{key}": value for key, value in fm.items() if key != "top_quartile_load_MAE"},
            }
        )
    model_table = pd.DataFrame(model_rows).sort_values(
        ["validation_mean_daily_peak", "validation_worst_10pct_daily_peak", "validation_top_quartile_load_MAE", "candidate"]
    ).reset_index(drop=True)
    selected_model = _clean_record(model_table.iloc[0].to_dict())
    model_table.to_csv(output_dir / "model_selection.csv", index=False)

    selected_config = {
        "protocol": "docs/PHASE6_PROTOCOL.md",
        "building": BUILDING,
        "features": ALL_FEATURES,
        "battery": "Phase 5 frozen Medium",
        "selected_blended_baseline": selected_baseline,
        "selected_peak_aware_model": selected_model,
        "test_used_for_selection": False,
        "test_is_historically_observed_not_pristine_blind": True,
    }
    (output_dir / "selected_config.json").write_text(
        json.dumps(selected_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from lightgbm import LGBMRegressor

    refit = pd.concat([train, validation], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    threshold = selected_model["training_peak_threshold"]
    multiplier = float(selected_model["peak_multiplier"])
    refit_weights = np.ones(len(refit), dtype=float)
    if threshold is not None:
        refit_weights[refit["target"].to_numpy(float) >= float(threshold)] = multiplier
    final_parameters = {**BASE_PARAMETERS, "n_estimators": int(selected_model["best_iteration"])}
    final_model = LGBMRegressor(**final_parameters)
    final_model.fit(refit[ALL_FEATURES], refit["target"], sample_weight=refit_weights)

    # Test begins here. No candidate or hyperparameter choice is permitted after this line.
    canonical_test, lineage = load_canonical_test_forecast(root)
    phase6_test_prediction = np.maximum(final_model.predict(test_features[ALL_FEATURES]), 0.0)
    _require(
        np.array_equal(test_features["target_timestamp"].to_numpy(), canonical_test["timestamp"].to_numpy()),
        "Phase 6 Test target timestamps differ from canonical lineage",
    )
    _require(
        np.allclose(test_features["target"].to_numpy(float), canonical_test["actual"].to_numpy(float), atol=1e-12, rtol=0.0),
        "Phase 6 Test actual differs from canonical lineage",
    )

    yesterday = test_features["yesterday_pred"].to_numpy(float)
    last_week = test_features["last_week_pred"].to_numpy(float)
    weekly_weight = float(selected_baseline["weekly_weight"])
    blended = (1.0 - weekly_weight) * yesterday + weekly_weight * last_week
    actual = canonical_test["actual"].to_numpy(float)
    timestamps = canonical_test["timestamp"]
    forecasts = {
        "Yesterday persistence": yesterday,
        "Last-week persistence": last_week,
        "Selected blended persistence": blended,
        "Phase 4.5 canonical LightGBM": canonical_test["prediction"].to_numpy(float),
        "Phase 6 peak-aware LightGBM": phase6_test_prediction,
        "Oracle": actual.copy(),
    }

    forecast_table = pd.DataFrame(
        [{"method": name, **forecast_metrics(timestamps, actual, values)} for name, values in forecasts.items()]
    )
    forecast_table.to_csv(output_dir / "test_forecast_metrics.csv", index=False)

    dispatches: dict[str, pd.DataFrame] = {}
    daily_parts: list[pd.DataFrame] = []
    for name, values in forecasts.items():
        hourly, daily = evaluate_dispatch(timestamps, actual, values, battery, name)
        dispatches[name] = hourly
        daily_parts.append(daily)
    oracle_daily = next(part for part in daily_parts if part["method"].iloc[0] == "Oracle")

    dispatch_rows = []
    for daily in daily_parts:
        name = str(daily["method"].iloc[0])
        dispatch_rows.append(
            {"method": name, **_dispatch_summary(daily, None if name == "Oracle" else oracle_daily)}
        )

    no_battery_hourly = pd.DataFrame(
        {"timestamp": pd.to_datetime(timestamps).to_numpy(), "actual": actual}
    )
    no_battery_daily = (
        no_battery_hourly.assign(date=no_battery_hourly["timestamp"].dt.date.astype(str))
        .groupby("date", as_index=False)["actual"]
        .max()
        .rename(columns={"actual": "realized_peak"})
    )
    no_battery_daily.insert(0, "method", "No Battery")
    no_battery_daily["original_peak"] = no_battery_daily["realized_peak"]
    no_battery_daily["peak_reduction"] = 0.0
    no_battery_daily["throughput"] = 0.0
    dispatch_rows.insert(0, {"method": "No Battery", **_dispatch_summary(no_battery_daily, oracle_daily)})

    dispatch_table = pd.DataFrame(dispatch_rows)
    dispatch_table.to_csv(output_dir / "test_dispatch_metrics.csv", index=False)
    pd.concat([no_battery_daily, *daily_parts], ignore_index=True, sort=False).to_csv(
        output_dir / "test_daily_metrics.csv", index=False
    )
    pd.DataFrame({"timestamp": timestamps, "actual": actual, **forecasts}).to_csv(
        output_dir / "test_predictions.csv", index=False, date_format="%Y-%m-%d %H:%M:%S"
    )
    dispatches["Phase 6 peak-aware LightGBM"].to_csv(
        output_dir / "dispatch_phase6_lightgbm.csv", index=False, date_format="%Y-%m-%d %H:%M:%S"
    )
    dispatches["Selected blended persistence"].to_csv(
        output_dir / "dispatch_selected_blend.csv", index=False, date_format="%Y-%m-%d %H:%M:%S"
    )

    canonical_peak = float(
        dispatch_table.loc[dispatch_table["method"].eq("Phase 4.5 canonical LightGBM"), "mean_daily_peak"].iloc[0]
    )
    phase6_peak = float(
        dispatch_table.loc[dispatch_table["method"].eq("Phase 6 peak-aware LightGBM"), "mean_daily_peak"].iloc[0]
    )
    summary = {
        **selected_config,
        "lineage": lineage,
        "phase6_vs_canonical_mean_daily_peak_delta": phase6_peak - canonical_peak,
        "phase6_improves_primary_test_metric": bool(phase6_peak < canonical_peak),
        "runtime_seconds": time.perf_counter() - started,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_report(report_path, summary, forecast_table, dispatch_table)
    return summary
