"""Competition-ready Phase 9 cleanup derived from frozen canonical outputs.

This module never fits a model or changes an experimental choice.  It validates
the existing Phase 9 lineage, derives display-ready statistics from the saved
CSV/JSON artifacts, strengthens the algorithm freeze metadata, and refreshes
the canonical documentation and manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DISPLAY_METHODS = (
    ("Persistence", "Day Persistence", "Persistence|Day", True),
    ("Week", "Week", "Week", False),
    ("DayWeek", "DayWeek", "DayWeek", False),
    ("LightGBM", "LightGBM", "LightGBM", False),
    ("XGBoost", "XGBoost", "XGBoost", False),
    ("CatBoost", "CatBoost", "CatBoost", False),
    ("Phase8_DOEF", "DOEF", "Phase8_DOEF", False),
    ("PeakAwareLightGBM", "Peak-aware LightGBM", "PeakAwareLightGBM", False),
)
FIXED_BUILDINGS = (
    "Hog_office_Rolando", "Hog_office_Lavon", "Hog_office_Joey",
    "Lamb_office_Caitlin", "Robin_office_Addie", "Lamb_office_Gerardo",
    "Hog_office_Alexis", "Hog_office_Byron",
)
EQUIVALENCE_BAND = 0.001
FINAL_NAME = "Decision-Oriented Ensemble Forecasting"
FINAL_ACRONYM = "DOEF"
FINAL_VERSION = "1.0"
FINAL_NAME_ZH = "面向储能决策的集成负荷预测方法"
FINALIZER_OWNED_ARTIFACTS = {
    "outputs/phase9/competition_summary.json",
    "outputs/phase9/data_lineage.json",
    "outputs/phase9/final_algorithm.json",
    "outputs/phase9/final_benchmark.csv",
    "outputs/phase9/summary.json",
    "reports/phase9_report.md",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_current_lineage(root: Path) -> dict[str, Any]:
    """Verify frozen inputs and parents before regenerating owned derivatives."""
    lineage_path = root / "outputs/phase9/data_lineage.json"
    lineage = _read_json(lineage_path)
    if lineage.get("status") != "canonical":
        raise ValueError("Phase 9 lineage must be canonical before cleanup")
    for artifact in lineage.get("artifacts", []):
        if artifact["path"] in FINALIZER_OWNED_ARTIFACTS:
            continue
        path = root / artifact["path"]
        if not path.is_file() or _sha256(path) != artifact["sha256"]:
            raise ValueError(f"Registered Phase 9 artifact drift: {artifact['path']}")
    for parent in lineage.get("parents", {}).values():
        path = root / parent["path"]
        if not path.is_file() or _sha256(path) != parent["sha256"]:
            raise ValueError(f"Frozen parent artifact drift: {parent['path']}")
    return lineage


def _assert_day_aliases(aggregate: pd.DataFrame, per_building: pd.DataFrame) -> None:
    aggregate_numeric = aggregate.select_dtypes(include="number").columns
    persistence = aggregate.loc[aggregate.method.eq("Persistence"), aggregate_numeric]
    day = aggregate.loc[aggregate.method.eq("Day"), aggregate_numeric]
    if len(persistence) != 1 or len(day) != 1 or not np.allclose(persistence.to_numpy(float), day.to_numpy(float), atol=1e-12, rtol=0.0):
        raise AssertionError("Persistence and Day aggregate metrics are not mathematically identical")
    p = per_building.loc[per_building.method.eq("Persistence")].sort_values("building").reset_index(drop=True)
    d = per_building.loc[per_building.method.eq("Day")].sort_values("building").reset_index(drop=True)
    if p.building.tolist() != d.building.tolist():
        raise AssertionError("Persistence and Day building coverage differs")
    numeric = [column for column in p.select_dtypes(include="number").columns if column in d]
    if not np.allclose(p[numeric].to_numpy(float), d[numeric].to_numpy(float), atol=1e-12, rtol=0.0):
        raise AssertionError("Persistence and Day per-building metrics differ")


def build_final_benchmark(aggregate: pd.DataFrame, per_building: pd.DataFrame,
                          summary: dict[str, Any]) -> pd.DataFrame:
    """Create one display-ready row per competition method without recomputation of models."""
    _assert_day_aliases(aggregate, per_building)
    indexed = aggregate.set_index("method")
    required = {item[0] for item in DISPLAY_METHODS} | {"Day"}
    if not required.issubset(indexed.index):
        raise ValueError(f"Aggregate benchmark is missing methods: {sorted(required.difference(indexed.index))}")
    comparisons = summary["comparisons"]
    comparison_keys = {
        "Phase8_DOEF": "Phase8_DOEF_vs_LightGBM",
        "PeakAwareLightGBM": "PeakAwareLightGBM_vs_LightGBM",
    }
    rows: list[dict[str, Any]] = []
    for internal, display, raw_identifiers, alias in DISPLAY_METHODS:
        source = indexed.loc[internal]
        building_values = per_building.loc[per_building.method.eq(internal), "peak_reduction_percentage"].to_numpy(float)
        if building_values.size != len(FIXED_BUILDINGS):
            raise AssertionError(f"Expected eight peak-reduction values for {internal}")
        comparison = comparisons.get(comparison_keys.get(internal, ""), {})
        rows.append({
            "display_name": display,
            "internal_method": internal,
            "raw_identifiers": raw_identifiers,
            "equivalent_alias": bool(alias),
            "normalized_mae_mean": float(source.mean_normalized_MAE),
            "normalized_mae_median": float(source.median_normalized_MAE),
            "normalized_rmse_mean": float(source.mean_normalized_RMSE),
            "normalized_peak_mae_mean": float(source.mean_normalized_peak_region_MAE),
            "normalized_decision_regret_mean": float(source.mean_normalized_regret),
            "normalized_decision_regret_median": float(source.median_normalized_regret),
            "peak_reduction_mean_pct": float(np.mean(building_values)),
            "peak_reduction_median_pct": float(np.median(building_values)),
            "peak_reduction_min_pct": float(np.min(building_values)),
            "peak_reduction_max_pct": float(np.max(building_values)),
            "decision_wins_vs_lightgbm": comparison.get("wins"),
            "decision_ties_vs_lightgbm": comparison.get("ties"),
            "decision_losses_vs_lightgbm": comparison.get("losses"),
        })
    result = pd.DataFrame(rows)
    for column in ("decision_wins_vs_lightgbm", "decision_ties_vs_lightgbm", "decision_losses_vs_lightgbm"):
        result[column] = result[column].astype("Int64")
    if result.display_name.duplicated().any() or set(result.display_name).difference({item[1] for item in DISPLAY_METHODS}):
        raise AssertionError("Display benchmark method mapping is invalid")
    return result


def build_final_algorithm_metadata() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": FINAL_NAME,
        "acronym": FINAL_ACRONYM,
        "display_name_zh": FINAL_NAME_ZH,
        "source_phase": 9,
        "algorithm_version": FINAL_VERSION,
        "freeze_status": "frozen",
        "status": "canonical",
        "algorithm_development_status": "ENDED / FROZEN",
        "selection_basis": "Phase 8 Validation-selected decision-oriented ensemble, frozen before Test evaluation.",
        "algorithm_selection_source": "Validation",
        "held_out_evaluation_role": "Evaluation and reporting only; not used to promote an algorithm or choose buildings, model parameters, or ensemble weights.",
        "test_role": "evaluation_only",
        "fixed_buildings": list(FIXED_BUILDINGS),
        "forecast_horizon_hours": 24,
        "model_components": [
            {
                "name": "DayWeek",
                "role": "causal baseline component",
                "formula": "0.5 * actual(t-24h) + 0.5 * actual(t-168h)",
            },
            {
                "name": "LightGBM",
                "role": "frozen per-building tree forecast component",
                "metadata_path": "outputs/phase7/model_selection_config.json",
            },
        ],
        "ensemble": {
            "formula": "w * LightGBM + (1-w) * DayWeek",
            "weight_config_path": "outputs/phase8/selected_weights.csv",
            "weight_field": "w_decision",
            "weight_selection": "Per-building Validation mean daily regret vs non-deployable Oracle with frozen tie-breaks",
        },
        "building_config_path": "outputs/phase7/selected_buildings.json",
        "battery_config_path": "outputs/phase7/building_battery_configs.csv",
        "required_artifacts": [
            "outputs/phase7/selected_buildings.json",
            "outputs/phase7/model_selection_config.json",
            "outputs/phase7/building_battery_configs.csv",
            "outputs/phase8/selected_weights.csv",
            "outputs/phase9/run_config.json",
            "outputs/phase9/aggregate_metrics.csv",
            "outputs/phase9/final_benchmark.csv",
            "outputs/phase9/competition_summary.json",
        ],
        "decision_equivalence_band": {
            "metric": "normalized mean Validation regret",
            "tolerance": EQUIVALENCE_BAND,
            "purpose": "Conservative model-selection tolerance that treats very small Validation differences as practically equivalent and prefers weaker sample weighting.",
            "is_statistical_significance_threshold": False,
        },
        "peak_aware_experiment": {
            "status": "rejected supporting experiment",
            "result_zh": "未成功",
            "entered_final_algorithm": False,
        },
        "test_used_to_choose_peak_configuration": False,
        "test_used_to_promote_algorithm": False,
        "algorithm_development_frozen": True,
        "legacy_method_key": "Phase8_DOEF",
        "legacy_final_algorithm": "DOEF — Decision-Oriented Ensemble Forecasting",
    }


def build_competition_summary(benchmark: pd.DataFrame, per_building: pd.DataFrame,
                              bootstrap: pd.DataFrame, efficiency: pd.DataFrame,
                              selected_peak: pd.DataFrame) -> dict[str, Any]:
    indexed = benchmark.set_index("display_name")
    doef = indexed.loc["DOEF"]
    lightgbm = indexed.loc["LightGBM"]
    comparison = bootstrap.set_index("comparison").loc["Phase8_DOEF_minus_LightGBM"]
    catboost_values = per_building.loc[per_building.method.eq("CatBoost"), ["building", "peak_reduction_percentage", "no_battery_peak", "post_dispatch_peak", "normalized_MAE", "daily_peak_hour_MAE"]].sort_values("building")
    cat_values = catboost_values.peak_reduction_percentage.to_numpy(float)
    lavon = catboost_values.loc[catboost_values.building.eq("Hog_office_Lavon")].iloc[0]
    efficiency_summary = []
    display_efficiency = {"Phase8_DOEF": "DOEF", "PeakAwareLightGBM": "Peak-aware LightGBM"}
    for method, part in efficiency.groupby("method", sort=True):
        efficiency_summary.append({
            "display_name": display_efficiency.get(method, method),
            "training_time_seconds_mean_across_buildings": float(part.training_time_seconds.mean()),
            "inference_time_ms_mean_across_buildings": float(part.inference_time_ms.mean()),
            "artifact_size_kib_mean_across_buildings": float(part.artifact_size_bytes.mean() / 1024.0),
            "test_samples_per_building": int(part.test_samples.iloc[0]),
            "inference_repeats": int(part.inference_repeats.iloc[0]),
        })
    return {
        "schema_version": 1,
        "status": "canonical",
        "source_phase": 9,
        "final_algorithm": {
            "name": FINAL_NAME,
            "acronym": FINAL_ACRONYM,
            "display_name_zh": FINAL_NAME_ZH,
            "algorithm_version": FINAL_VERSION,
            "freeze_status": "frozen",
        },
        "buildings": len(FIXED_BUILDINGS),
        "building_ids": list(FIXED_BUILDINGS),
        "doef_vs_lightgbm": {
            "normalized_mae_relative_improvement_pct": float(100.0 * (lightgbm.normalized_mae_mean - doef.normalized_mae_mean) / lightgbm.normalized_mae_mean),
            "normalized_regret_relative_improvement_pct": float(100.0 * (lightgbm.normalized_decision_regret_mean - doef.normalized_decision_regret_mean) / lightgbm.normalized_decision_regret_mean),
            "win_tie_loss": {"wins": int(doef.decision_wins_vs_lightgbm), "ties": int(doef.decision_ties_vs_lightgbm), "losses": int(doef.decision_losses_vs_lightgbm)},
            "bootstrap_point_difference": float(comparison.point_estimate),
            "bootstrap_ci_low": float(comparison.ci95_lower),
            "bootstrap_ci_high": float(comparison.ci95_upper),
            "bootstrap_resamples": int(comparison.resamples),
            "bootstrap_seed": int(comparison.seed),
        },
        "day_persistence_alias": {
            "display_name": "Day Persistence",
            "formula": "forecast(t) = actual(t - 24h)",
            "raw_identifiers": ["Persistence", "Day"],
            "equivalent_alias": True,
        },
        "decision_equivalence_band": {
            "metric": "normalized mean Validation regret",
            "tolerance": EQUIVALENCE_BAND,
            "purpose": "Avoid interpreting very small and potentially unstable Validation differences as substantive decision improvements; prefer weaker sample weighting among equivalent candidates.",
            "is_statistical_significance_threshold": False,
        },
        "catboost_peak_reduction_pct": {
            "mean": float(np.mean(cat_values)),
            "median": float(np.median(cat_values)),
            "min": float(np.min(cat_values)),
            "max": float(np.max(cat_values)),
            "per_building": catboost_values[["building", "peak_reduction_percentage"]].to_dict("records"),
            "extreme_case": {
                "building": str(lavon.building),
                "no_battery_peak_kw": float(lavon.no_battery_peak),
                "post_dispatch_peak_kw": float(lavon.post_dispatch_peak),
                "normalized_mae": float(lavon.normalized_MAE),
                "daily_peak_hour_mae_hours": float(lavon.daily_peak_hour_MAE),
            },
        },
        "peak_aware_result": {
            "status_zh": "未成功",
            "selected_alpha_zero_buildings": int(selected_peak.alpha.eq(0.0).sum()),
            "nonzero_selection": selected_peak.loc[selected_peak.alpha.ne(0.0), ["building", "q", "alpha"]].to_dict("records"),
            "vs_lightgbm_win_tie_loss": {"wins": 0, "ties": 7, "losses": 1},
            "vs_doef_win_tie_loss": {"wins": 0, "ties": 2, "losses": 6},
        },
        "test_protocol": {
            "preferred_term": "frozen held-out test period",
            "preferred_term_zh": "冻结的留出测试区间",
            "historical_results_previously_viewed": True,
            "phase7_9_boundaries_frozen": True,
            "used_for_model_or_hyperparameter_selection": False,
        },
        "metric_semantics": {
            "peak_reduction_percentage": "Peak shaving under the frozen battery capacity, power constraints, and dispatch protocol.",
            "peak_reduction_is_energy_saving": False,
            "energy_saving_metric_present": False,
            "cost_reduction_metric_present": False,
            "carbon_reduction_metric_present": False,
        },
        "efficiency_protocol": {
            "aggregation": "mean across 8 buildings",
            "inference_measurement": "median of 20 repetitions on the same 720 samples per building, then mean across buildings",
            "environment": "CPU test environment recorded in outputs/phase9/summary.json",
            "embedded_device_test": False,
            "industrial_control_latency_proven": False,
            "methods": efficiency_summary,
        },
        "historical_artifact_audit": {
            "phase7_manifest_path": "outputs/phase7/artifact_manifest.json",
            "phase7_manifest_sha256": _sha256(Path(per_building.attrs["project_root"]) / "outputs/phase7/artifact_manifest.json"),
            "phase8_lineage_path": "outputs/phase8/lineage.json",
            "phase8_lineage_sha256": _sha256(Path(per_building.attrs["project_root"]) / "outputs/phase8/lineage.json"),
            "frozen_artifacts_modified_by_cleanup": False,
        },
    }


def _markdown(frame: pd.DataFrame, columns: list[str], digits: int = 5) -> str:
    shown = frame[columns].copy()
    for column in shown.columns:
        if pd.api.types.is_numeric_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.{digits}f}")
    rows = [list(shown.columns), ["---"] * len(shown.columns), *shown.astype(str).values.tolist()]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def build_report(root: Path, benchmark: pd.DataFrame, competition: dict[str, Any],
                 selected_peak: pd.DataFrame) -> str:
    derived = competition["doef_vs_lightgbm"]
    cat = competition["catboost_peak_reduction_pct"]
    cat_table = pd.DataFrame(cat["per_building"]).rename(columns={"peak_reduction_percentage": "peak_reduction_pct"})
    efficiency = pd.DataFrame(competition["efficiency_protocol"]["methods"])
    selected = selected_peak[["building", "q", "alpha"]].copy()
    return "\n".join([
        "# Phase 9 — Final Algorithm Validation & Algorithm Freeze v1.0", "",
        "## 1. Scope and honest evaluation protocol", "",
        "Phase 9 是最后一个算法研发阶段。本次 cleanup 没有训练新模型、搜索新参数、改变建筑/切分/battery，也没有用测试结果重新选择配置。8 栋建筑、24 h horizon、31 个因果特征、Phase 7 模型参数、Phase 8 决策导向权重和全部正式数值保持不变。", "",
        "正式术语为 **frozen held-out test period（冻结的留出测试区间）**。该区间在早期阶段作为固定 held-out evaluation period 使用，但历史阶段已经查看过结果；Phase 7–9 保持边界冻结，并禁止使用它重新选择模型、建筑或超参数。这是 honest evaluation protocol，不是项目级从未查看过的盲测声明。", "",
        "## 2. Peak-aware design and 0.001 equivalence band", "",
        "Peak-aware 仅比较 q∈{0.80,0.90}、alpha∈{0,0.5,1,2}，threshold 来自允许用于拟合/选择的 labels。为避免将 Validation 上极小、可能缺乏稳定性的数值差异解释为实质性决策提升，本阶段采用 normalized mean regret `0.001` 的等价带。与最佳候选差异不超过该阈值的配置视为决策表现近似等价，并优先选择复杂度更低、sample weighting 更弱的方案。", "",
        "`0.001` 是保守的 model-selection tolerance，**不是** p-value、统计显著性阈值或置信阈值。", "",
        _markdown(selected, ["building", "q", "alpha"]), "",
        "## 3. Canonical competition benchmark", "",
        "原始 machine-readable 结果为兼容历史仍保留 `Persistence` 和 `Day`；两者均严格满足 `forecast(t)=actual(t-24h)`。比赛展示合并为一行 **Day Persistence**。`DOEF` 是 Phase 8 decision-oriented ensemble 在 Phase 9 正式冻结后的比赛方法名。", "",
        _markdown(benchmark, ["display_name", "normalized_mae_mean", "normalized_rmse_mean", "normalized_peak_mae_mean", "normalized_decision_regret_mean", "peak_reduction_mean_pct", "peak_reduction_median_pct"]), "",
        "所有 peak-reduction 数值表示当前冻结储能容量、功率约束和调度协议下的削峰结果。**Peak shaving 不等于 energy saving**；本项目没有由该百分比推导节电量、电费或碳减排。", "",
        "## 4. DOEF v1.0 core evidence", "",
        f"8 栋异质办公建筑上，DOEF 相对 LightGBM 的 normalized MAE 从 0.14734 降至 0.13797，程序计算的相对改善为 **{derived['normalized_mae_relative_improvement_pct']:.4f}%**；normalized decision regret 从 0.11613 降至 0.11193，相对改善为 **{derived['normalized_regret_relative_improvement_pct']:.4f}%**。", "",
        f"Decision win/tie/loss = **{derived['win_tie_loss']['wins']}/{derived['win_tie_loss']['ties']}/{derived['win_tie_loss']['losses']}**。DOEF − LightGBM normalized regret difference = **{derived['bootstrap_point_difference']:.6f}**，95% CI **[{derived['bootstrap_ci_low']:.6f}, {derived['bootstrap_ci_high']:.6f}]**（10,000 paired bootstrap，seed 42）。", "",
        "本项目的创新重点不是重新设计基础预测器，而是针对建筑储能削峰任务中“平均预测误差最优并不必然对应下游调度最优”的目标错位问题，建立预测—储能决策闭环评价体系，并通过 Validation 下游决策指标进行模型选择与融合，形成 DOEF。创新链为：Causal time-series forecasting + Decision-oriented validation + Forecast-to-storage closed-loop evaluation + Multi-building generalization + Decision-oriented ensemble。", "",
        "## 5. CatBoost extreme aggregate audit", "",
        f"CatBoost peak reduction：mean={cat['mean']:.5f}%，median={cat['median']:.5f}%，min={cat['min']:.5f}%，max={cat['max']:.5f}%。均值受少数建筑极端负向调度结果显著影响，因此单独使用 arithmetic mean 容易夸大其典型表现差异；这里保留真实均值，并同时报告 median、范围和全部逐建筑结果。", "",
        _markdown(cat_table, ["building", "peak_reduction_pct"]), "",
        f"极端值来自 Hog_office_Lavon：no-battery peak={cat['extreme_case']['no_battery_peak_kw']:.3f} kW，post-dispatch peak={cat['extreme_case']['post_dispatch_peak_kw']:.3f} kW，故比例为 {cat['min']:.3f}%。其 normalized MAE={cat['extreme_case']['normalized_mae']:.5f}，但 daily peak-hour MAE={cat['extreme_case']['daily_peak_hour_mae_hours']:.2f} h。结合该建筑按 Train scale 配置、而测试负荷峰值较低的 battery 条件，错误的峰时调度会被百分比的小分母放大。这是与已保存诊断一致的解释，不是新的因果实验，也不掩盖 CatBoost 的失败。", "",
        "## 6. Rejected supporting experiment: Peak-aware LightGBM", "",
        "事实是 7/8 建筑选择 alpha=0，仅 Hog_office_Byron 选择 q=0.8、alpha=2.0。冻结的留出测试区间上，Peak-aware vs LightGBM 为 0/7/1，Peak-aware vs DOEF 为 0/2/6；Peak-aware − LightGBM CI 跨 0，而 Peak-aware − DOEF CI 完全高于 0。", "",
        "简单的高负荷 sample weighting 没有产生稳定的跨建筑 downstream decision improvement。结果说明储能决策质量不能简单通过提高峰值样本训练权重获得；模型误差的时序结构、峰值时刻定位以及与储能约束的相互作用仍然重要。因此按照预定义停止规则，不再扩展 weighting function 或继续调参。", "",
        "## 7. Engineering efficiency", "",
        _markdown(efficiency, ["display_name", "training_time_seconds_mean_across_buildings", "inference_time_ms_mean_across_buildings", "artifact_size_kib_mean_across_buildings", "test_samples_per_building"]), "",
        "表中训练、推理和 artifact size 均为 8 栋建筑平均；inference 先对同一 720 样本重复 20 次取中位数，再跨建筑平均。环境是 summary.json 记录的 CPU 测试环境，不是嵌入式设备测试，不能外推为实际工业控制 latency。DOEF 相比标准 LightGBM 只增加很小的推理开销，在当前 CPU 测试环境下仍属于轻量级方法，但不声称已证明实时工业部署。", "",
        "## 8. Final Algorithm", "",
        "**DOEF v1.0**", "", "**Decision-Oriented Ensemble Forecasting**", "", f"**{FINAL_NAME_ZH}**", "",
        "Selection basis: Validation-selected decision-oriented ensemble, confirmed by frozen held-out multi-building evaluation. Held-out results用于报告与冻结确认，不用于重新选择建筑、模型参数或融合权重。", "",
        "Core evidence: 8 heterogeneous office buildings；DOEF vs LightGBM = 6 wins / 2 ties / 0 losses；normalized MAE = 0.13797 vs 0.14734；normalized decision regret = 0.11193 vs 0.11613；bootstrap difference = -0.004198，95% CI [-0.007830, -0.000356]。", "",
        "Rejected experiment: Peak-aware LightGBM 未产生稳定跨建筑收益，不进入最终算法。", "",
        "**Algorithm development: FROZEN**",
        "",
        "**Algorithm version: DOEF v1.0**",
        "**Further algorithm R&D: STOPPED**", "",
        "Phase 9 canonical consumers必须通过 `src.final_algorithm.load_final_algorithm()` 读取；Phase 9 缺失或校验失败时显式报错，不回退到 Phase 8。", "",
    ]) + "\n"


def build_readme_phase9(benchmark: pd.DataFrame, competition: dict[str, Any]) -> str:
    derived = competition["doef_vs_lightgbm"]
    table = _markdown(benchmark, ["display_name", "normalized_mae_mean", "normalized_rmse_mean", "normalized_peak_mae_mean", "normalized_decision_regret_mean", "peak_reduction_mean_pct", "peak_reduction_median_pct"])
    return "\n".join([
        "## Phase 9 — Final Algorithm Validation & Freeze", "",
        "Phase 9 是最后一个算法研发阶段。它没有增加模型家族，只在 Phase 7/8 完全冻结的 8 栋建筑、24 小时预测、Train/Validation/Test、31 个因果特征、逐建筑 LightGBM 参数和 Train-scale battery 上验证轻量 Peak-aware sample weighting。", "",
        "Validation 使用 normalized mean regret `0.001` 等价带，避免把极小且可能不稳定的差异解释为实质性提升；等价候选优先更弱 sample weighting。该值是保守 model-selection tolerance，不是统计显著性或置信阈值。", "",
        "正式评估术语为 **frozen held-out test period（冻结的留出测试区间）**。历史阶段已经查看过其结果；Phase 7–9 只保证边界冻结，且不使用该区间重新选择模型、建筑、参数、融合权重或 battery。", "",
        "### Competition-ready benchmark", "",
        "原始数据层为兼容历史保留 `Persistence`/`Day`，展示层合并为 `Day Persistence`，公式为 `forecast(t)=actual(t-24h)`。", "",
        table, "",
        "Peak reduction 是冻结 battery 容量、功率约束和调度协议下的削峰比例，不是节电率、成本降幅或碳减排。CatBoost 的负向 mean 由个别极端建筑驱动，因此主表同时给出 median；完整逐建筑值见 `competition_summary.json`。", "",
        f"**Final frozen algorithm: DOEF v1.0 — Decision-Oriented Ensemble Forecasting（{FINAL_NAME_ZH}）。** 相对 LightGBM，程序派生的 normalized MAE 相对改善为 {derived['normalized_mae_relative_improvement_pct']:.4f}%，normalized decision regret 相对改善为 {derived['normalized_regret_relative_improvement_pct']:.4f}%，decision win/tie/loss 为 6/2/0。", "",
        "Peak-aware LightGBM **未成功**：7/8 建筑选择 alpha=0，冻结的留出测试区间上相对 LightGBM 为 0/7/1、相对 DOEF 为 0/2/6，因此按停止规则不再扩展 weighting 或继续调参。", "",
        "正式输出位于 `outputs/phase9/`，比赛表为 `final_benchmark.csv`，派生摘要为 `competition_summary.json`，完整解释在 `reports/phase9_report.md`。后续消费者必须通过 `src.final_algorithm.load_final_algorithm()` 读取；Phase 9 artifact 缺失时显式失败，不回退历史阶段。", "",
        "## Algorithm Freeze", "",
        "**Phase 9 is the final algorithm-development phase.**", "",
        "- Final frozen algorithm: `DOEF v1.0`", "- Algorithm development: `ENDED / FROZEN`", "- Further algorithm R&D: `STOPPED`", "- 后续 visualization、prototype、report、presentation 或 demo 必须消费 Phase 9 canonical loader/artifacts。", "- 冻结后只允许修复经过验证的 bug；不得自行新增或调整模型。", "",
    ])


def finalize_phase9_outputs(project_root: Path) -> dict[str, Any]:
    """Finalize display/metadata from existing Phase 9 artifacts without model execution."""
    root = Path(project_root).resolve()
    output = root / "outputs/phase9"
    lineage = verify_current_lineage(root)
    aggregate = pd.read_csv(output / "aggregate_metrics.csv")
    per_building = pd.read_csv(output / "per_building_metrics.csv")
    per_building.attrs["project_root"] = str(root)
    bootstrap = pd.read_csv(output / "bootstrap_results.csv")
    efficiency = pd.read_csv(output / "efficiency_metrics.csv")
    selected_peak = pd.read_csv(output / "selected_peak_configs.csv")
    summary = _read_json(output / "summary.json")
    if tuple(summary["selected_buildings"]) != FIXED_BUILDINGS:
        raise AssertionError("Phase 9 fixed building list drifted")
    if summary["final_algorithm"]["peak_aware_result"] != "未成功":
        raise AssertionError("Peak-aware frozen conclusion changed")

    benchmark = build_final_benchmark(aggregate, per_building, summary)
    competition = build_competition_summary(benchmark, per_building, bootstrap, efficiency, selected_peak)
    final = build_final_algorithm_metadata()
    benchmark.to_csv(output / "final_benchmark.csv", index=False)
    _write_json(output / "competition_summary.json", competition)
    _write_json(output / "final_algorithm.json", final)
    summary["competition_summary_path"] = "outputs/phase9/competition_summary.json"
    summary["final_benchmark_path"] = "outputs/phase9/final_benchmark.csv"
    summary["algorithm_freeze"] = final
    summary["derived_competition_results"] = competition["doef_vs_lightgbm"]
    summary["test_protocol"] = competition["test_protocol"]
    _write_json(output / "summary.json", summary)
    (root / "reports/phase9_report.md").write_text(build_report(root, benchmark, competition, selected_peak), encoding="utf-8")

    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    marker = "## Phase 9 — Final Algorithm Validation & Freeze"
    if marker not in readme:
        raise ValueError("README Phase 9 section is missing")
    readme_path.write_text(readme[:readme.index(marker)] + build_readme_phase9(benchmark, competition), encoding="utf-8")

    artifact_paths = [path for path in output.rglob("*") if path.is_file() and path.name != "data_lineage.json"]
    artifact_paths.append(root / "reports/phase9_report.md")
    battery_path = root / "outputs/phase7/building_battery_configs.csv"
    lineage.setdefault("parents", {})["phase7_battery_configs"] = {
        "path": "outputs/phase7/building_battery_configs.csv",
        "sha256": _sha256(battery_path),
    }
    lineage.update({
        "schema_version": 2,
        "status": "canonical",
        "logical_role": "canonical final algorithm evidence and sole downstream result source",
        "finalizer": "scripts/finalize_phase9.py",
        "canonical_loader": "src.final_algorithm.load_final_algorithm",
        "algorithm_freeze": {"acronym": FINAL_ACRONYM, "version": FINAL_VERSION, "freeze_status": "frozen", "source_phase": 9},
        "acceptance_reason": "Competition-ready display aliases, derived statistics, honest held-out terminology, strict DOEF v1.0 metadata, and fail-closed canonical consumption; core experiment unchanged",
        "artifacts": [{"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)} for path in sorted(artifact_paths)],
        "documentation": ["README.md", "reports/phase9_report.md"],
        "historical_sources_preserved": True,
    })
    _write_json(output / "data_lineage.json", lineage)
    return competition
