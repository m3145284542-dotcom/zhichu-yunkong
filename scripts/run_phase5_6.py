"""Phase 5.6: repair forecast lineage and rerun the frozen Phase 5 experiment."""

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

from scripts.run_phase5 import (
    BUILDING,
    CONTROLLERS,
    TEST_END,
    TEST_START,
    TOLERANCE,
    no_battery_rows,
    run_controller,
    safe_prediction_metrics,
)
from src.battery.metrics import aggregate_performance, oracle_capture_ratio
from src.battery.model import BatteryConfig
from src.forecast_artifacts import load_canonical_test_forecast, sha256_file


REGRESSION_TOLERANCE = 1e-8
METRIC_COLUMNS = (
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
)


def _frozen_hashes(project_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for phase in ("phase4", "phase4_5", "phase5", "phase5_5"):
        directory = project_root / "outputs" / phase
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            hashes[path.relative_to(project_root).as_posix()] = sha256_file(path)
    return hashes


def _load_frozen_battery_configs(project_root: Path) -> tuple[dict[str, BatteryConfig], dict[str, Any]]:
    path = project_root / "outputs" / "phase5" / "phase5_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(BatteryConfig)}
    configs: dict[str, BatteryConfig] = {}
    for size in ("Small", "Medium", "Large"):
        recorded = payload["battery_configs"][size]
        config = BatteryConfig(**{key: value for key, value in recorded.items() if key in allowed})
        for derived in ("soc_min", "soc_max", "initial_soc", "terminal_soc", "round_trip_efficiency"):
            if not np.isclose(getattr(config, derived), recorded[derived], atol=1e-12, rtol=0.0):
                raise AssertionError(f"Frozen Phase 5 {size} {derived} does not reproduce")
        configs[size] = config
    return configs, payload


def _load_forecasts(
    project_root: Path,
) -> tuple[pd.DataFrame, dict[str, np.ndarray], pd.DataFrame, dict[str, Any], bool]:
    predictions, lineage = load_canonical_test_forecast(project_root)
    expected_index = pd.date_range(TEST_START, TEST_END, freq="h")
    if not predictions["timestamp"].equals(pd.Series(expected_index, name="timestamp")):
        raise AssertionError("Canonical target timestamps do not match the frozen Phase 5 Test period")

    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    raw = pd.read_csv(raw_path, usecols=["timestamp", BUILDING])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="raise")
    raw = raw.sort_values("timestamp")
    if raw["timestamp"].duplicated().any():
        raise AssertionError("Raw load contains duplicate timestamps")
    raw_series = raw.set_index("timestamp")[BUILDING].astype(float)
    raw_actual = raw_series.reindex(expected_index)
    raw_alignment = bool(
        raw_actual.notna().all()
        and np.allclose(predictions["actual"], raw_actual.to_numpy(), atol=1e-10, rtol=0.0)
    )
    if not raw_alignment:
        raise AssertionError("Canonical actual does not match raw load")

    persistence_source = expected_index - pd.Timedelta(hours=24)
    persistence = raw_series.reindex(persistence_source)
    if not persistence.notna().all():
        raise AssertionError("Persistence source load is incomplete")
    target_day_start = pd.Series(expected_index).dt.normalize().to_numpy()
    if not np.all(persistence_source.to_numpy() < target_day_start):
        raise AssertionError("Persistence uses information unavailable before target-day dispatch")
    if not np.all(expected_index - persistence_source == pd.Timedelta(hours=24)):
        raise AssertionError("Persistence must be actual(T-24h)")

    actual = predictions["actual"].to_numpy(dtype=float)
    forecasts = {
        "Persistence": persistence.to_numpy(dtype=float),
        "LightGBM": predictions["prediction"].to_numpy(dtype=float),
        "Oracle": actual.copy(),
    }

    historical = pd.read_csv(project_root / "outputs" / "phase4" / "test_prediction.csv")
    historical["timestamp"] = pd.to_datetime(historical["timestamp"], errors="raise")
    if not historical["timestamp"].equals(predictions["timestamp"]):
        raise AssertionError("Phase 4 and Phase 4.5 target timestamps differ")
    if not np.array_equal(historical["actual"].to_numpy(float), actual):
        raise AssertionError("Phase 4 and Phase 4.5 actual values differ")
    if np.array_equal(historical["prediction"].to_numpy(float), forecasts["LightGBM"]):
        raise AssertionError("Forecast lineage repair produced no source change")

    comparison_forecasts = {
        "Phase 4 historical LightGBM": historical["prediction"].to_numpy(float),
        "Phase 4.5 canonical LightGBM": forecasts["LightGBM"],
        "Persistence": forecasts["Persistence"],
        "Oracle": forecasts["Oracle"],
    }
    forecast_comparison = pd.DataFrame(
        [
            {"forecast_source": name, **safe_prediction_metrics(actual, values)}
            for name, values in comparison_forecasts.items()
        ]
    )
    return predictions, forecasts, forecast_comparison, lineage, raw_alignment


def _build_metrics(
    predictions: pd.DataFrame,
    forecasts: dict[str, np.ndarray],
    configs: dict[str, BatteryConfig],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    timestamps = predictions["timestamp"]
    actual = predictions["actual"].to_numpy(dtype=float)
    no_daily, no_aggregate = no_battery_rows(timestamps, actual)
    daily_parts = [no_daily]
    audit_parts: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = [no_aggregate]
    dispatches: dict[tuple[str, str], pd.DataFrame] = {}

    for size in ("Medium", "Small", "Large"):
        config = configs[size]
        for controller in CONTROLLERS:
            dispatch, daily, audit = run_controller(
                timestamps, actual, forecasts[controller], controller, config
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
                    "simultaneous_charge_discharge_violations": int(
                        audit["simultaneous_charge_discharge_violations"].sum()
                    ),
                    "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
                    "solver_failures": int((~audit["solver_success"]).sum()),
                    "oracle_capture_ratio": np.nan,
                }
            )

    metrics = pd.DataFrame(metric_rows)
    no_peak = float(metrics.loc[metrics["controller"].eq("No Battery"), "mean_daily_peak"].iloc[0])
    for size in configs:
        mask = metrics["battery_size"].eq(size)
        peaks = metrics.loc[mask].set_index("controller")["mean_daily_peak"]
        oracle_peak = float(peaks["Oracle"])
        for controller in CONTROLLERS:
            row = mask & metrics["controller"].eq(controller)
            metrics.loc[row, "oracle_capture_ratio"] = oracle_capture_ratio(
                no_peak, float(peaks[controller]), oracle_peak
            )
    return metrics, pd.concat(daily_parts, ignore_index=True), pd.concat(audit_parts, ignore_index=True), dispatches


def _comparison_vs_phase5(project_root: Path, metrics: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    old = pd.read_csv(project_root / "outputs" / "phase5" / "phase5_metrics.csv")
    old["battery_size"] = old["battery_size"].fillna("None")
    new = metrics.copy()
    new["battery_size"] = new["battery_size"].fillna("None")
    merged = old[["controller", "battery_size", *METRIC_COLUMNS]].merge(
        new[["controller", "battery_size", *METRIC_COLUMNS]],
        on=["controller", "battery_size"],
        how="outer",
        validate="one_to_one",
        suffixes=("_phase5", "_phase5_6"),
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise AssertionError("Phase 5 and Phase 5.6 metric row identities differ")
    merged = merged.drop(columns="_merge")
    for metric in METRIC_COLUMNS:
        merged[f"delta_{metric}"] = merged[f"{metric}_phase5_6"] - merged[f"{metric}_phase5"]

    statuses: dict[str, Any] = {}
    for controller in ("No Battery", "Persistence", "Oracle"):
        rows = merged.loc[merged["controller"].eq(controller)]
        finite_deltas = []
        for metric in METRIC_COLUMNS:
            values = rows[f"delta_{metric}"].dropna().abs().to_numpy(float)
            finite_deltas.extend(values.tolist())
        maximum = max(finite_deltas, default=0.0)
        passed = maximum <= REGRESSION_TOLERANCE
        statuses[controller] = {"passed": passed, "maximum_absolute_delta": maximum}
        if not passed:
            raise AssertionError(f"Isolation regression failed for {controller}: {maximum}")
    return merged, statuses


def _write_report(
    project_root: Path,
    forecast_comparison: pd.DataFrame,
    comparison: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    def markdown_table(frame: pd.DataFrame, digits: int) -> str:
        columns = list(frame.columns)
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for row in frame.itertuples(index=False, name=None):
            rendered = []
            for value in row:
                if isinstance(value, (float, np.floating)):
                    rendered.append("" if np.isnan(value) else f"{value:.{digits}f}")
                else:
                    rendered.append(str(value))
            lines.append("| " + " | ".join(rendered) + " |")
        return "\n".join(lines)

    medium = comparison.loc[
        comparison["controller"].eq("LightGBM") & comparison["battery_size"].eq("Medium")
    ]
    forecast_table = markdown_table(forecast_comparison, 6)
    selected = ["controller", "battery_size"]
    for metric in ("mean_daily_peak", "mean_peak_reduction", "mean_peak_reduction_pct", "max_peak", "oracle_capture_ratio"):
        selected.extend([f"{metric}_phase5", f"{metric}_phase5_6", f"delta_{metric}"])
    decision_table = comparison.loc[
        comparison["controller"].isin(["No Battery", "Persistence", "LightGBM", "Oracle"])
        & comparison["battery_size"].isin(["None", "Medium"]),
        selected,
    ]
    decision_table = markdown_table(decision_table, 8)
    lightgbm_delta = medium.iloc[0]
    audit = summary["audit_findings"]
    constraints = summary["invariants"]
    text = f"""# Phase 5.6：预测数据血缘修复与下游重算

## 漏洞发现与根因

Phase 4.5 已输出经过边界标签 purge 和重新拟合的 `outputs/phase4_5/final_predictions.csv`，但代码审计发现 `scripts/run_phase5.py` 的 `load_inputs()` 仍硬编码读取 `outputs/phase4/test_prediction.csv`。Phase 5.5 又复用该输入函数，因此修复前的数据链实际为 `Phase 4 -> Phase 5 -> Phase 5.5`。

不覆盖 Phase 4 的原因是它仍是可复现实验的历史基线；覆盖会破坏既有 Phase 5/5.5 的来源证据和前后对照。Phase 4.5 被设为 canonical 的理由是实验时间边界和数据可用性协议更严格，而不是根据 Test 预测或削峰结果择优。

修复后正式数据链为 `Phase 4 -> Phase 4.5 canonical forecast -> Phase 5.6 -> 后续阶段`。统一入口为 `load_canonical_test_forecast(project_root)`，且没有 Phase 4 fallback。

## 修改前审计事实

- Phase 4.5 Test feature 时间：{audit['phase4_5_test_feature_period']}；target 时间：{audit['phase4_5_test_target_period']}。
- Test 为 720 小时、30 天、每日 24 条，且每行 `target_timestamp - feature_timestamp = 24h`。
- Phase 4 与 Phase 4.5 的 timestamp、actual 完全一致；720 行 prediction 全部变化，最大绝对预测差为 {audit['prediction_max_absolute_difference']:.6f}。
- Phase 4.5 对 Train 和 Validation 边界标签均执行 purge；配置明确 Test 不参与特征或参数选择。
- Phase 5 的旧配置明确记录 `input_prediction_file = outputs/phase4/test_prediction.csv`，绕过原因仅是硬编码输入血缘。

## Phase 4 vs Phase 4.5 预测指标

{forecast_table}

不能把该表概括为“Phase 4.5 精度更高”：MAE/MAPE 变差而 RMSE 改善。canonical 身份来自更正确的可用性协议。

## Phase 5 vs Phase 5.6 削峰指标（Medium 为主）

{decision_table}

Phase 4.5 来源修复后，Medium LightGBM 的 mean daily peak 变化 {lightgbm_delta['delta_mean_daily_peak']:+.8f} kW，mean peak reduction 变化 {lightgbm_delta['delta_mean_peak_reduction']:+.8f} kW，mean peak reduction pct 变化 {lightgbm_delta['delta_mean_peak_reduction_pct']:+.8f} 个百分点，max peak 变化 {lightgbm_delta['delta_max_peak']:+.8f} kW，oracle capture ratio 变化 {lightgbm_delta['delta_oracle_capture_ratio']:+.8f}。

## Isolation regression 与约束审计

No Battery、Persistence、Oracle 的最大绝对指标 delta 分别为 {summary['invariants']['regression_status']['No Battery']['maximum_absolute_delta']:.3e}、{summary['invariants']['regression_status']['Persistence']['maximum_absolute_delta']:.3e}、{summary['invariants']['regression_status']['Oracle']['maximum_absolute_delta']:.3e}，均在 `1e-8` 内。全部 MILP 求解成功；SOC、功率、同时充放电、初始 SOC、终端 SOC 违规数均为 0。

## 对 Phase 5.5 的影响

Phase 5.5 历史输出继续保留，但其中 LightGBM 的误差传播、鲁棒性和敏感性结论基于旧 Phase 4 forecast source，不能作为 canonical forecast 的正式下游结论。建议以 Phase 4.5 canonical forecast 重跑一个新的 corrective robustness stage；不得覆盖 Phase 5.5。

## 后续数据血缘规则

Phase 6/7、储能决策和 Web 层必须通过 canonical loader 取得正式预测，不得拼接具体阶段路径。loader 必须同时验证来源配置、时间语义、完整性、误差列一致性与 SHA-256。Oracle 仅是不可部署的 hindsight upper bound；Persistence 仍严格为目标日前已知的 `actual(T-24h)`。
"""
    path = project_root / "reports" / "phase5_6_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    root = Path(project_root).resolve()
    frozen_before = _frozen_hashes(root)
    output_dir = root / "outputs" / "phase5_6"
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions, forecasts, forecast_comparison, lineage, raw_alignment = _load_forecasts(root)
    configs, phase5_config = _load_frozen_battery_configs(root)
    metrics, daily, audit, dispatches = _build_metrics(predictions, forecasts, configs)
    comparison, regression_status = _comparison_vs_phase5(root, metrics)

    if not audit["solver_success"].all():
        raise AssertionError("At least one Phase 5.6 MILP failed")
    if int(audit[["soc_violations", "power_violations", "simultaneous_charge_discharge_violations"]].sum().sum()) != 0:
        raise AssertionError("Phase 5.6 battery constraint violation")
    if not (audit["initial_soc_error"].abs() <= TOLERANCE).all():
        raise AssertionError("Phase 5.6 initial SOC violation")
    if not (audit["terminal_soc_error"].abs() <= TOLERANCE).all():
        raise AssertionError("Phase 5.6 terminal SOC violation")

    metrics.to_csv(output_dir / "phase5_6_metrics.csv", index=False, float_format="%.10f")
    daily.to_csv(output_dir / "daily_metrics.csv", index=False, float_format="%.10f")
    audit.to_csv(output_dir / "constraint_audit.csv", index=False, float_format="%.10f")
    forecast_comparison.to_csv(output_dir / "forecast_source_comparison.csv", index=False, float_format="%.10f")
    comparison.to_csv(output_dir / "comparison_vs_phase5.csv", index=False, float_format="%.10f")
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

    phase4 = pd.read_csv(root / "outputs" / "phase4" / "test_prediction.csv")
    phase45_test = pd.read_csv(root / "outputs" / "phase4_5" / "final_predictions.csv")
    phase45_test = phase45_test.loc[phase45_test["split"].eq("test")].reset_index(drop=True)
    prediction_max_difference = float(
        np.max(np.abs(phase4["prediction"].to_numpy(float) - phase45_test["y_pred"].to_numpy(float)))
    )
    constraint_totals = {
        "solver_failures": int((~audit["solver_success"]).sum()),
        "soc_violations": int(audit["soc_violations"].sum()),
        "power_violations": int(audit["power_violations"].sum()),
        "simultaneous_charge_discharge_violations": int(
            audit["simultaneous_charge_discharge_violations"].sum()
        ),
        "initial_soc_violations": int((audit["initial_soc_error"].abs() > TOLERANCE).sum()),
        "terminal_soc_violations": int((audit["terminal_soc_error"].abs() > TOLERANCE).sum()),
    }
    summary: dict[str, Any] = {
        "status": "PASS",
        "phase": "Phase 5.6 forecast lineage repair and downstream regression audit",
        "runtime_seconds": time.perf_counter() - started,
        "finding": "Phase 5 consumed Phase 4 prediction instead of the Phase 4.5 leakage-audited final prediction.",
        "resolution": {
            "historical_baseline": "Phase 4 is retained unchanged as the historical baseline.",
            "canonical_artifact": "outputs/phase4_5/final_predictions.csv",
            "rule": "Phase 4.5 is canonical because its boundary-label availability protocol is stricter, not because of downstream Test performance.",
        },
        "lineage": lineage,
        "audit_findings": {
            "phase4_5_test_feature_period": "2017-12-01 00:00:00 to 2017-12-30 23:00:00",
            "phase4_5_test_target_period": "2017-12-02 00:00:00 to 2017-12-31 23:00:00",
            "phase4_and_phase4_5_timestamps_identical": True,
            "phase4_and_phase4_5_actual_identical": True,
            "phase4_and_phase4_5_predictions_identical": False,
            "changed_prediction_rows": 720,
            "prediction_max_absolute_difference": prediction_max_difference,
            "train_boundary_labels_purged": True,
            "validation_boundary_labels_purged": True,
            "test_used_for_selection": False,
            "historical_phase5_input_prediction_file": phase5_config["input_prediction_file"],
        },
        "frozen_phase5_experiment": {
            "source_config": "outputs/phase5/phase5_config.json",
            "source_config_sha256": sha256_file(root / "outputs" / "phase5" / "phase5_config.json"),
            "battery_configs": phase5_config["battery_configs"],
            "solver": phase5_config["solver"],
            "objective": phase5_config["objective"],
            "daily_soc_reset": True,
            "persistence": "forecast(T) = raw actual(T-24h), available before target day starts",
            "oracle": "perfect-foresight hindsight upper bound; not deployable",
        },
        "invariants": {
            "hours": 720,
            "days": 30,
            "hours_per_day": 24,
            "raw_actual_alignment": raw_alignment,
            **constraint_totals,
            "regression_tolerance": REGRESSION_TOLERANCE,
            "regression_status": regression_status,
        },
        "supersession": {
            "phase5": "Retained unchanged; its LightGBM result is no longer the final official competition result.",
            "phase5_5": "Retained unchanged; its LightGBM robustness conclusion uses the historical Phase 4 forecast source.",
            "downstream": "Use the Phase 4.5 canonical forecast and Phase 5.6 results for official downstream work.",
        },
    }
    if _frozen_hashes(root) != frozen_before:
        raise AssertionError("A historical Phase 4/4.5/5/5.5 output was modified")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    _write_report(root, forecast_comparison, comparison, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return summary


if __name__ == "__main__":
    run()
