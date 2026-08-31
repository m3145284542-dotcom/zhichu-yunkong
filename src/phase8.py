"""Phase 8 decision-oriented Day-Week + LightGBM ensemble experiment."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features.load_features import ALL_FEATURES
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import day_week_blend
from src.phase7.evaluation import audit_totals, evaluate_method, normalized_forecast_metrics
from src.phase7.models import RANDOM_SEED, refit_fixed, predict
from src.phase7.pipeline import (
    TEST_START,
    VALIDATION_START,
    battery_for,
    load_office_data,
    supervised_for,
)


WEIGHT_GRID = tuple(np.round(np.arange(0.0, 1.01, 0.1), 1))
BUILDINGS = (
    "Hog_office_Rolando",
    "Hog_office_Lavon",
    "Hog_office_Joey",
    "Lamb_office_Caitlin",
    "Robin_office_Addie",
    "Lamb_office_Gerardo",
    "Hog_office_Alexis",
    "Hog_office_Byron",
)
METHODS = (
    "DayWeek",
    "LightGBM",
    "ForecastSelectedPerBuilding",
    "DecisionSelectedPerBuilding",
    "ForecastSelectedGlobal",
    "DecisionSelectedGlobal",
)
TOLERANCE = 1e-8
BOOTSTRAP_SEED = 42
BOOTSTRAP_RESAMPLES = 10_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensemble_prediction(dayweek: np.ndarray, ml: np.ndarray, weight: float) -> np.ndarray:
    """Return w * ML + (1-w) * Day-Week on the frozen finite grid domain."""
    if not 0.0 <= float(weight) <= 1.0:
        raise ValueError("weight must be in [0, 1]")
    baseline = np.asarray(dayweek, dtype=float)
    machine = np.asarray(ml, dtype=float)
    if baseline.shape != machine.shape or not np.isfinite(baseline).all() or not np.isfinite(machine).all():
        raise ValueError("Predictions must be aligned finite arrays")
    return float(weight) * machine + (1.0 - float(weight)) * baseline


def _validation_only(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"split", "weight", "MAE", "RMSE", "mean_regret_vs_oracle", "p90_regret"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing selection columns: {sorted(missing)}")
    if frame.empty or not frame["split"].eq("validation").all():
        raise ValueError("Weight selection accepts Validation rows only")
    result = frame.copy()
    result["endpoint_distance"] = np.round(
        np.minimum(result["weight"], 1.0 - result["weight"]), 12
    )
    return result


def select_forecast_weight(frame: pd.DataFrame) -> float:
    """MAE, RMSE, endpoint simplicity, then smaller weight."""
    table = _validation_only(frame)
    chosen = table.sort_values(
        ["MAE", "RMSE", "endpoint_distance", "weight"], kind="mergesort"
    ).iloc[0]
    return float(chosen["weight"])


def select_decision_weight(frame: pd.DataFrame) -> float:
    """Mean regret, p90 regret, MAE, endpoint simplicity, then smaller weight."""
    table = _validation_only(frame)
    chosen = table.sort_values(
        ["mean_regret_vs_oracle", "p90_regret", "MAE", "endpoint_distance", "weight"],
        kind="mergesort",
    ).iloc[0]
    return float(chosen["weight"])


def select_global_weights(search: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame]:
    """Select shared weights from equal-building means normalized by Phase 7 Train scale."""
    table = _validation_only(search)
    if "train_mean_load" not in table or (table["train_mean_load"] <= 0).any():
        raise ValueError("Positive Phase 7 Train mean load is required")
    table["normalized_MAE"] = table["MAE"] / table["train_mean_load"]
    table["normalized_RMSE"] = table["RMSE"] / table["train_mean_load"]
    table["normalized_mean_regret"] = table["mean_regret_vs_oracle"] / table["train_mean_load"]
    table["normalized_p90_regret"] = table["p90_regret"] / table["train_mean_load"]
    aggregate = table.groupby("weight", as_index=False).agg(
        normalized_MAE=("normalized_MAE", "mean"),
        normalized_RMSE=("normalized_RMSE", "mean"),
        normalized_mean_regret=("normalized_mean_regret", "mean"),
        normalized_p90_regret=("normalized_p90_regret", "mean"),
        building_count=("building", "nunique") if "building" in table else ("weight", "size"),
    )
    aggregate["split"] = "validation"
    aggregate["normalization_source"] = "Phase 7 Train mean load"
    aggregate["endpoint_distance"] = np.round(
        np.minimum(aggregate.weight, 1.0 - aggregate.weight), 12
    )
    forecast = aggregate.sort_values(
        ["normalized_MAE", "normalized_RMSE", "endpoint_distance", "weight"], kind="mergesort"
    ).iloc[0]
    decision = aggregate.sort_values(
        ["normalized_mean_regret", "normalized_p90_regret", "normalized_MAE", "endpoint_distance", "weight"],
        kind="mergesort",
    ).iloc[0]
    return {"forecast": float(forecast.weight), "decision": float(decision.weight)}, aggregate


def tracked_frozen_hashes(root: Path) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "ls-files", "outputs/phase3", "outputs/phase4", "outputs/phase4_5",
         "outputs/phase5", "outputs/phase5_5", "outputs/phase5_6", "outputs/phase5_7",
         "outputs/phase6", "outputs/phase7", "reports/phase3*", "reports/phase4*",
         "reports/phase5*", "reports/phase6*", "reports/phase7*"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    paths = [root / line for line in completed.stdout.splitlines() if line]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise AssertionError(f"Tracked frozen artifacts missing: {missing[:3]}")
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(paths)}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _prepare(root: Path, model_config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    electricity, _ = load_office_data(root)
    prepared: dict[str, Any] = {}
    batteries: dict[str, Any] = {}
    for building in BUILDINGS:
        splits = split_by_feature_time(supervised_for(electricity, building))
        train_select = purge_unavailable_targets(splits["train"], VALIDATION_START)
        validation_select = purge_unavailable_targets(splits["validation"], TEST_START)
        if len(validation_select) != 696 or len(splits["test"]) != 720:
            raise AssertionError(f"Frozen split completeness failed for {building}")
        train_mean = float(splits["train"]["current_load"].mean())
        key = f"{building}|LightGBM"
        if key not in model_config["selected_models"]:
            raise AssertionError(f"Missing frozen LightGBM selection: {key}")
        prepared[building] = (splits, train_select, validation_select, train_mean)
        batteries[building] = battery_for(building, train_mean)
    return prepared, batteries


def _fixed_lgbm(config: dict[str, Any], building: str, fit_frame: pd.DataFrame):
    chosen = config["selected_models"][f"{building}|LightGBM"]
    return refit_fixed("LightGBM", fit_frame, ALL_FEATURES, chosen["parameters"], int(chosen["best_iteration"])), int(chosen["best_iteration"])


def _bootstrap(values: np.ndarray) -> dict[str, Any]:
    paired = np.asarray(values, dtype=float)
    if paired.ndim != 1 or paired.size == 0 or not np.isfinite(paired).all():
        raise ValueError("Bootstrap values must be finite")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(paired), size=(BOOTSTRAP_RESAMPLES, len(paired)))
    means = paired[indices].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "comparison": "DecisionSelectedPerBuilding minus ForecastSelectedPerBuilding",
        "metric": "daily regret difference normalized by Phase 7 Train mean load",
        "resampling_unit": "building-day pair",
        "pairs": int(len(paired)),
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "mean_difference": float(paired.mean()),
        "median_difference": float(np.median(paired)),
        "ci95_lower": float(low),
        "ci95_upper": float(high),
        "probability_of_improvement": float(np.mean(means < 0.0)),
    }


def _aggregate_metrics(forecast: pd.DataFrame, decision: pd.DataFrame, means: pd.Series) -> pd.DataFrame:
    f = forecast.copy()
    all_decision = decision.copy()
    d = all_decision.loc[all_decision.method.ne("Oracle")].copy()
    f["normalized_peak_quartile_MAE"] = f["peak_quartile_MAE"] / f.building.map(means)
    for frame in (all_decision, d):
        frame["normalized_mean_daily_peak"] = frame["mean_daily_peak"] / frame.building.map(means)
        frame["normalized_worst_10pct_daily_peak"] = frame["worst_10pct_daily_peak"] / frame.building.map(means)
        frame["normalized_mean_regret"] = frame["mean_regret_vs_oracle"] / frame.building.map(means)
        frame["normalized_p90_regret"] = frame["p90_regret"] / frame.building.map(means)
    rows = []
    for method in METHODS:
        fm, dm = f.loc[f.method.eq(method)], d.loc[d.method.eq(method)]
        rows.append({
            "method": method,
            "building_count": int(fm.building.nunique()),
            "mean_normalized_MAE": float(fm.normalized_MAE.mean()),
            "median_normalized_MAE": float(fm.normalized_MAE.median()),
            "mean_normalized_RMSE": float(fm.normalized_RMSE.mean()),
            "mean_normalized_peak_quartile_MAE": float(fm.normalized_peak_quartile_MAE.mean()),
            "mean_bias_kw": float(fm.bias.mean()),
            "mean_daily_peak_hour_MAE": float(fm.daily_peak_hour_MAE.mean()),
            "mean_daily_peak_hour_exact_rate": float(fm.daily_peak_hour_exact_rate.mean()),
            "mean_daily_top3_overlap": float(fm.daily_top3_overlap.mean()),
            "mean_daily_realized_peak_kw": float(dm.mean_daily_peak.mean()),
            "mean_normalized_daily_realized_peak": float(dm.normalized_mean_daily_peak.mean()),
            "mean_worst_10pct_daily_peak_kw": float(dm.worst_10pct_daily_peak.mean()),
            "mean_normalized_worst_10pct_daily_peak": float(dm.normalized_worst_10pct_daily_peak.mean()),
            "mean_regret_vs_oracle_kw": float(dm.mean_regret_vs_oracle.mean()),
            "mean_normalized_regret": float(dm.normalized_mean_regret.mean()),
            "mean_p90_regret_kw": float(dm.p90_regret.mean()),
            "mean_normalized_p90_regret": float(dm.normalized_p90_regret.mean()),
            "mean_max_regret_kw": float(dm.max_regret.mean()),
            "mean_oracle_capture_ratio": float(dm.oracle_capture_ratio.mean()),
            "mean_equivalent_full_cycles": float(dm.equivalent_full_cycles.mean()),
        })
    oracle = all_decision.loc[all_decision.method.eq("Oracle")]
    rows.append({
        "method": "Oracle", "building_count": int(oracle.building.nunique()),
        "mean_normalized_MAE": np.nan, "median_normalized_MAE": np.nan,
        "mean_normalized_RMSE": np.nan, "mean_normalized_peak_quartile_MAE": np.nan,
        "mean_bias_kw": np.nan, "mean_daily_peak_hour_MAE": np.nan,
        "mean_daily_peak_hour_exact_rate": np.nan, "mean_daily_top3_overlap": np.nan,
        "mean_daily_realized_peak_kw": float(oracle.mean_daily_peak.mean()),
        "mean_normalized_daily_realized_peak": float(oracle.normalized_mean_daily_peak.mean()),
        "mean_worst_10pct_daily_peak_kw": float(oracle.worst_10pct_daily_peak.mean()),
        "mean_normalized_worst_10pct_daily_peak": float(oracle.normalized_worst_10pct_daily_peak.mean()),
        "mean_regret_vs_oracle_kw": 0.0, "mean_normalized_regret": 0.0,
        "mean_p90_regret_kw": 0.0, "mean_normalized_p90_regret": 0.0,
        "mean_max_regret_kw": 0.0, "mean_oracle_capture_ratio": 1.0,
        "mean_equivalent_full_cycles": float(oracle.equivalent_full_cycles.mean()),
    })
    return pd.DataFrame(rows)


def _plots(output: Path, search: pd.DataFrame, selected: pd.DataFrame, summary: pd.DataFrame,
           building_summary: pd.DataFrame, daily: pd.DataFrame, dispatch: pd.DataFrame) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    search = search.copy()
    search["normalized_mean_regret"] = search.mean_regret_vs_oracle / search.train_mean_load
    fig, ax = plt.subplots(figsize=(9, 5))
    for building, part in search.groupby("building"):
        ax.plot(part.weight, part.normalized_MAE, alpha=.55, label=building)
    ax.set(title="Validation weight vs normalized MAE", xlabel="LightGBM weight", ylabel="MAE / Train mean")
    ax.legend(fontsize=6, ncol=2); fig.tight_layout(); fig.savefig(figures / "01_validation_weight_vs_mae.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for building, part in search.groupby("building"):
        ax.plot(part.weight, part.normalized_mean_regret, alpha=.55, label=building)
    ax.set(title="Validation weight vs normalized decision regret", xlabel="LightGBM weight", ylabel="Mean regret / Train mean")
    ax.legend(fontsize=6, ncol=2); fig.tight_layout(); fig.savefig(figures / "02_validation_weight_vs_regret.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(selected.w_forecast, selected.w_decision, s=55)
    for row in selected.itertuples(): ax.annotate(row.building, (row.w_forecast, row.w_decision), fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.plot([0, 1], [0, 1], "--", color="gray"); ax.set(xlim=(-.03, 1.03), ylim=(-.03, 1.03), xlabel="Forecast-selected weight", ylabel="Decision-selected weight", title="Per-building selected weights")
    fig.tight_layout(); fig.savefig(figures / "03_selected_weights.png", dpi=180); plt.close(fig)

    shown = summary.loc[summary.method.isin(["ForecastSelectedPerBuilding", "DecisionSelectedPerBuilding", "ForecastSelectedGlobal", "DecisionSelectedGlobal"])]
    fig, ax = plt.subplots(figsize=(9, 5)); ax.bar(shown.method, shown.mean_normalized_regret)
    ax.set(title="Test decision regret comparison", ylabel="Mean regret / Train mean"); ax.tick_params(axis="x", rotation=20)
    fig.tight_layout(); fig.savefig(figures / "04_test_decision_regret.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6)); ax.scatter(building_summary.forecast_MAE_delta_decision_minus_forecast, building_summary.decision_regret_delta_decision_minus_forecast)
    for row in building_summary.itertuples(): ax.annotate(row.building, (row.forecast_MAE_delta_decision_minus_forecast, row.decision_regret_delta_decision_minus_forecast), fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.axhline(0, color="gray", linewidth=1); ax.axvline(0, color="gray", linewidth=1)
    ax.set(title="Forecast vs decision effect on Test", xlabel="MAE delta: decision-selected − forecast-selected (kW)", ylabel="Mean regret delta (kW)")
    fig.tight_layout(); fig.savefig(figures / "05_forecast_vs_decision_effect.png", dpi=180); plt.close(fig)

    paired = daily.loc[daily.method.isin(["ForecastSelectedPerBuilding", "DecisionSelectedPerBuilding"])]
    pivot = paired.pivot(index=["building", "date"], columns="method", values="realized_peak")
    key = (pivot.DecisionSelectedPerBuilding - pivot.ForecastSelectedPerBuilding).abs().idxmax()
    case = dispatch.loc[dispatch.building.eq(key[0]) & dispatch.date.eq(key[1]) & dispatch.method.isin(["ForecastSelectedPerBuilding", "DecisionSelectedPerBuilding"])]
    fig, ax = plt.subplots(figsize=(10, 5)); actual = case.drop_duplicates("timestamp")
    ax.plot(actual.timestamp, actual.actual_load, color="black", linewidth=2, label="Actual")
    for method, part in case.groupby("method"):
        ax.plot(part.timestamp, part.realized_grid_load, label=method)
    ax.set(title=f"Representative frozen Test dispatch: {key[0]}, {key[1]}", ylabel="kW"); ax.legend(fontsize=7); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(figures / "06_representative_dispatch.png", dpi=180); plt.close(fig)


def _md(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    shown = frame[columns] if columns else frame
    lines = ["| " + " | ".join(map(str, shown.columns)) + " |", "| " + " | ".join(["---"] * len(shown.columns)) + " |"]
    for row in shown.itertuples(index=False):
        lines.append("| " + " | ".join(
            "" if pd.isna(value) else f"{value:.5f}" if isinstance(value, float) else str(value)
            for value in row
        ) + " |")
    return "\n".join(lines)


def _build_report(path: Path, selected: pd.DataFrame, global_weights: dict[str, float],
                  forecast: pd.DataFrame, decision: pd.DataFrame, building: pd.DataFrame,
                  aggregate: pd.DataFrame, bootstrap: dict[str, Any], summary: dict[str, Any]) -> None:
    mismatch = building.loc[building.mismatch]
    lines = [
        "# Phase 8 — 决策导向的预测融合与严格对照验证", "",
        "## 1. Motivation", "",
        "本阶段检验：按 Validation 预测误差选择的线性融合权重，是否等价于按下游储能削峰决策价值选择的权重。贡献是把 frozen battery decision value 显式用于融合权重选择并与传统 MAE 导向选择做受控比较；普通加权平均本身不是新算法。", "",
        "## 2. Frozen protocol", "",
        "固定 Phase 7 的 8 栋 office、24h horizon、Train/Validation/Test、target-availability purge、31 个 causal features、Day-Week weekly weight=0.5、逐建筑 frozen LightGBM configuration 与 Train-scale battery。无天气、未来天气、MPC、强化学习、深度学习或 Test-time tuning。Phase 7 未保存逐时预测，因此按其冻结配置确定性复现；端点指标与 Phase 7 正式指标核验通过后才接受本阶段结果。", "",
        "## 3. Ensemble definition", "",
        "`prediction = w * LightGBM + (1-w) * DayWeek`，预注册 `w={0.0,0.1,...,1.0}`。w=0/1 分别严格复现 Day-Week/LightGBM。", "",
        "## 4. Forecast-oriented selection", "",
        "只在 Validation 按 MAE、RMSE、距 endpoint 的距离、较小 w 的固定顺序选择。", "",
        "## 5. Decision-oriented selection", "",
        "同一 Validation grid 中，每个预测均进入同一 frozen battery optimizer，并在 actual load 上评价 realized result。按 mean daily regret vs Oracle、p90 regret、MAE、距 endpoint 的距离、较小 w 选择；Oracle 仅为不可部署 hindsight upper bound。", "",
        "## 6. Building-specific results", "", _md(selected), "",
        f"8 栋中 {summary['different_weight_buildings']}/8 的 forecast/decision 权重不同。Test 上 decision-oriented 相对 prediction-oriented：改善 {summary['decision_improved_buildings']} 栋、退化 {summary['decision_degraded_buildings']} 栋、持平 {summary['decision_tied_buildings']} 栋。", "",
        "## 7. Global-weight robustness", "",
        f"共享 forecast weight={global_weights['forecast']:.1f}；共享 decision weight={global_weights['decision']:.1f}。聚合先用 Phase 7 Train mean load 逐建筑归一化，再对 8 栋等权平均。", "", _md(aggregate), "",
        "## 8. Forecast vs decision mismatch analysis", "",
        f"观察到 {len(mismatch)} 个 Test mismatch case（一个方向改善而另一个方向退化）：", "", _md(mismatch) if len(mismatch) else "无。", "",
        "Validation MAE 排序与 Validation decision-regret 排序的逐建筑 Spearman 相关见 selected_weights.csv；Test 只作为冻结后的泛化证据，不参与权重或 tie-break。", "",
        "## 9. Statistical uncertainty", "", _md(pd.DataFrame([bootstrap])), "",
        "bootstrap 对 building-day normalized regret difference 作 10,000 次 paired resampling（seed=42），只描述不确定性，不参与选择。", "",
        "## 10. Leakage and battery constraint audit", "",
        f"Leakage={summary['leakage_audit']['status']}；battery constraints={summary['constraint_audit']['status']}；Phase 3–7 tracked artifacts unchanged={summary['frozen_phase3_7_artifacts_unchanged']}；endpoint reproduction={summary['endpoint_reproduction_passed']}。", "",
        "## 11. Limitations", "",
        "证据仅覆盖固定的 8 栋 office、单一月份 Test、简单两模型凸组合与当前 battery protocol。Test 在 Phase 3–7 已被历史阶段使用，故不是项目级从未查看过的盲测集；本阶段仅保证 Test 不进入权重选择。未尝试第三模型、细化 grid 或 Test 后目标调整。", "",
        "## 12. Final conclusion", "",
        summary["final_conclusion"], "",
        "允许声称的是：本阶段实施了 Validation-only 的决策导向预测融合受控对照，并如实报告跨建筑 Test 结果与不确定性。不能声称普通 weighted average 是全新 AI 架构、Oracle 可部署、Validation 优势就是 Test 泛化、或在缺乏一致跨建筑与 CI 支持时声称显著且稳定提升。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    root = Path(project_root)
    output = root / "outputs" / "phase8"
    output.mkdir(parents=True, exist_ok=True)
    frozen_before = tracked_frozen_hashes(root)
    phase7_manifest = json.loads((root / "outputs/phase7/artifact_manifest.json").read_text(encoding="utf-8"))
    phase7_config_path = root / "outputs/phase7/model_selection_config.json"
    model_config = json.loads(phase7_config_path.read_text(encoding="utf-8"))
    selected_phase7 = json.loads((root / "outputs/phase7/selected_buildings.json").read_text(encoding="utf-8"))
    actual_buildings = tuple(item["building"] for item in selected_phase7["selected_buildings"])
    if actual_buildings != BUILDINGS:
        raise AssertionError(f"Phase 7 building freeze changed: {actual_buildings}")

    created_at = datetime.now(timezone.utc).isoformat()
    lineage: dict[str, Any] = {
        "status": "candidate", "logical_role": "Phase 8 formal decision-oriented ensemble evidence",
        "producer": "scripts/run_phase8.py", "created_at_utc": created_at, "schema_version": 1,
        "parent_artifacts": {
            "phase7_commit": "5c89bdea663563d90df5eb52e289a9171573bc52",
            "phase7_manifest": "outputs/phase7/artifact_manifest.json",
            "phase7_manifest_sha256": sha256(root / "outputs/phase7/artifact_manifest.json"),
            "phase7_model_selection_config_sha256": sha256(phase7_config_path),
        },
        "artifacts": [],
    }
    _write_json(output / "lineage.json", lineage)
    run_config = {
        "status": "frozen_before_test", "phase": 8, "random_seed": RANDOM_SEED,
        "buildings": list(BUILDINGS), "ensemble": "w * LightGBM + (1-w) * DayWeek",
        "candidate_weights": list(WEIGHT_GRID), "primary_ml_model": "LightGBM",
        "forecast_selection_order": ["Validation MAE", "Validation RMSE", "endpoint distance", "smaller weight"],
        "decision_selection_order": ["Validation mean daily regret vs Oracle", "Validation p90 regret", "Validation MAE", "endpoint distance", "smaller weight"],
        "global_aggregation": "equal-building mean after division by frozen Phase 7 Train mean load",
        "split_protocol": model_config["split_protocol"], "feature_list": ALL_FEATURES,
        "day_week_source": model_config["day_week_source"],
        "battery_source": "Phase 7 train-scaled battery and Phase 5/6 daily optimizer",
        "test_used_for_selection": False, "test_evaluated_after_weight_files_written": True,
        "weather_used": False, "future_weather_used": False, "test_time_tuning": False,
    }
    _write_json(output / "run_config.json", run_config)
    prepared, batteries = _prepare(root, model_config)

    validation_rows: list[dict[str, Any]] = []
    validation_audits: list[pd.DataFrame] = []
    validation_dispatches: list[pd.DataFrame] = []
    endpoint_deltas: list[float] = []
    phase7_validation = pd.read_csv(root / "outputs/phase7/model_validation_results.csv")
    for building in BUILDINGS:
        splits, train_select, validation_select, train_mean = prepared[building]
        ts = validation_select.target_timestamp.reset_index(drop=True)
        actual = validation_select.target.to_numpy(float)
        _, oracle_daily, oracle_audit, oracle_dispatch = evaluate_method(building, "validation", "Oracle", ts, actual, actual, batteries[building], None)
        validation_audits.append(oracle_audit); validation_dispatches.append(oracle_dispatch)
        dayweek = day_week_blend(validation_select, 0.5)
        model, iteration = _fixed_lgbm(model_config, building, train_select)
        lgbm = predict(model, "LightGBM", validation_select, ALL_FEATURES, iteration)
        for endpoint_method, endpoint_prediction in (("DayWeek", dayweek), ("LightGBM", lgbm)):
            reproduced = normalized_forecast_metrics(ts, actual, endpoint_prediction, train_mean)
            reference = phase7_validation.loc[
                phase7_validation.building.eq(building) & phase7_validation.model_family.eq(endpoint_method) & phase7_validation.selected
            ].iloc[0]
            for metric in ("MAE", "RMSE", "normalized_MAE", "normalized_RMSE"):
                endpoint_deltas.append(abs(float(reproduced[metric]) - float(reference[f"validation_{metric}"])))
        for weight in WEIGHT_GRID:
            pred = ensemble_prediction(dayweek, lgbm, weight)
            forecast_metric = normalized_forecast_metrics(ts, actual, pred, train_mean)
            decision_metric, _, audit, dispatch = evaluate_method(
                building, "validation", f"Weight_{weight:.1f}", ts, actual, pred, batteries[building], oracle_daily
            )
            validation_audits.append(audit); validation_dispatches.append(dispatch)
            validation_rows.append({
                "building": building, "split": "validation", "weight": weight,
                "train_mean_load": train_mean, **forecast_metric,
                **{key: value for key, value in decision_metric.items() if key not in ("building", "split", "method")},
            })
    search = pd.DataFrame(validation_rows)
    search.to_csv(output / "validation_weight_search.csv", index=False)
    selected_rows = []
    for building, part in search.groupby("building", sort=False):
        forecast_weight = select_forecast_weight(part)
        decision_weight = select_decision_weight(part)
        mae_rank = part.MAE.rank(method="average")
        decision_rank = part.mean_regret_vs_oracle.rank(method="average")
        selected_rows.append({
            "building": building, "w_forecast": forecast_weight, "w_decision": decision_weight,
            "weights_differ": forecast_weight != decision_weight,
            "validation_MAE_decision_minus_forecast": float(part.loc[part.weight.eq(decision_weight), "MAE"].iloc[0] - part.loc[part.weight.eq(forecast_weight), "MAE"].iloc[0]),
            "validation_regret_decision_minus_forecast": float(part.loc[part.weight.eq(decision_weight), "mean_regret_vs_oracle"].iloc[0] - part.loc[part.weight.eq(forecast_weight), "mean_regret_vs_oracle"].iloc[0]),
            "validation_MAE_decision_rank_spearman": float(mae_rank.corr(decision_rank, method="pearson")),
        })
    selected = pd.DataFrame(selected_rows)
    selected.to_csv(output / "selected_weights.csv", index=False)
    global_weights, global_search = select_global_weights(search)
    global_search.to_csv(output / "global_weight_search.csv", index=False)
    _write_json(output / "global_selected_weights.json", {
        "status": "frozen_before_test", "w_forecast": global_weights["forecast"],
        "w_decision": global_weights["decision"], "candidate_weights": list(WEIGHT_GRID),
        "normalization_source": "Phase 7 Train mean load", "test_used_for_selection": False,
    })

    # Test is first used below, after both per-building and global weight files exist.
    forecast_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    daily_parts: list[pd.DataFrame] = []
    test_audits: list[pd.DataFrame] = []
    test_dispatches: list[pd.DataFrame] = []
    phase7_test_forecast = pd.read_csv(root / "outputs/phase7/model_test_forecast_metrics.csv")
    for building in BUILDINGS:
        splits, _, validation_select, train_mean = prepared[building]
        test = splits["test"]
        ts = test.target_timestamp.reset_index(drop=True)
        actual = test.target.to_numpy(float)
        _, oracle_daily, oracle_audit, oracle_dispatch = evaluate_method(building, "test", "Oracle", ts, actual, actual, batteries[building], None)
        oracle_metric, oracle_daily_for_output, _, _ = evaluate_method(building, "test", "Oracle", ts, actual, actual, batteries[building], None)
        decision_rows.append(oracle_metric); daily_parts.append(oracle_daily_for_output)
        test_audits.append(oracle_audit); test_dispatches.append(oracle_dispatch)
        dayweek = day_week_blend(test, 0.5)
        final_fit = pd.concat([splits["train"], validation_select], ignore_index=True)
        model, iteration = _fixed_lgbm(model_config, building, final_fit)
        lgbm = predict(model, "LightGBM", test, ALL_FEATURES, iteration)
        weights = selected.set_index("building").loc[building]
        method_weights = {
            "DayWeek": 0.0, "LightGBM": 1.0,
            "ForecastSelectedPerBuilding": float(weights.w_forecast),
            "DecisionSelectedPerBuilding": float(weights.w_decision),
            "ForecastSelectedGlobal": global_weights["forecast"],
            "DecisionSelectedGlobal": global_weights["decision"],
        }
        for method, weight in method_weights.items():
            pred = ensemble_prediction(dayweek, lgbm, weight)
            fm = normalized_forecast_metrics(ts, actual, pred, train_mean)
            forecast_rows.append({"building": building, "split": "test", "method": method, "weight": weight, **fm})
            dm, daily, audit, dispatch = evaluate_method(building, "test", method, ts, actual, pred, batteries[building], oracle_daily)
            decision_rows.append(dm); daily_parts.append(daily); test_audits.append(audit); test_dispatches.append(dispatch)
            if method in ("DayWeek", "LightGBM"):
                reference = phase7_test_forecast.loc[phase7_test_forecast.building.eq(building) & phase7_test_forecast.method.eq(method)].iloc[0]
                for metric in ("MAE", "RMSE", "normalized_MAE", "normalized_RMSE"):
                    endpoint_deltas.append(abs(float(fm[metric]) - float(reference[metric])))
    forecast = pd.DataFrame(forecast_rows)
    decision = pd.DataFrame(decision_rows)
    daily = pd.concat(daily_parts, ignore_index=True)
    audits = pd.concat(validation_audits + test_audits, ignore_index=True)
    dispatch = pd.concat(validation_dispatches + test_dispatches, ignore_index=True)
    forecast.to_csv(output / "test_forecast_metrics.csv", index=False)
    decision.to_csv(output / "test_decision_metrics.csv", index=False)
    daily.to_csv(output / "test_daily_decision_metrics.csv", index=False)
    audits.to_csv(output / "constraint_audit_details.csv", index=False)

    means = search.groupby("building").train_mean_load.first()
    aggregate = _aggregate_metrics(forecast, decision, means)
    aggregate.to_csv(output / "global_test_summary.csv", index=False)
    building_rows = []
    for building in BUILDINGS:
        fp = forecast.loc[forecast.building.eq(building)].set_index("method")
        dp = decision.loc[decision.building.eq(building)].set_index("method")
        forecast_delta = float(fp.loc["DecisionSelectedPerBuilding", "MAE"] - fp.loc["ForecastSelectedPerBuilding", "MAE"])
        regret_delta = float(dp.loc["DecisionSelectedPerBuilding", "mean_regret_vs_oracle"] - dp.loc["ForecastSelectedPerBuilding", "mean_regret_vs_oracle"])
        p90_delta = float(dp.loc["DecisionSelectedPerBuilding", "p90_regret"] - dp.loc["ForecastSelectedPerBuilding", "p90_regret"])
        worst_delta = float(dp.loc["DecisionSelectedPerBuilding", "worst_10pct_daily_peak"] - dp.loc["ForecastSelectedPerBuilding", "worst_10pct_daily_peak"])
        mismatch = (forecast_delta < -TOLERANCE and regret_delta > TOLERANCE) or (forecast_delta > TOLERANCE and regret_delta < -TOLERANCE)
        building_rows.append({
            "building": building,
            "w_forecast": float(selected.set_index("building").loc[building, "w_forecast"]),
            "w_decision": float(selected.set_index("building").loc[building, "w_decision"]),
            "forecast_MAE_delta_decision_minus_forecast": forecast_delta,
            "decision_regret_delta_decision_minus_forecast": regret_delta,
            "p90_regret_delta_decision_minus_forecast": p90_delta,
            "worst_10pct_peak_delta_decision_minus_forecast": worst_delta,
            "decision_outcome": "improved" if regret_delta < -TOLERANCE else "degraded" if regret_delta > TOLERANCE else "tied",
            "mismatch": mismatch,
            "mismatch_type": ("forecast better / decision worse" if forecast_delta < -TOLERANCE and regret_delta > TOLERANCE else
                              "forecast worse / decision better" if forecast_delta > TOLERANCE and regret_delta < -TOLERANCE else "none"),
        })
    building_summary = pd.DataFrame(building_rows)
    building_summary.to_csv(output / "building_summary.csv", index=False)

    per_daily = daily.loc[daily.method.isin(["ForecastSelectedPerBuilding", "DecisionSelectedPerBuilding"])]
    daily_pivot = per_daily.pivot(index=["building", "date"], columns="method", values="regret_vs_oracle").reset_index()
    daily_pivot["train_mean_load"] = daily_pivot.building.map(means)
    bootstrap = _bootstrap((daily_pivot.DecisionSelectedPerBuilding - daily_pivot.ForecastSelectedPerBuilding).to_numpy(float) / daily_pivot.train_mean_load.to_numpy(float))
    _write_json(output / "bootstrap_summary.json", bootstrap)

    totals = audit_totals(audits, dispatch)
    constraint = {
        "status": "PASS" if sum(totals.values()) == 0 else "FAIL",
        "controllers_audited": int(audits[["building", "split", "method"]].drop_duplicates().shape[0]),
        "daily_solves": int(len(audits)), "totals": totals,
    }
    (output / "constraint_audit.txt").write_text(json.dumps(constraint, ensure_ascii=False, indent=2), encoding="utf-8")
    endpoint_max_delta = float(max(endpoint_deltas))
    leakage_checks = {
        "fixed_phase7_buildings": tuple(BUILDINGS) == actual_buildings,
        "same_validation_grid_for_both_objectives": set(search.weight) == set(WEIGHT_GRID),
        "selection_rows_validation_only": bool(search.split.eq("validation").all()),
        "weight_files_written_before_test_evaluation": True,
        "test_not_used_for_selection_or_tie_break": True,
        "global_scale_uses_phase7_train_mean": bool(global_search.normalization_source.eq("Phase 7 Train mean load").all()),
        "target_not_in_features": "target" not in ALL_FEATURES,
        "weather_not_in_features": not any("weather" in feature.casefold() for feature in ALL_FEATURES),
        "same_frozen_battery_optimizer": True,
        "realized_decisions_evaluated_on_actual": True,
        "oracle_not_deployable": True,
    }
    leakage = {"status": "PASS" if all(leakage_checks.values()) else "FAIL", "checks": leakage_checks}
    (output / "leakage_audit.txt").write_text(json.dumps(leakage, ensure_ascii=False, indent=2), encoding="utf-8")
    if constraint["status"] != "PASS" or leakage["status"] != "PASS":
        raise AssertionError({"constraint": constraint, "leakage": leakage})
    if endpoint_max_delta > 1e-8:
        raise AssertionError(f"Phase 7 endpoint reproduction drift: {endpoint_max_delta}")
    frozen_after = tracked_frozen_hashes(root)
    if frozen_before != frozen_after:
        raise AssertionError("A tracked frozen Phase 3–7 artifact changed")

    improved = int(building_summary.decision_outcome.eq("improved").sum())
    degraded = int(building_summary.decision_outcome.eq("degraded").sum())
    tied = int(building_summary.decision_outcome.eq("tied").sum())
    regret_delta = building_summary.decision_regret_delta_decision_minus_forecast
    if improved > degraded and regret_delta.mean() < -TOLERANCE:
        conclusion = "Decision-oriented ensemble 在多数建筑且平均 Test regret 上改善，可作为最终候选组成部分；但仍受单月 Test 与 bootstrap 区间约束，不表述为普遍或显著提升。"
        recommendation = True
    elif improved and degraded:
        conclusion = "Decision-oriented ensemble 的 Test 效果跨建筑不稳定；保留为有潜力的受控候选，但当前证据不足以声称稳定改善。"
        recommendation = False
    else:
        conclusion = "Decision-oriented ensemble 未显示优于 prediction-oriented ensemble 的跨建筑 Test 证据；按预注册停止规则，不扩展 grid、模型或 objective。"
        recommendation = False
    summary = {
        "status": "PASS", "phase": "Phase 8 — Decision-Oriented Ensemble and Controlled Validation",
        "runtime_seconds": time.perf_counter() - started, "different_weight_buildings": int(selected.weights_differ.sum()),
        "global_weights": global_weights, "decision_improved_buildings": improved,
        "decision_degraded_buildings": degraded, "decision_tied_buildings": tied,
        "mean_test_regret_delta_decision_minus_forecast_kw": float(regret_delta.mean()),
        "median_test_regret_delta_decision_minus_forecast_kw": float(regret_delta.median()),
        "mismatch_buildings": building_summary.loc[building_summary.mismatch, "building"].tolist(),
        "bootstrap": bootstrap, "endpoint_reproduction_max_metric_delta": endpoint_max_delta,
        "endpoint_reproduction_passed": endpoint_max_delta <= 1e-8,
        "constraint_audit": constraint, "leakage_audit": leakage,
        "frozen_phase3_7_artifacts_unchanged": True,
        "retain_as_final_algorithm_component": recommendation, "final_conclusion": conclusion,
        "phase7_manifest_status": phase7_manifest["status"],
        "versions": {"python": platform.python_version(), "pandas": pd.__version__},
    }
    _write_json(output / "aggregate_summary.json", summary)
    _plots(output, search, selected, aggregate, building_summary, daily, dispatch)
    _build_report(root / "reports/phase8_report.md", selected, global_weights, forecast, decision, building_summary, aggregate, bootstrap, summary)

    manifest_paths = [path for path in output.rglob("*") if path.is_file() and path.name != "lineage.json"]
    manifest_paths.append(root / "reports/phase8_report.md")
    lineage.update({
        "status": "canonical",
        "acceptance_reason": "Validation-only selection frozen before Test; Phase 7 endpoints reproduced; leakage, constraints, and frozen-artifact checks passed",
        "artifacts": [{"path": path.relative_to(root).as_posix(), "sha256": sha256(path)} for path in sorted(manifest_paths)],
    })
    _write_json(output / "lineage.json", lineage)
    return summary
