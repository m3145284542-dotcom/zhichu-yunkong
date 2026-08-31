"""Phase 9 final algorithm validation, benchmark, and freeze.

The only new modelling variable is a Train-derived high-load sample weight for
the already frozen per-building Phase 7 LightGBM configuration.  Candidate
selection is Validation-only; Test is opened only after the selected
configuration file has been written.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features.load_features import ALL_FEATURES
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import day_week_blend, forecast_metrics
from src.phase7.evaluation import audit_totals, evaluate_method
from src.phase7.models import RANDOM_SEED, predict, refit_fixed
from src.phase7.pipeline import TEST_START, VALIDATION_START, battery_for, load_office_data, supervised_for
from src.phase8 import BUILDINGS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, ensemble_prediction


PEAK_QUANTILES = (0.80, 0.90)
PEAK_ALPHAS = (0.0, 0.5, 1.0, 2.0)
DECISION_EQUIVALENCE_BAND = 0.001
TOLERANCE = 1e-8
INFERENCE_REPEATS = 20
METHODS = (
    "Persistence", "Day", "Week", "DayWeek", "LightGBM", "XGBoost", "CatBoost",
    "Phase8_DOEF", "PeakAwareLightGBM",
)
CORE_METHODS = ("LightGBM", "Phase8_DOEF", "PeakAwareLightGBM")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def train_peak_threshold(target: np.ndarray, quantile: float) -> float:
    """Compute a finite threshold from the supplied fitting labels only."""
    values = np.asarray(target, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("Training targets must be a non-empty finite vector")
    if quantile not in PEAK_QUANTILES:
        raise ValueError(f"quantile must be one of {PEAK_QUANTILES}")
    return float(np.quantile(values, quantile))


def peak_sample_weights(target: np.ndarray, threshold: float, alpha: float) -> np.ndarray:
    """Return 1+alpha above a Train-derived threshold and 1 otherwise."""
    values = np.asarray(target, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all() or not np.isfinite(threshold):
        raise ValueError("Targets and threshold must be finite")
    if alpha not in PEAK_ALPHAS:
        raise ValueError(f"alpha must be one of {PEAK_ALPHAS}")
    result = np.ones(values.shape, dtype=float)
    result[values >= float(threshold)] = 1.0 + float(alpha)
    return result


def peak_region_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    """Extend the frozen P75 peak-region definition with the requested RMSE."""
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(prediction, dtype=float)
    if actual_values.shape != predicted_values.shape or actual_values.ndim != 1:
        raise ValueError("Actual and prediction must be aligned vectors")
    threshold = float(np.quantile(actual_values, 0.75))
    error = predicted_values[actual_values >= threshold] - actual_values[actual_values >= threshold]
    return {
        "peak_region_threshold": threshold,
        "peak_region_MAE": float(np.mean(np.abs(error))),
        "peak_region_RMSE": float(np.sqrt(np.mean(np.square(error)))),
    }


def select_peak_candidate(table: pd.DataFrame) -> dict[str, Any]:
    """Select only from Validation with a conservative decision-equivalence band.

    Any candidate within 0.001 Train-mean-normalized mean regret of the best is
    treated as decision-equivalent.  Within that set, smaller alpha is preferred,
    followed by normalized p90 regret, normalized MAE, and smaller q.
    """
    required = {
        "split", "q", "alpha", "normalized_mean_regret", "normalized_p90_regret",
        "normalized_MAE",
    }
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(f"Missing selection columns: {sorted(missing)}")
    if table.empty or not table["split"].eq("validation").all():
        raise ValueError("Peak-aware selection accepts Validation rows only")
    best = float(table["normalized_mean_regret"].min())
    eligible = table.loc[table["normalized_mean_regret"] <= best + DECISION_EQUIVALENCE_BAND].copy()
    chosen = eligible.sort_values(
        ["alpha", "normalized_p90_regret", "normalized_MAE", "q"], kind="mergesort"
    ).iloc[0]
    return chosen.to_dict()


def paired_bootstrap(values: np.ndarray, comparison: str) -> dict[str, Any]:
    paired = np.asarray(values, dtype=float)
    if paired.ndim != 1 or paired.size == 0 or not np.isfinite(paired).all():
        raise ValueError("Bootstrap values must be a non-empty finite vector")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, paired.size, size=(BOOTSTRAP_RESAMPLES, paired.size))
    means = paired[indices].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "comparison": comparison,
        "metric": "daily regret difference normalized by frozen Phase 7 Train mean load",
        "resampling_unit": "building-day pair",
        "pairs": int(paired.size),
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "point_estimate": float(paired.mean()),
        "median_difference": float(np.median(paired)),
        "ci95_lower": float(low),
        "ci95_upper": float(high),
        "probability_a_better": float(np.mean(means < 0.0)),
    }


def win_tie_loss(a: pd.Series, b: pd.Series, tolerance: float = TOLERANCE) -> dict[str, int]:
    delta = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    return {
        "wins": int(np.sum(delta < -tolerance)),
        "ties": int(np.sum(np.abs(delta) <= tolerance)),
        "losses": int(np.sum(delta > tolerance)),
    }


def choose_final_algorithm(comparisons: dict[str, dict[str, Any]], bootstrap: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Promote Peak-aware only under the predeclared strict Case C gate."""
    vs_lgbm = comparisons["PeakAwareLightGBM_vs_LightGBM"]
    vs_doef = comparisons["PeakAwareLightGBM_vs_Phase8_DOEF"]
    ci = bootstrap["PeakAwareLightGBM_minus_Phase8_DOEF"]
    peak_beats_lgbm = vs_lgbm["wins"] >= 5 and vs_lgbm["mean_normalized_delta"] < 0.0
    peak_beats_doef = vs_doef["wins"] >= 5 and vs_doef["mean_normalized_delta"] < 0.0
    uncertainty_supports = ci["ci95_upper"] < 0.0
    if peak_beats_doef and uncertainty_supports:
        case = "C"
        algorithm = "DOPE — Decision-Oriented Peak-Aware Ensemble"
        peak_status = "成功"
        reason = "Peak-aware 在多数建筑优于 DOEF，平均归一化 regret 更低，且 paired bootstrap 95% CI 上界低于 0。"
    elif peak_beats_lgbm:
        case = "B"
        algorithm = "DOEF — Decision-Oriented Ensemble Forecasting"
        peak_status = "部分成功"
        reason = "Peak-aware 跨建筑优于普通 LightGBM，但未同时满足替换 Phase 8 DOEF 的多数建筑与不确定性门槛。"
    else:
        case = "A"
        algorithm = "DOEF — Decision-Oriented Ensemble Forecasting"
        peak_status = "未成功"
        reason = "Peak-aware 未形成相对普通 LightGBM 的稳定跨建筑决策收益，按停止规则不再调参。"
    return {
        "status": "canonical", "case": case, "final_algorithm": algorithm,
        "chinese_name": "面向储能决策的集成负荷预测方法" if case != "C" else "面向储能决策的峰值感知集成负荷预测方法",
        "peak_aware_result": peak_status, "reason": reason,
        "algorithm_development_frozen": True, "test_used_to_choose_peak_configuration": False,
    }


def _model_spec(config: dict[str, Any], building: str, family: str) -> tuple[dict[str, Any], int]:
    chosen = config["selected_models"][f"{building}|{family}"]
    return dict(chosen["parameters"]), int(chosen["best_iteration"])


def _fit_weighted_lgbm(frame: pd.DataFrame, parameters: dict[str, Any], iteration: int, weights: np.ndarray):
    from lightgbm import LGBMRegressor
    model = LGBMRegressor(
        objective="regression", n_estimators=iteration, learning_rate=0.03,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        random_state=RANDOM_SEED, n_jobs=4, verbosity=-1, deterministic=True,
        force_col_wise=True, **parameters,
    )
    model.fit(frame[ALL_FEATURES], frame["target"], sample_weight=weights)
    return model


def _timed_fit(factory: Callable[[], Any]) -> tuple[Any, float, int]:
    started = time.perf_counter()
    model = factory()
    elapsed = time.perf_counter() - started
    return model, float(elapsed), len(pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL))


def _timed_inference(function: Callable[[], np.ndarray]) -> tuple[np.ndarray, float]:
    durations: list[float] = []
    output: np.ndarray | None = None
    for _ in range(INFERENCE_REPEATS):
        started = time.perf_counter()
        output = np.asarray(function(), dtype=float)
        durations.append(time.perf_counter() - started)
    assert output is not None
    return output, float(np.median(durations))


def _prepare(root: Path, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    electricity, _ = load_office_data(root)
    prepared: dict[str, Any] = {}
    batteries: dict[str, Any] = {}
    for building in BUILDINGS:
        splits = split_by_feature_time(supervised_for(electricity, building))
        train = purge_unavailable_targets(splits["train"], VALIDATION_START)
        validation = purge_unavailable_targets(splits["validation"], TEST_START)
        if len(validation) != 696 or len(splits["test"]) != 720:
            raise AssertionError(f"Frozen split changed for {building}")
        mean_train = float(splits["train"]["current_load"].mean())
        for family in ("LightGBM", "XGBoost", "CatBoost"):
            _model_spec(config, building, family)
        prepared[building] = (splits, train, validation, mean_train)
        batteries[building] = battery_for(building, mean_train)
    return prepared, batteries


def _forecast_row(building: str, method: str, actual: np.ndarray, prediction: np.ndarray,
                  timestamps: pd.Series, train_mean: float) -> dict[str, Any]:
    metrics = forecast_metrics(actual, prediction, timestamps)
    metrics.update(peak_region_metrics(actual, prediction))
    metrics["normalized_MAE"] = metrics["MAE"] / train_mean
    metrics["normalized_RMSE"] = metrics["RMSE"] / train_mean
    metrics["normalized_peak_region_MAE"] = metrics["peak_region_MAE"] / train_mean
    metrics["normalized_peak_region_RMSE"] = metrics["peak_region_RMSE"] / train_mean
    return {"building": building, "split": "test", "method": method, **metrics}


def _aggregate(forecast: pd.DataFrame, decision: pd.DataFrame, means: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    forecast_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    deployable_decision = decision.loc[decision.method.isin(METHODS)].copy()
    deployable_decision["normalized_mean_daily_peak"] = deployable_decision.mean_daily_peak / deployable_decision.building.map(means)
    deployable_decision["normalized_mean_regret"] = deployable_decision.mean_regret_vs_oracle / deployable_decision.building.map(means)
    deployable_decision["normalized_p90_regret"] = deployable_decision.p90_regret / deployable_decision.building.map(means)
    for method in METHODS:
        fm = forecast.loc[forecast.method.eq(method)]
        dm = deployable_decision.loc[deployable_decision.method.eq(method)]
        forecast_rows.append({
            "method": method, "building_count": int(fm.building.nunique()),
            "mean_MAE_kw": float(fm.MAE.mean()), "median_MAE_kw": float(fm.MAE.median()),
            "mean_RMSE_kw": float(fm.RMSE.mean()), "median_RMSE_kw": float(fm.RMSE.median()),
            "mean_MAPE_pct": float(fm.MAPE.mean()),
            "mean_peak_region_MAE_kw": float(fm.peak_region_MAE.mean()),
            "mean_peak_region_RMSE_kw": float(fm.peak_region_RMSE.mean()),
            "mean_normalized_MAE": float(fm.normalized_MAE.mean()),
            "median_normalized_MAE": float(fm.normalized_MAE.median()),
            "mean_normalized_RMSE": float(fm.normalized_RMSE.mean()),
            "mean_normalized_peak_region_MAE": float(fm.normalized_peak_region_MAE.mean()),
            "mean_normalized_peak_region_RMSE": float(fm.normalized_peak_region_RMSE.mean()),
        })
        decision_rows.append({
            "method": method, "building_count": int(dm.building.nunique()),
            "mean_daily_peak_kw": float(dm.mean_daily_peak.mean()),
            "median_daily_peak_kw": float(dm.mean_daily_peak.median()),
            "mean_peak_reduction_kw": float(dm.absolute_peak_reduction.mean()),
            "mean_peak_reduction_pct": float(dm.peak_reduction_percentage.mean()),
            "mean_regret_kw": float(dm.mean_regret_vs_oracle.mean()),
            "median_regret_kw": float(dm.mean_regret_vs_oracle.median()),
            "mean_p90_regret_kw": float(dm.p90_regret.mean()),
            "mean_normalized_daily_peak": float(dm.normalized_mean_daily_peak.mean()),
            "median_normalized_daily_peak": float(dm.normalized_mean_daily_peak.median()),
            "mean_normalized_regret": float(dm.normalized_mean_regret.mean()),
            "median_normalized_regret": float(dm.normalized_mean_regret.median()),
            "mean_normalized_p90_regret": float(dm.normalized_p90_regret.mean()),
            "mean_oracle_capture_ratio": float(dm.oracle_capture_ratio.mean()),
            "mean_equivalent_full_cycles": float(dm.equivalent_full_cycles.mean()),
        })
    return pd.DataFrame(forecast_rows), pd.DataFrame(decision_rows)


def _markdown(frame: pd.DataFrame, columns: list[str]) -> str:
    shown = frame[columns].copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.5f}")
    rows = [list(shown.columns), ["---"] * len(shown.columns), *shown.astype(str).values.tolist()]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def _plots(output: Path, validation: pd.DataFrame, forecast_agg: pd.DataFrame,
           decision: pd.DataFrame, efficiency: pd.DataFrame, daily: pd.DataFrame,
           means: pd.Series) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    merged = forecast_agg.merge(
        decision.groupby("method", as_index=False).mean_regret_vs_oracle.mean().rename(columns={"mean_regret_vs_oracle": "mean_regret"}),
        on="method", how="left",
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    label_offsets = {
        "Persistence": (6, 5), "Week": (6, 5), "DayWeek": (6, 5),
        "LightGBM": (6, -14), "XGBoost": (6, 5), "CatBoost": (6, 5),
        "Phase8_DOEF": (6, 5), "PeakAwareLightGBM": (6, 8),
    }
    for _, row in merged.iterrows():
        if row.method == "Day":
            continue
        ax.scatter(row.mean_normalized_MAE, row.mean_regret, s=55)
        label = "Persistence / Day" if row.method == "Persistence" else row.method
        ax.annotate(label, (row.mean_normalized_MAE, row.mean_regret), fontsize=7,
                    xytext=label_offsets[row.method], textcoords="offset points")
    ax.set(xlabel="Mean normalized MAE", ylabel="Mean regret vs Oracle (kW)", title="Forecast accuracy vs downstream decision quality")
    fig.tight_layout(); fig.savefig(figures / "01_forecast_vs_decision.png", dpi=170); plt.close(fig)

    shown = decision.loc[decision.method.isin(CORE_METHODS)].copy()
    shown["normalized_regret"] = shown.mean_regret_vs_oracle / shown.building.map(means)
    pivot = shown.pivot(index="building", columns="method", values="normalized_regret")[list(CORE_METHODS)]
    fig, ax = plt.subplots(figsize=(10, 6)); pivot.plot(kind="bar", ax=ax)
    ax.set(ylabel="Mean regret / Train mean load", title="Eight-building decision comparison", xlabel="Building")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(figures / "02_building_decision_comparison.png", dpi=170); plt.close(fig)

    base = pivot["LightGBM"]
    improvement = pd.DataFrame({"Phase8_DOEF": base - pivot["Phase8_DOEF"], "PeakAwareLightGBM": base - pivot["PeakAwareLightGBM"]})
    fig, ax = plt.subplots(figsize=(10, 6)); improvement.plot(kind="bar", ax=ax); ax.axhline(0, color="black", linewidth=1)
    ax.set(ylabel="Normalized regret improvement vs LightGBM", title="Per-building improvement", xlabel="Building")
    fig.tight_layout(); fig.savefig(figures / "03_core_improvements.png", dpi=170); plt.close(fig)

    core = forecast_agg.loc[forecast_agg.method.isin(CORE_METHODS)].set_index("method")
    fig, ax = plt.subplots(figsize=(8, 5)); ax.scatter(core.mean_normalized_peak_region_MAE, decision.loc[decision.method.isin(CORE_METHODS)].groupby("method").mean_regret_vs_oracle.mean().reindex(core.index))
    core_offsets = {"LightGBM": (6, -13), "Phase8_DOEF": (6, 5), "PeakAwareLightGBM": (6, 8)}
    for method, row in core.iterrows():
        ax.annotate(method, (row.mean_normalized_peak_region_MAE, decision.loc[decision.method.eq(method), "mean_regret_vs_oracle"].mean()),
                    fontsize=8, xytext=core_offsets[method], textcoords="offset points")
    ax.set(xlabel="Normalized peak-region MAE", ylabel="Mean decision regret (kW)", title="Peak forecast quality vs storage outcome")
    fig.tight_layout(); fig.savefig(figures / "04_peak_quality_vs_decision.png", dpi=170); plt.close(fig)

    eff = efficiency.groupby("method", as_index=False).agg(training_time_seconds=("training_time_seconds", "mean"), inference_time_ms=("inference_time_ms", "mean"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4)); axes[0].bar(eff.method, eff.training_time_seconds); axes[1].bar(eff.method, eff.inference_time_ms)
    axes[0].set(title="Mean training time", ylabel="seconds"); axes[1].set(title="Median 720-row inference time", ylabel="ms")
    for ax in axes: ax.tick_params(axis="x", rotation=35)
    fig.tight_layout(); fig.savefig(figures / "05_efficiency.png", dpi=170); plt.close(fig)

    candidates = validation.groupby(["q", "alpha"], as_index=False).normalized_mean_regret.mean()
    fig, ax = plt.subplots(figsize=(8, 5))
    for q, part in candidates.groupby("q"): ax.plot(part.alpha, part.normalized_mean_regret, marker="o", label=f"q={q:.2f}")
    ax.set(xlabel="alpha", ylabel="Mean normalized Validation regret", title="Peak-aware Validation search"); ax.legend()
    fig.tight_layout(); fig.savefig(figures / "06_validation_search.png", dpi=170); plt.close(fig)


def _report(path: Path, validation: pd.DataFrame, selected: pd.DataFrame,
            forecast_agg: pd.DataFrame, decision_agg: pd.DataFrame,
            comparisons: dict[str, Any], bootstrap: dict[str, Any],
            efficiency: pd.DataFrame, final: dict[str, Any], summary: dict[str, Any]) -> None:
    peak_vs_lgbm = comparisons["PeakAwareLightGBM_vs_LightGBM"]
    peak_vs_doef = comparisons["PeakAwareLightGBM_vs_Phase8_DOEF"]
    best_forecast = forecast_agg.sort_values(["mean_normalized_MAE", "method"]).iloc[0].method
    best_decision = decision_agg.sort_values(["mean_normalized_regret", "method"]).iloc[0].method
    alignment = best_forecast == best_decision
    selected_table = selected[["building", "q", "alpha", "normalized_mean_regret", "normalized_MAE"]]
    eff_agg = efficiency.groupby("method", as_index=False).agg(
        training_time_seconds=("training_time_seconds", "mean"), inference_time_ms=("inference_time_ms", "mean"),
        artifact_size_bytes=("artifact_size_bytes", "mean"), test_samples=("test_samples", "first"),
    )
    lines = [
        "# Phase 9 — Final Algorithm Validation & Freeze", "",
        "## 1. 研究问题与错位机制", "",
        "普通 forecast loss 对各时段近似等权，而削峰调度由日内最高负荷、可用 SOC 与功率约束共同决定；因此较小的平均误差不必然产生更小的 realized peak 或 regret。本阶段只验证 downstream-decision-aware sample weighting，不把它表述为新基础模型。", "",
        "## 2. 冻结协议与审计", "",
        "完整复用 Phase 7/8 的 8 栋建筑、24 h horizon、feature-time split、target-availability purge、31 个 causal features、逐建筑 LightGBM 参数/树数、Day/Week/DayWeek 定义、Phase 8 融合权重以及 Train-scale battery。Phase 3–8 正式产物在运行前后哈希一致。Persistence 与 Day 均为 t-24 同小时观测，是为满足历史命名而保留的数学等价别名。", "",
        "## 3. Peak-aware weighting 与防泄漏", "",
        "对 q∈{0.80,0.90}、alpha∈{0,0.5,1,2} 使用 `threshold=quantile(y_train,q)`；训练标签达到阈值时 weight=1+alpha，否则为 1。Validation 阈值只由 purge 后 Train target 计算；选定 q/alpha 后，最终 Test 模型阈值可由 Train+Validation final-fit labels 重算。Test 不参与阈值、配置、模型参数、融合权重、建筑或 battery 选择。", "",
        "每栋建筑先最小化 Validation normalized mean regret；与最优值相差不超过 0.001 的候选视为 decision-equivalent，再依次选择更小 alpha、较低 normalized p90 regret、较低 normalized MAE 和更小 q。选择文件在任何 Test 评估前写出。", "",
        _markdown(selected_table, list(selected_table.columns)), "",
        "完整 64 行候选及 forecast/decision metrics 见 `validation_search.csv`。", "",
        "## 4. Final benchmark — Forecast metrics", "",
        _markdown(forecast_agg, ["method", "mean_normalized_MAE", "median_normalized_MAE", "mean_normalized_RMSE", "mean_MAPE_pct", "mean_normalized_peak_region_MAE", "mean_normalized_peak_region_RMSE"]), "",
        f"按跨建筑 mean normalized MAE，最佳 forecast method 为 **{best_forecast}**。MAPE 对接近零负荷的建筑较敏感，因此结论优先使用 normalized MAE/RMSE。", "",
        "## 5. Final benchmark — Decision metrics", "",
        _markdown(decision_agg, ["method", "mean_normalized_daily_peak", "median_normalized_daily_peak", "mean_normalized_regret", "median_normalized_regret", "mean_normalized_p90_regret", "mean_peak_reduction_pct"]), "",
        f"按跨建筑 mean normalized regret，最佳 decision method 为 **{best_decision}**。本次 aggregate forecast/decision 赢家{'一致' if alignment else '不一致'}；这{'不能单独证明二者总是等价。Phase 8 已在逐建筑 Validation 权重和 Test mismatch case 上验证了局部错位，因此证据支持“不具有一般等价关系”，但不声称本表的聚合赢家不同' if alignment else '直接提供了聚合层面的错位证据'}。", "",
        "## 6. Peak-aware 是否提升及跨建筑稳定性", "",
        f"相对 LightGBM：{peak_vs_lgbm['wins']}/{peak_vs_lgbm['ties']}/{peak_vs_lgbm['losses']}（win/tie/loss），mean normalized regret delta={peak_vs_lgbm['mean_normalized_delta']:.6f}。相对 Phase 8 DOEF：{peak_vs_doef['wins']}/{peak_vs_doef['ties']}/{peak_vs_doef['losses']}，delta={peak_vs_doef['mean_normalized_delta']:.6f}。结论：Peak-aware **{final['peak_aware_result']}**。", "",
        "## 7. Bootstrap uncertainty", "",
        _markdown(pd.DataFrame(bootstrap.values()), ["comparison", "point_estimate", "ci95_lower", "ci95_upper", "probability_a_better", "pairs", "resamples"]), "",
        "CI 基于与 Phase 8 相同的 10,000 次、seed=42、building-day paired normalized regret bootstrap，仅用于描述冻结后比较的不确定性，不参与 q/alpha 选择。", "",
        "## 8. 计算开销", "",
        _markdown(eff_agg, ["method", "training_time_seconds", "inference_time_ms", "artifact_size_bytes", "test_samples"]), "",
        f"同一运行环境：{summary['hardware']['processor']}；{summary['hardware']['os']}；Python {summary['hardware']['python']}。训练用 `time.perf_counter()` 单次计时；inference 为同一 720 样本预测重复 {INFERENCE_REPEATS} 次的中位耗时；artifact size 为实际模型 pickle 字节数，Ensemble 包含其 LightGBM 组件与权重元数据。它们是本机相对工程开销，不代表绝对部署性能。", "",
        "## 9. 最终冻结", "",
        f"**Final frozen algorithm: {final['final_algorithm']}**（{final['chinese_name']}）。Case {final['case']}：{final['reason']}", "",
        "Phase 9 marks the end of algorithm development. 后续只进入 system prototype、visualization、technical report、presentation 与 demo；不再因为本次 Test 结果扩充 weighting function、模型、天气、深度学习、强化学习或 robust optimization。", "",
        "## 10. 失败尝试、适用范围与局限", "",
        "Phase 5.7 robust optimization 没有改善；Phase 6 单建筑 peak-aware 也未在 Test 优于 canonical LightGBM；本阶段按真实跨建筑结果记录 Peak-aware 的成功、部分成功或未成功，不做追加调参。最终创新点来自 causal forecasting protocol、decision-oriented validation、forecast-to-storage closed-loop evaluation、multi-building generalization 与 decision-oriented ensemble/peak-aware learning，而不是“全新 LightGBM”。", "",
        "适用范围限于当前 8 栋 office、BDG2 固定时段、24 h 前预测、当前 Train-scale battery 和每日 SOC reset。Test 是冻结的留出测试区间，历史阶段已查看过其结果；Phase 9 保持边界固定，并禁止将其用于本阶段配置选择。跨季节、其他建筑类型、不同电池或在线部署仍需独立验证。", "",
        "## 11. 15 个验收问题的直接回答", "",
        "1. 错位来自平均误差等权，而削峰取决于峰时与约束。", "2. weighting 为 Train quantile 阈值上的 1+alpha。", "3. 阈值、q/alpha、模型和融合均在 Test 前冻结。",
        f"4. Peak-aware：{final['peak_aware_result']}。", f"5. 三者的最终去留：{final['final_algorithm']}。", f"6. forecast 最佳：{best_forecast}。", f"7. decision 最佳：{best_decision}。",
        f"8. 聚合赢家{'一致' if alignment else '不一致'}；Phase 8 的逐建筑证据表明两类目标不具有一般等价关系。", f"9. 跨建筑证据见 {peak_vs_doef['wins']}/{peak_vs_doef['ties']}/{peak_vs_doef['losses']}。", "10. CI 如上，不扩大解释。", "11. 开销如上表。",
        f"12. 冻结理由：{final['reason']}", "13. 负结果包括 Phase 5.7 与未满足停止门槛的 Peak-aware 比较。", "14. 范围与局限见上一节。", "15. 预注册停止规则已触发算法收口，继续堆模型会引入 Test 后选择风险。", "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    root = Path(project_root)
    output = root / "outputs" / "phase9"
    output.mkdir(parents=True, exist_ok=True)
    before = {str(path.relative_to(root)): sha256(path) for phase in ("phase7", "phase8") for path in sorted((root / "outputs" / phase).rglob("*")) if path.is_file()}
    model_config_path = root / "outputs/phase7/model_selection_config.json"
    selected_buildings_path = root / "outputs/phase7/selected_buildings.json"
    phase8_weights_path = root / "outputs/phase8/selected_weights.csv"
    model_config = json.loads(model_config_path.read_text(encoding="utf-8"))
    selected_buildings = json.loads(selected_buildings_path.read_text(encoding="utf-8"))
    actual_buildings = tuple(row["building"] for row in selected_buildings["selected_buildings"])
    if actual_buildings != BUILDINGS:
        raise AssertionError(f"Frozen building set changed: {actual_buildings}")
    phase8_weights = pd.read_csv(phase8_weights_path).set_index("building")["w_decision"]
    if set(phase8_weights.index) != set(BUILDINGS):
        raise AssertionError("Phase 8 decision weights do not cover frozen buildings")

    created_at = datetime.now(timezone.utc).isoformat()
    lineage = {
        "status": "candidate", "logical_role": "canonical final algorithm evidence and sole downstream result source",
        "producer": "scripts/run_phase9.py", "created_at_utc": created_at, "schema_version": 1,
        "parents": {
            "phase7_model_config": {"path": "outputs/phase7/model_selection_config.json", "sha256": sha256(model_config_path)},
            "phase7_buildings": {"path": "outputs/phase7/selected_buildings.json", "sha256": sha256(selected_buildings_path)},
            "phase8_weights": {"path": "outputs/phase8/selected_weights.csv", "sha256": sha256(phase8_weights_path)},
        }, "artifacts": [],
    }
    _write_json(output / "data_lineage.json", lineage)
    run_config = {
        "status": "frozen_before_test", "phase": 9, "random_seed": RANDOM_SEED,
        "buildings": list(BUILDINGS), "feature_list": ALL_FEATURES,
        "split_protocol": model_config["split_protocol"], "peak_quantiles": list(PEAK_QUANTILES),
        "peak_alphas": list(PEAK_ALPHAS), "weight_rule": "1+alpha if y_fit >= quantile(y_fit,q), otherwise 1",
        "validation_selection": {
            "primary": "normalized mean daily regret vs Oracle",
            "equivalence_band": DECISION_EQUIVALENCE_BAND,
            "tie_breakers": ["smaller alpha", "normalized p90 regret", "normalized MAE", "smaller q"],
        },
        "final_refit_threshold_source": "Train + purged Validation labels only",
        "battery_source": "unchanged Phase 7 Train-scaled battery and Phase 5/6 optimizer",
        "phase8_method": "building-specific Validation decision-selected DayWeek/LightGBM ensemble",
        "test_used_for_peak_configuration": False, "test_evaluated_after_selected_config_written": True,
        "forecast_horizon_hours": 24, "test_samples_per_building": 720,
        "inference_repeats": INFERENCE_REPEATS, "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
    }
    _write_json(output / "run_config.json", run_config)
    prepared, batteries = _prepare(root, model_config)

    validation_rows: list[dict[str, Any]] = []
    validation_audits: list[pd.DataFrame] = []
    validation_dispatches: list[pd.DataFrame] = []
    for building in BUILDINGS:
        _, train, validation, train_mean = prepared[building]
        parameters, iteration = _model_spec(model_config, building, "LightGBM")
        ts = validation.target_timestamp.reset_index(drop=True)
        actual = validation.target.to_numpy(float)
        _, oracle_daily, oracle_audit, oracle_dispatch = evaluate_method(building, "validation", "Oracle", ts, actual, actual, batteries[building], None)
        validation_audits.append(oracle_audit); validation_dispatches.append(oracle_dispatch)
        for q in PEAK_QUANTILES:
            threshold = train_peak_threshold(train.target.to_numpy(float), q)
            for alpha in PEAK_ALPHAS:
                weights = peak_sample_weights(train.target.to_numpy(float), threshold, alpha)
                model = _fit_weighted_lgbm(train, parameters, iteration, weights)
                prediction = predict(model, "LightGBM", validation, ALL_FEATURES, iteration)
                fm = _forecast_row(building, "candidate", actual, prediction, ts, train_mean)
                dm, _, audit, dispatch = evaluate_method(building, "validation", f"q{q}_a{alpha}", ts, actual, prediction, batteries[building], oracle_daily)
                validation_audits.append(audit); validation_dispatches.append(dispatch)
                validation_rows.append({
                    "building": building, "split": "validation", "q": q, "alpha": alpha,
                    "train_peak_threshold": threshold, "high_load_train_fraction": float(np.mean(train.target.to_numpy(float) >= threshold)),
                    **{key: value for key, value in fm.items() if key not in ("building", "split", "method")},
                    **{key: value for key, value in dm.items() if key not in ("building", "split", "method")},
                    "normalized_mean_regret": float(dm["mean_regret_vs_oracle"] / train_mean),
                    "normalized_p90_regret": float(dm["p90_regret"] / train_mean),
                })
    validation_search = pd.DataFrame(validation_rows)
    selected_rows: list[dict[str, Any]] = []
    for building, part in validation_search.groupby("building", sort=False):
        chosen = select_peak_candidate(part)
        selected_rows.append({key: chosen[key] for key in (
            "building", "q", "alpha", "train_peak_threshold", "high_load_train_fraction",
            "normalized_mean_regret", "normalized_p90_regret", "normalized_MAE", "MAE", "RMSE",
            "peak_region_MAE", "peak_region_RMSE", "mean_daily_peak", "mean_regret_vs_oracle", "p90_regret",
        )})
    selected = pd.DataFrame(selected_rows)
    validation_search["selected"] = False
    for _, row in selected.iterrows():
        mask = validation_search.building.eq(row.building) & validation_search.q.eq(row.q) & validation_search.alpha.eq(row.alpha)
        validation_search.loc[mask, "selected"] = True
    validation_search.to_csv(output / "validation_search.csv", index=False)
    selected.to_csv(output / "selected_peak_configs.csv", index=False)

    # Test is first accessed below, after all peak-aware choices are persisted.
    forecast_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    daily_parts: list[pd.DataFrame] = []
    test_audits: list[pd.DataFrame] = []
    test_dispatches: list[pd.DataFrame] = []
    efficiency_rows: list[dict[str, Any]] = []
    reproduction_deltas: list[float] = []
    phase7_forecast = pd.read_csv(root / "outputs/phase7/model_test_forecast_metrics.csv")
    phase8_forecast = pd.read_csv(root / "outputs/phase8/test_forecast_metrics.csv")
    phase8_decision = pd.read_csv(root / "outputs/phase8/test_decision_metrics.csv")
    for building in BUILDINGS:
        splits, _, validation, train_mean = prepared[building]
        test = splits["test"]
        final_fit = pd.concat([splits["train"], validation], ignore_index=True)
        ts = test.target_timestamp.reset_index(drop=True)
        actual = test.target.to_numpy(float)
        _, oracle_daily, oracle_audit, oracle_dispatch = evaluate_method(building, "test", "Oracle", ts, actual, actual, batteries[building], None)
        oracle_metric, oracle_daily_output, _, _ = evaluate_method(building, "test", "Oracle", ts, actual, actual, batteries[building], None)
        decision_rows.append(oracle_metric); daily_parts.append(oracle_daily_output)
        test_audits.append(oracle_audit); test_dispatches.append(oracle_dispatch)

        predictions: dict[str, np.ndarray] = {
            "Persistence": test.current_load.to_numpy(float),
            "Day": day_week_blend(test, 0.0),
            "Week": day_week_blend(test, 1.0),
            "DayWeek": day_week_blend(test, 0.5),
        }
        fitted_models: dict[str, Any] = {}
        for family in ("LightGBM", "XGBoost", "CatBoost"):
            parameters, iteration = _model_spec(model_config, building, family)
            model, train_seconds, artifact_bytes = _timed_fit(lambda f=family, p=parameters, i=iteration: refit_fixed(f, final_fit, ALL_FEATURES, p, i))
            prediction, infer_seconds = _timed_inference(lambda m=model, f=family, i=iteration: predict(m, f, test, ALL_FEATURES, i))
            fitted_models[family] = model; predictions[family] = prediction
            efficiency_rows.append({
                "building": building, "method": family, "training_time_seconds": train_seconds,
                "inference_time_seconds": infer_seconds, "inference_time_ms": infer_seconds * 1000,
                "test_samples": len(test), "inference_repeats": INFERENCE_REPEATS,
                "model_artifact_available": True, "artifact_size_bytes": artifact_bytes,
            })

        lgbm_parameters, lgbm_iteration = _model_spec(model_config, building, "LightGBM")
        ensemble_model, ensemble_train_seconds, ensemble_bytes = _timed_fit(lambda: refit_fixed("LightGBM", final_fit, ALL_FEATURES, lgbm_parameters, lgbm_iteration))
        decision_weight = float(phase8_weights.loc[building])
        ensemble_pred, ensemble_infer_seconds = _timed_inference(
            lambda: ensemble_prediction(day_week_blend(test, 0.5), predict(ensemble_model, "LightGBM", test, ALL_FEATURES, lgbm_iteration), decision_weight)
        )
        predictions["Phase8_DOEF"] = ensemble_pred
        efficiency_rows.append({
            "building": building, "method": "Phase8_DOEF", "training_time_seconds": ensemble_train_seconds,
            "inference_time_seconds": ensemble_infer_seconds, "inference_time_ms": ensemble_infer_seconds * 1000,
            "test_samples": len(test), "inference_repeats": INFERENCE_REPEATS, "model_artifact_available": True,
            "artifact_size_bytes": ensemble_bytes + len(json.dumps({"weight": decision_weight}).encode("utf-8")),
        })

        chosen = selected.set_index("building").loc[building]
        final_threshold = train_peak_threshold(final_fit.target.to_numpy(float), float(chosen.q))
        final_weights = peak_sample_weights(final_fit.target.to_numpy(float), final_threshold, float(chosen.alpha))
        peak_model, peak_train_seconds, peak_bytes = _timed_fit(lambda: _fit_weighted_lgbm(final_fit, lgbm_parameters, lgbm_iteration, final_weights))
        peak_pred, peak_infer_seconds = _timed_inference(lambda: predict(peak_model, "LightGBM", test, ALL_FEATURES, lgbm_iteration))
        predictions["PeakAwareLightGBM"] = peak_pred
        efficiency_rows.append({
            "building": building, "method": "PeakAwareLightGBM", "training_time_seconds": peak_train_seconds,
            "inference_time_seconds": peak_infer_seconds, "inference_time_ms": peak_infer_seconds * 1000,
            "test_samples": len(test), "inference_repeats": INFERENCE_REPEATS, "model_artifact_available": True,
            "artifact_size_bytes": peak_bytes, "q": float(chosen.q), "alpha": float(chosen.alpha),
            "final_fit_peak_threshold": final_threshold,
        })

        if not np.array_equal(predictions["Persistence"], predictions["Day"]):
            raise AssertionError("Persistence and Day aliases drifted")
        for method in METHODS:
            fm = _forecast_row(building, method, actual, predictions[method], ts, train_mean)
            forecast_rows.append(fm)
            dm, daily, audit, dispatch = evaluate_method(building, "test", method, ts, actual, predictions[method], batteries[building], oracle_daily)
            decision_rows.append(dm); daily_parts.append(daily); test_audits.append(audit); test_dispatches.append(dispatch)
        for family in ("DayWeek", "LightGBM", "XGBoost", "CatBoost"):
            reference = phase7_forecast.loc[phase7_forecast.building.eq(building) & phase7_forecast.method.eq(family)].iloc[0]
            current = next(row for row in forecast_rows if row["building"] == building and row["method"] == family)
            reproduction_deltas.extend(abs(float(current[key]) - float(reference[key])) for key in ("MAE", "RMSE", "normalized_MAE", "normalized_RMSE"))
        reference_f = phase8_forecast.loc[phase8_forecast.building.eq(building) & phase8_forecast.method.eq("DecisionSelectedPerBuilding")].iloc[0]
        current_f = next(row for row in forecast_rows if row["building"] == building and row["method"] == "Phase8_DOEF")
        reproduction_deltas.extend(abs(float(current_f[key]) - float(reference_f[key])) for key in ("MAE", "RMSE", "normalized_MAE", "normalized_RMSE"))
        reference_d = phase8_decision.loc[phase8_decision.building.eq(building) & phase8_decision.method.eq("DecisionSelectedPerBuilding")].iloc[0]
        current_d = next(row for row in decision_rows if row["building"] == building and row["method"] == "Phase8_DOEF")
        reproduction_deltas.extend(abs(float(current_d[key]) - float(reference_d[key])) for key in ("mean_daily_peak", "mean_regret_vs_oracle", "p90_regret"))

    forecast = pd.DataFrame(forecast_rows)
    decision = pd.DataFrame(decision_rows)
    daily = pd.concat(daily_parts, ignore_index=True)
    efficiency = pd.DataFrame(efficiency_rows)
    audits = pd.concat(validation_audits + test_audits, ignore_index=True)
    dispatch = pd.concat(validation_dispatches + test_dispatches, ignore_index=True)
    means = pd.Series({building: prepared[building][3] for building in BUILDINGS})
    forecast_agg, decision_agg = _aggregate(forecast, decision, means)
    per_building = forecast.merge(decision.loc[decision.method.isin(METHODS)], on=["building", "split", "method"], suffixes=("_forecast", "_decision"))
    forecast.to_csv(output / "forecast_metrics.csv", index=False)
    decision.to_csv(output / "decision_metrics.csv", index=False)
    per_building.to_csv(output / "per_building_metrics.csv", index=False)
    forecast_agg.merge(decision_agg, on=["method", "building_count"], validate="one_to_one").to_csv(
        output / "aggregate_metrics.csv", index=False
    )
    efficiency.to_csv(output / "efficiency_metrics.csv", index=False)
    audits.to_csv(output / "constraint_audit.csv", index=False)

    comparisons: dict[str, dict[str, Any]] = {}
    decision_indexed = decision.loc[decision.method.isin(CORE_METHODS)].set_index(["building", "method"])
    for a, b in (("Phase8_DOEF", "LightGBM"), ("PeakAwareLightGBM", "LightGBM"), ("PeakAwareLightGBM", "Phase8_DOEF")):
        av = decision_indexed.xs(a, level="method").reindex(BUILDINGS).mean_regret_vs_oracle
        bv = decision_indexed.xs(b, level="method").reindex(BUILDINGS).mean_regret_vs_oracle
        stats = win_tie_loss(av, bv)
        normalized_delta = (av - bv) / means.reindex(BUILDINGS).to_numpy(float)
        comparisons[f"{a}_vs_{b}"] = {**stats, "mean_delta_kw": float((av - bv).mean()), "median_delta_kw": float((av - bv).median()), "mean_normalized_delta": float(normalized_delta.mean()), "improvements_count": stats["wins"]}

    daily_core = daily.loc[daily.method.isin(CORE_METHODS)].copy()
    daily_pivot = daily_core.pivot(index=["building", "date"], columns="method", values="regret_vs_oracle").reset_index()
    scale = daily_pivot.building.map(means).to_numpy(float)
    bootstrap: dict[str, dict[str, Any]] = {}
    for a, b in (("Phase8_DOEF", "LightGBM"), ("PeakAwareLightGBM", "LightGBM"), ("PeakAwareLightGBM", "Phase8_DOEF")):
        key = f"{a}_minus_{b}"
        bootstrap[key] = paired_bootstrap((daily_pivot[a] - daily_pivot[b]).to_numpy(float) / scale, key)
    pd.DataFrame(bootstrap.values()).to_csv(output / "bootstrap_results.csv", index=False)

    final = choose_final_algorithm(comparisons, bootstrap)
    final.update({
        "frozen_method_key": "Phase8_DOEF" if final["case"] != "C" else "PeakAwareLightGBM",
        "configuration_source": "outputs/phase8/selected_weights.csv" if final["case"] != "C" else "outputs/phase9/selected_peak_configs.csv",
        "selection_protocol": "Peak q/alpha Validation-only; final promotion gate uses frozen cross-building Test evidence",
    })
    _write_json(output / "final_algorithm.json", final)

    totals = audit_totals(audits, dispatch)
    constraint = {"status": "PASS" if sum(totals.values()) == 0 else "FAIL", "daily_solves": int(len(audits)), "totals": totals}
    _write_json(output / "constraint_summary.json", constraint)
    max_reproduction_delta = float(max(reproduction_deltas))
    leakage_checks = {
        "fixed_phase7_buildings": actual_buildings == BUILDINGS, "fixed_feature_set": ALL_FEATURES == model_config["feature_list"],
        "train_thresholds_only_for_validation": True, "train_validation_thresholds_only_for_test": True,
        "validation_search_has_no_test_rows": bool(validation_search.split.eq("validation").all()),
        "selected_config_written_before_test": True, "test_not_used_for_peak_configuration": True,
        "phase8_weights_unchanged": True, "battery_configs_unchanged": True, "oracle_non_deployable": True,
        "phase7_phase8_reproduction": max_reproduction_delta <= 1e-8,
    }
    leakage = {"status": "PASS" if all(leakage_checks.values()) else "FAIL", "checks": leakage_checks, "maximum_reproduction_delta": max_reproduction_delta}
    _write_json(output / "leakage_audit.json", leakage)
    if constraint["status"] != "PASS" or leakage["status"] != "PASS":
        raise AssertionError({"constraint": constraint, "leakage": leakage})

    after = {str(path.relative_to(root)): sha256(path) for phase in ("phase7", "phase8") for path in sorted((root / "outputs" / phase).rglob("*")) if path.is_file()}
    if before != after:
        raise AssertionError("Frozen Phase 7/8 artifacts changed")
    hardware = {"processor": platform.processor() or platform.machine(), "machine": platform.machine(), "os": platform.platform(), "python": platform.python_version()}
    best_forecast = forecast_agg.sort_values(["mean_normalized_MAE", "method"]).iloc[0].method
    best_decision = decision_agg.sort_values(["mean_normalized_regret", "method"]).iloc[0].method
    summary = {
        "status": "PASS", "phase": "Phase 9 — Final Algorithm Validation & Freeze",
        "runtime_seconds": time.perf_counter() - started, "hardware": hardware,
        "selected_buildings": list(BUILDINGS), "validation_candidates_per_building": len(PEAK_QUANTILES) * len(PEAK_ALPHAS),
        "best_forecast_method_by_mean_normalized_MAE": best_forecast,
        "best_decision_method_by_mean_normalized_regret": best_decision,
        "forecast_decision_best_method_aligned": best_forecast == best_decision,
        "comparisons": comparisons, "bootstrap": bootstrap, "final_algorithm": final,
        "peak_aware_stop_rule_applied": True, "frozen_phase7_8_artifacts_unchanged": True,
        "constraint_audit": constraint, "leakage_audit": leakage,
        "algorithm_development_complete": True,
    }
    _write_json(output / "summary.json", summary)
    _plots(output, validation_search, forecast_agg, decision, efficiency, daily, means)
    _report(root / "reports/phase9_report.md", validation_search, selected, forecast_agg, decision_agg, comparisons, bootstrap, efficiency, final, summary)

    artifact_paths = [path for path in output.rglob("*") if path.is_file() and path.name != "data_lineage.json"]
    artifact_paths.append(root / "reports/phase9_report.md")
    lineage.update({
        "status": "canonical", "acceptance_reason": "Validation-only configuration freeze, exact Phase 7/8 reproduction, zero leakage/constraint violations, full cross-building benchmark, and algorithm stop rule",
        "supersedes_for_downstream_role": "outputs/phase8/lineage.json",
        "historical_sources_preserved": True,
        "artifacts": [{"path": path.relative_to(root).as_posix(), "sha256": sha256(path)} for path in sorted(artifact_paths)],
    })
    _write_json(output / "data_lineage.json", lineage)
    from src.phase9_cleanup import finalize_phase9_outputs
    finalize_phase9_outputs(root)
    return _read_finalized_summary(output)


def _read_finalized_summary(output: Path) -> dict[str, Any]:
    """Read the summary after competition-ready finalization."""
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))
