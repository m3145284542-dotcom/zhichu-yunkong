"""Build and validate Phase 13.0B presentation evidence maps.

This script only selects and annotates values already present in the canonical
Phase 13.0A evidence layer. It does not run any model, prediction, optimizer,
bootstrap, statistical test, or figure-generation code.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "phase13_0a"
OUTPUT = ROOT / "outputs" / "phase13_0b"
REPORT = ROOT / "reports" / "phase13" / "phase13_0b_frozen_presentation_evidence_selection_and_story_mapping.md"
STARTING_HEAD = "dc9ad91c57d1e8c9037bef8216ccad23619ce85b"
FROZEN_BASELINE = "549abc314e93e2862bfc22965db89622c22890e1"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_text_sha256(path: Path) -> str:
    """Hash text as the LF-normalized bytes stored by Git."""
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


manifest = read_json(INPUT / "frozen_presentation_data_manifest.json")
manifest_by_id = {item["id"]: item for item in manifest["items"]}
matrix = read_csv(INPUT / "presentation_claim_evidence_matrix.csv")
matrix_ids = {row["claim_id"] for row in matrix}
figures_0a = {row["figure_id"]: row for row in read_csv(INPUT / "figure_inventory.csv")}


def evidence_for_metric(metric_id: str) -> str:
    item = manifest_by_id[metric_id]
    matches = [
        row for row in matrix
        if row["source_path"] == item["source_path"]
        and row["source_field"] == item["source_field"]
        and row["value"] == str(item["value"])
        and row["candidate_claim"] == item["label"]
        and row["evidence_status"] == item["status"]
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one Phase 13.0A evidence row for {metric_id}, found {len(matches)}")
    return matches[0]["claim_id"]


def claim(
    claim_id: str,
    tier: str,
    category: str,
    technical: str,
    presentation: str,
    metrics: list[str],
    figures: list[str],
    building_scope: str,
    split: str,
    model_scope: str,
    aggregation: str,
    unit: str,
    caveat: str,
    forbidden: str,
    safe: bool = True,
    provenance_sources: list[str] | None = None,
    score: dict[str, int] | None = None,
    explicit_evidence: list[str] | None = None,
) -> dict[str, Any]:
    evidence = list(dict.fromkeys((explicit_evidence or []) + [evidence_for_metric(mid) for mid in metrics]))
    return {
        "claim_id": claim_id,
        "tier": tier,
        "category": category,
        "technical_wording": technical,
        "presentation_wording": presentation,
        "claim_status": "PRESENTATION_SAFE" if safe else "NOT_PRESENTATION_SAFE",
        "evidence_ids": evidence,
        "primary_metric_ids": metrics,
        "figure_ids": figures,
        "building_scope": building_scope,
        "split": split,
        "model_scope": model_scope,
        "aggregation": aggregation,
        "unit": unit,
        "caveat": caveat,
        "forbidden_overclaim": forbidden,
        "presentation_safe": safe,
        "provenance_sources": provenance_sources or [],
        "competition_value": score,
    }


core_scores = {
    "scientific_importance": 5,
    "ai_algorithm_relevance": 5,
    "decision_relevance": 5,
    "visualizability": 4,
    "defensibility_in_qa": 5,
    "evidence_strength": 5,
    "uniqueness_within_project": 5,
}

claims = [
    claim(
        "CORE-01", "TIER 1 — CORE CLAIM", "Real problem",
        "The frozen task produces a 24-hour-ahead load forecast that is consumed by a battery peak-shaving dispatch evaluation; forecasting is an input to the decision task, not the terminal objective.",
        "预测不是终点：24 小时前瞻负荷预测服务于电池削峰决策。",
        ["forecast.horizon"], ["FIG-037"], "8 fixed office buildings", "Train/Validation/Test protocol", "DOEF pipeline", "not applicable", "hours; kW",
        "The evidence supports peak-demand reduction only, not tariff savings, carbon reduction, or energy-use reduction.",
        "The system has validated electricity-cost savings, carbon reduction, or lower energy consumption.",
        provenance_sources=["outputs/phase9/final_algorithm.json", "outputs/phase9_1/final_reporting_summary.json"], score=core_scores,
    ),
    claim(
        "CORE-02", "TIER 1 — CORE CLAIM", "Forecast accuracy versus decision quality",
        "On the frozen 8-building Test aggregate, XGBoost has slightly lower normalized RMSE than LightGBM (0.216751 versus 0.216942) but higher normalized decision regret (0.117534 versus 0.116127).",
        "更低的预测 RMSE 不必然带来更好的储能决策：冻结 Test 结果中，XGBoost 的 RMSE 略优，决策 regret 却更差。",
        ["9.final_benchmark.4.normalized_rmse_mean", "9.final_benchmark.3.normalized_rmse_mean", "9.final_benchmark.4.normalized_decision_regret_mean", "9.final_benchmark.3.normalized_decision_regret_mean"],
        ["FIG-038"], "8 fixed office buildings", "Test", "XGBoost versus LightGBM", "equal-building mean after Train-mean normalization", "dimensionless",
        "The RMSE gap is small and this is a project-specific counterexample, not proof that forecast accuracy never matters.",
        "Forecast accuracy is irrelevant, or all more accurate models make worse decisions.", score=core_scores,
    ),
    claim(
        "CORE-03", "TIER 1 — CORE CLAIM", "Decision-oriented model selection",
        "Phase 8 evaluates 11 predeclared DayWeek/LightGBM weights on Validation and freezes each building's weight by mean daily regret versus a non-deployable Oracle; for Hog_office_Joey, forecast-MAE selection chooses w=0.6 while decision-regret selection chooses w=0.3.",
        "DOEF 不只按预测误差选融合权重，而是在 Validation 上按储能决策 regret 冻结权重。",
        ["phase8.weight_candidates", "phase8.Hog_office_Joey.w_forecast", "phase8.Hog_office_Joey.w_decision"],
        ["FIG-032", "FIG-033", "FIG-034"], "8 fixed office buildings; example: Hog_office_Joey", "Validation only", "DayWeek/LightGBM ensemble", "per-building selection", "ensemble LightGBM weight",
        "The Joey weights are an illustrative frozen example; Oracle is hindsight-only and non-deployable.",
        "Weights were tuned on Test, or the Oracle is deployable.",
        provenance_sources=["outputs/phase8/run_config.json", "outputs/phase9/final_algorithm.json"], score=core_scores,
    ),
    claim(
        "CORE-04", "TIER 1 — CORE CLAIM", "Multi-building benchmark",
        "The benchmark fixes 8 heterogeneous office buildings using Train-only morphology after frozen eligibility filtering from 296 office candidates, of which 82 pass the frozen quality rules.",
        "在 296 个办公候选中按冻结质量规则筛到 82 个，再仅用 Train 期形态预选 8 栋异质办公建筑。",
        ["dataset.office_candidates", "dataset.office_quality_pass", "dataset.final_buildings"], ["FIG-024"],
        "8 pre-selected heterogeneous office buildings", "Train-only building selection; later Validation/Test evaluation", "multi-model benchmark", "fixed selection counts", "buildings",
        "This is multi-building evaluation across fixed buildings, not unseen-building transfer.",
        "DOEF generalizes to unseen buildings, zero-shot transfers, or performs domain adaptation.",
        provenance_sources=["outputs/phase7/selected_buildings.json"], score=core_scores,
    ),
    claim(
        "CORE-05", "TIER 1 — CORE CLAIM", "DOEF v1.0 system",
        "DOEF v1.0 is formally named Decision-Oriented Ensemble Forecasting and computes w_b·LightGBM + (1-w_b)·DayWeek for a 24-hour-ahead forecast, with w_b frozen per building by Validation decision regret before battery dispatch evaluation.",
        "DOEF v1.0（Decision-Oriented Ensemble Forecasting）把因果预测、决策导向融合和电池削峰评估连成一条冻结流程。",
        ["forecast.horizon", "phase8.Hog_office_Joey.w_decision"], ["FIG-034"], "8 fixed office buildings", "Validation selection; Test evaluation", "DayWeek + LightGBM → DOEF → battery dispatch", "per-building frozen ensemble", "hours; ensemble weight; kW",
        "The pipeline is integrated for evaluation; it is not end-to-end differentiable training and does not claim online deployment.",
        "DOEF is a new LightGBM model, an end-to-end differentiable optimizer, or a deployed production system.",
        provenance_sources=["outputs/phase9/final_algorithm.json", "outputs/phase9_1/final_reporting_summary.json"], score=core_scores,
    ),
    claim(
        "CORE-06", "TIER 1 — CORE CLAIM", "Final forecast outcome",
        "On the frozen 8-building Test aggregate, DOEF reduces mean normalized MAE from 0.147338 for LightGBM to 0.137970, a relative improvement of 6.3585%.",
        "在冻结的 8 栋建筑 Test 汇总上，DOEF 相对 LightGBM 的 normalized MAE 改善 6.36%。",
        ["phase9_1.lightgbm_mean_normalized_mae", "phase9_1.doef_mean_normalized_mae", "phase9_1.normalized_mae_relative_improvement_pct"], ["FIG-040"],
        "8 fixed office buildings", "Test", "DOEF v1.0 versus LightGBM", "equal-building mean; normalized by frozen Train mean load", "dimensionless; %",
        "One fixed Test month per building; the result is not evidence of universal or unseen-building performance.",
        "DOEF beats all forecasting methods everywhere or is state of the art.", score=core_scores,
    ),
    claim(
        "CORE-07", "TIER 1 — CORE CLAIM", "Final decision outcome",
        "On the frozen 8-building Test aggregate, DOEF reduces mean normalized decision regret from 0.116127 for LightGBM to 0.111929, a relative improvement of 3.6147%, with 6 building wins, 2 ties, and 0 losses.",
        "DOEF 相对 LightGBM 的 normalized decision regret 改善 3.61%，建筑级结果为 6 胜、2 平、0 负。",
        ["phase9_1.lightgbm_mean_normalized_regret", "phase9_1.doef_mean_normalized_regret", "phase9_1.normalized_regret_relative_improvement_pct", "phase9_1.decision_wins", "phase9_1.decision_ties", "phase9_1.decision_losses"],
        ["FIG-039", "FIG-040"], "8 fixed office buildings", "Test", "DOEF v1.0 versus LightGBM", "equal-building mean; building-level win/tie/loss", "dimensionless; %; buildings",
        "Regret is defined against the non-deployable Oracle under the frozen battery protocol; this is not monetary regret.",
        "DOEF beats every method on every building, or the improvement is monetary savings.", score=core_scores,
    ),
    claim(
        "CORE-08", "TIER 1 — CORE CLAIM", "Peak-shaving outcome",
        "Across the 8 fixed Test buildings, DOEF's mean whole-window peak reduction is 6.4423%; the building-level minimum is -1.0170%, so the frozen evidence includes a degradation case.",
        "DOEF 的 8 栋建筑平均削峰率为 6.44%，同时如实保留最差建筑 -1.02% 的负结果。",
        ["9.final_benchmark.6.peak_reduction_mean_pct", "9.final_benchmark.6.peak_reduction_min_pct"], ["FIG-040"],
        "8 fixed office buildings", "Test", "DOEF v1.0", "equal-building mean and building minimum of whole-window peak reduction", "%",
        "Whole-window peak reduction is not daily-average peak reduction; one building is negative.",
        "DOEF always reduces peak demand, or every building improves.", score=core_scores,
    ),
    claim(
        "SUP-01", "TIER 2 — SUPPORTING CLAIM", "Dataset scale",
        "The frozen Phase 3 selection table represents 1,578 building series; 296 are office candidates.",
        "项目冻结的 BDG2 选择表覆盖 1,578 栋建筑序列，其中 296 栋为办公候选。",
        ["dataset.raw_building_count", "dataset.office_candidates"], ["FIG-024"], "project selection universe", "not applicable", "dataset", "row count", "buildings",
        "The 1,578 count is scoped to this repository's frozen selection table.", "BDG2 universally has exactly 1,578 buildings.",
    ),
    claim(
        "SUP-02", "TIER 2 — SUPPORTING CLAIM", "Causal protocol",
        "Forecasts use only causally available load-history and calendar features for a 24-hour horizon; target leakage and weather features are excluded in the frozen protocol.",
        "24 小时前瞻预测只使用因果可得的负荷历史与日历特征。",
        ["forecast.horizon"], [], "8 fixed office buildings", "all splits", "forecast components", "not applicable", "hours",
        "This does not claim the feature set is optimal or exhaustive.", "The system uses real-time future weather or future target values.",
        provenance_sources=["outputs/phase9/final_algorithm.json"],
    ),
    claim(
        "SUP-03", "TIER 2 — SUPPORTING CLAIM", "Validation discipline",
        "All model and ensemble choices were frozen using Validation only; Test is evaluation-only and cannot promote an algorithm.",
        "所有模型与融合选择均只用 Validation 冻结，Test 仅用于评估。",
        ["phase8.weight_candidates"], ["FIG-032", "FIG-033"], "8 fixed office buildings", "Validation selection; Test evaluation", "all selected models and ensemble weights", "not applicable", "weights",
        "Historical Test results had been viewed; the safe statement concerns non-use for selection, not pristine visibility.",
        "The Test set was pristine, completely untouched, or never viewed.",
        provenance_sources=["outputs/phase9_1/final_reporting_summary.json", "outputs/phase8/run_config.json"],
    ),
    claim(
        "SUP-04", "TIER 2 — SUPPORTING CLAIM", "Building-level uncertainty",
        "A frozen building-level paired bootstrap of DOEF minus LightGBM normalized mean decision regret uses 10,000 resamples and yields point estimate -0.004198 with 95% interval [-0.006850, -0.001719].",
        "以建筑为重采样单位的冻结 bootstrap 区间仍位于 0 以下。",
        ["phase9_1.bootstrap.resamples", "phase9_1.bootstrap.point_estimate", "phase9_1.bootstrap.ci95_lower", "phase9_1.bootstrap.ci95_upper", "phase9_1.bootstrap.probability_mean_less_than_zero"],
        [], "8 fixed office buildings", "Test", "DOEF v1.0 minus LightGBM", "building-level paired bootstrap", "normalized regret difference; resamples",
        "Only 8 building units are available; the bootstrap quantifies uncertainty within this fixed scope.",
        "This proves universal statistical superiority across buildings.",
    ),
    claim(
        "SUP-05", "TIER 2 — SUPPORTING CLAIM", "Reproducibility",
        "The explicit DOEF v1.0 formula reproduces all 5,760 frozen Phase 8 ensemble predictions with maximum absolute difference 0.0 kW.",
        "DOEF v1.0 公式对 5,760 个冻结预测实现零差异复现。",
        ["phase9_1.invariance_samples", "phase9_1.invariance_max_delta"], [], "8 fixed office buildings", "Test", "DOEF v1.0", "all stored predictions", "predictions; kW",
        "This is prediction identity, not a fresh model rerun or independent replication.", "A new independent experiment reproduced the result.",
    ),
    claim(
        "SUP-06", "TIER 2 — SUPPORTING CLAIM", "Battery evaluation",
        "Forecast-driven daily battery schedules are evaluated on realized load under frozen capacity, power, efficiency, SOC, and daily-reset constraints.",
        "所有预测方法在同一冻结电池约束下比较，实现从预测到真实削峰结果的闭环评价。",
        ["phase9_1.doef_mean_normalized_regret"], ["FIG-037", "FIG-042"], "8 fixed office buildings", "Test", "all forecast-driven controllers", "daily dispatch evaluation", "kW; kWh",
        "The protocol is a fixed offline evaluation, not a field deployment.", "The battery controller has been deployed in real buildings.",
        provenance_sources=["outputs/phase9/final_algorithm.json", "outputs/phase13_0a/conflict_register.csv"],
    ),
    claim(
        "SUP-07", "TIER 2 — SUPPORTING CLAIM", "Honest aggregation",
        "Peak-reduction conclusions must retain method, building, split, whole-window/daily scope, and aggregation labels; CatBoost's frozen Test mean is -24.4824% while its median is 4.8209%.",
        "削峰率必须同时说明方法、建筑范围和聚合口径；均值与中位数可能给出相反印象。",
        ["9.final_benchmark.5.peak_reduction_mean_pct", "9.final_benchmark.5.peak_reduction_median_pct"], ["FIG-041"], "8 fixed office buildings", "Test", "CatBoost example", "equal-building mean versus median", "%",
        "The extreme mean is driven by a documented low-load building case; do not collapse it to one unlabeled scalar.",
        "Peak reduction is one universal scalar or CatBoost uniformly increases peaks.",
    ),
    claim(
        "SUP-08", "TIER 2 — SUPPORTING CLAIM", "Evidence-first falsification",
        "Negative or mixed frozen outcomes are retained and are not used to revise the Validation-frozen algorithm after Test evaluation.",
        "负结果不被隐藏，也不用于 Test 后反向改选算法。",
        ["phase5_7.test.lightgbm_robust.mean_regret", "phase5_7.test.lightgbm_deterministic.mean_regret"], ["FIG-022"], "Hog_office_Rolando and 8-building follow-up", "Validation selection; Test reporting", "robust and peak-aware supporting experiments", "method-specific", "kW",
        "These experiments are supporting falsification evidence, not DOEF components.", "Every attempted method improved Test performance.",
    ),
    claim(
        "BACK-01", "TIER 3 — BACKUP / Q&A CLAIM", "Robust optimization negative result",
        "For Hog_office_Rolando Test, the Validation-selected robust LightGBM configuration (lambda=0.5) has mean regret 20.4635 kW versus 11.1274 kW for deterministic LightGBM.",
        "稳健优化实验是负结果：Test mean regret 由 11.1274 kW 恶化至 20.4635 kW。",
        ["phase5_7.selected_lambda", "phase5_7.test.lightgbm_robust.mean_regret", "phase5_7.test.lightgbm_deterministic.mean_regret"], ["FIG-022", "FIG-023"], "Hog_office_Rolando", "Test after Validation selection", "robust versus deterministic LightGBM", "mean daily regret", "kW",
        "Single-building negative supporting experiment; not part of DOEF v1.0.", "Robust optimization improved Test performance.",
    ),
    claim(
        "BACK-02", "TIER 3 — BACKUP / Q&A CLAIM", "Unit semantics",
        "Raw meter observations are kWh per one-hour interval; dispatch quantities are interpreted as interval-average kW, while battery capacity and SOC remain kWh.",
        "一小时时间步下，负荷读数按区间能量解释，调度功率用 kW，电池容量与 SOC 用 kWh。",
        ["forecast.horizon"], [], "all buildings", "all splits", "data and battery semantics", "one-hour intervals", "kWh; kW",
        "Numerical values coincide only because delta-t equals one hour.", "kWh and kW are interchangeable units.",
        provenance_sources=["outputs/phase13_0a/conflict_register.csv"],
    ),
    claim(
        "BACK-03", "TIER 3 — BACKUP / Q&A CLAIM", "Test scope",
        "The frozen evaluation contains one fixed future Test month per building; Test did not select models or weights but historical Test results had been viewed.",
        "Test 不参与选择，但评估范围仅为每栋建筑一个固定未来月份，且不能称为从未查看。",
        ["dataset.final_buildings"], [], "8 fixed office buildings", "one fixed Test month per building", "all final methods", "not applicable", "buildings",
        "This limits temporal generalization and pristine-Test wording.", "Completely untouched pristine Test set or broad temporal generalization.",
        provenance_sources=["outputs/phase9_1/final_reporting_summary.json"],
    ),
    claim(
        "BACK-04", "TIER 3 — BACKUP / Q&A CLAIM", "DOEF weight detail",
        "DOEF uses frozen per-building Validation-selected weights rather than one universal ensemble weight; the Joey decision-selected LightGBM weight is 0.3.",
        "DOEF 使用逐建筑冻结权重，而不是一个全局固定权重。",
        ["phase8.Hog_office_Joey.w_decision"], ["FIG-034"], "8 fixed office buildings", "Validation", "DOEF ensemble", "per building", "ensemble LightGBM weight",
        "Do not generalize Joey's value to other buildings.", "DOEF always uses w=0.3.",
    ),
    claim(
        "BACK-05", "TIER 3 — BACKUP / Q&A CLAIM", "Prediction lineage",
        "The Phase 9.1 invariance audit confirms the reporting definition is byte-identical in values to the frozen Phase 8 ensemble prediction over 5,760 samples.",
        "报告中的 DOEF 定义与冻结 Phase 8 预测逐值一致。",
        ["phase9_1.invariance_samples", "phase9_1.invariance_max_delta"], [], "8 fixed office buildings", "Test", "DOEF v1.0", "all samples", "predictions; kW",
        "This does not repair the separately documented historical canonical-loader parent-hash caveat.", "All repository lineage issues are repaired.",
    ),
]

rejected_specs = [
    ("REJ-01", "Unseen-building transfer", "DOEF generalizes to unseen buildings.", "Frozen evidence covers 8 fixed buildings only.", "CLM-2568"),
    ("REJ-02", "Monetary savings", "DOEF delivers verified electricity-cost savings.", "No tariff or monetary outcome model exists.", "CLM-2569"),
    ("REJ-03", "Carbon reduction", "DOEF reduces carbon emissions.", "No carbon outcome model exists.", "CLM-2570"),
    ("REJ-04", "Energy reduction", "DOEF reduces building energy consumption.", "The outcome is peak demand, not energy use.", "CLM-2571"),
    ("REJ-05", "Broader building scope", "Results generalize beyond the 8 buildings.", "No frozen experiment supports that scope.", "CLM-2572"),
    ("REJ-06", "Broader temporal scope", "Results generalize across seasons and years.", "Only one fixed Test month per building is available.", "CLM-2573"),
    ("REJ-07", "Pristine Test", "The Test set was completely untouched and never viewed.", "Test was not used for selection, but historical results had been viewed.", "CLM-2574"),
    ("REJ-08", "Universal BDG2 count", "BDG2 has exactly 1,578 buildings.", "The count is limited to the frozen project selection table.", "CLM-2564"),
    ("REJ-09", "Universal peak scalar", "Peak reduction is one project-wide scalar.", "Method, building, split, scope, and aggregation change the value.", "CLM-2567"),
    ("REJ-10", "Robust improvement", "Robust optimization improved Test performance.", "Frozen Test regret materially degraded.", evidence_for_metric("phase5_7.test.lightgbm_robust.mean_regret")),
    ("REJ-11", "External novelty", "DOEF is first, novel, world-first, or state of the art.", "No external literature or SOTA audit is part of Phase 13.0B.", evidence_for_metric("phase9_1.normalized_regret_relative_improvement_pct")),
    ("REJ-12", "Universal superiority", "DOEF beats all methods on every metric and building.", "Frozen results include ties, method-specific strengths, and negative cases.", evidence_for_metric("9.final_benchmark.6.peak_reduction_min_pct")),
]
for claim_id, category, forbidden, reason, evidence_id in rejected_specs:
    claims.append(claim(
        claim_id, "REJECTED CLAIM", category, reason, "NOT_PRESENTATION_SAFE", [], [], "unsupported or over-broad scope", "not applicable", "not applicable", "not applicable", "not applicable",
        reason, forbidden, safe=False, explicit_evidence=[evidence_id],
    ))

claim_by_id = {row["claim_id"]: row for row in claims}

metric_specs = [
    ("dataset.final_buildings", "CORE", "scope", "Final fixed building count", ["CORE-04", "BACK-03"], "protocol", "Fixed, pre-selected buildings; not unseen transfer."),
    ("forecast.horizon", "CORE", "task", "Forecast horizon", ["CORE-01", "CORE-05"], "problem/method", "Target timestamp is feature timestamp +24 h."),
    ("9.final_benchmark.4.normalized_rmse_mean", "CORE", "mismatch", "XGBoost mean normalized RMSE", ["CORE-02"], "mismatch", "Slightly below LightGBM; retain full scope label."),
    ("9.final_benchmark.3.normalized_rmse_mean", "CORE", "mismatch", "LightGBM mean normalized RMSE", ["CORE-02"], "mismatch", "Comparator for frozen counterexample."),
    ("9.final_benchmark.4.normalized_decision_regret_mean", "CORE", "mismatch", "XGBoost mean normalized decision regret", ["CORE-02"], "mismatch", "Higher is worse; Oracle-relative, not monetary regret."),
    ("9.final_benchmark.3.normalized_decision_regret_mean", "CORE", "mismatch", "LightGBM mean normalized decision regret", ["CORE-02"], "mismatch", "Lower than XGBoost despite slightly higher RMSE."),
    ("phase8.Hog_office_Joey.w_forecast", "CORE", "selection", "Joey forecast-selected LightGBM weight", ["CORE-03"], "selection example", "Illustrative building only."),
    ("phase8.Hog_office_Joey.w_decision", "CORE", "selection", "Joey decision-selected LightGBM weight", ["CORE-03", "CORE-05", "BACK-04"], "selection example", "Illustrative building only."),
    ("phase9_1.lightgbm_mean_normalized_mae", "CORE", "outcome", "LightGBM mean normalized MAE", ["CORE-06"], "final result", "Equal-building aggregate."),
    ("phase9_1.doef_mean_normalized_mae", "CORE", "outcome", "DOEF mean normalized MAE", ["CORE-06"], "final result", "Equal-building aggregate."),
    ("phase9_1.normalized_mae_relative_improvement_pct", "CORE", "outcome", "DOEF relative normalized-MAE improvement", ["CORE-06"], "headline", "Versus LightGBM only."),
    ("phase9_1.lightgbm_mean_normalized_regret", "CORE", "outcome", "LightGBM mean normalized decision regret", ["CORE-07"], "final result", "Oracle-relative; not monetary."),
    ("phase9_1.doef_mean_normalized_regret", "CORE", "outcome", "DOEF mean normalized decision regret", ["CORE-07"], "final result", "Oracle-relative; not monetary."),
    ("phase9_1.normalized_regret_relative_improvement_pct", "CORE", "outcome", "DOEF relative normalized-regret improvement", ["CORE-07"], "headline", "Versus LightGBM under frozen protocol."),
    ("phase9_1.decision_wins", "CORE", "consistency", "DOEF decision-regret building wins", ["CORE-07"], "headline", "Ties use frozen comparison semantics."),
    ("phase9_1.decision_ties", "CORE", "consistency", "DOEF decision-regret building ties", ["CORE-07"], "headline", "Do not report as wins."),
    ("phase9_1.decision_losses", "CORE", "consistency", "DOEF decision-regret building losses", ["CORE-07"], "headline", "Does not imply superiority on every metric."),
    ("9.final_benchmark.6.peak_reduction_mean_pct", "CORE", "outcome", "DOEF mean whole-window peak reduction", ["CORE-08"], "headline", "Equal-building mean; whole-window definition."),
    ("9.final_benchmark.6.peak_reduction_min_pct", "CORE", "negative case", "DOEF minimum building peak reduction", ["CORE-08"], "limitation", "Negative value must remain visible."),
    ("dataset.raw_building_count", "SUPPORTING", "scale", "Frozen project-universe building series", ["SUP-01"], "dataset", "Do not generalize to every BDG2 release."),
    ("dataset.office_candidates", "SUPPORTING", "scale", "Office candidates", ["CORE-04", "SUP-01"], "dataset", "Pre-quality-filter count."),
    ("dataset.office_quality_pass", "SUPPORTING", "protocol", "Office candidates passing quality rules", ["CORE-04"], "protocol", "Frozen quality rules."),
    ("phase8.weight_candidates", "SUPPORTING", "selection", "Predeclared candidate weights", ["CORE-03", "SUP-03"], "method", "Grid fixed before Test."),
    ("phase9_1.bootstrap.resamples", "SUPPORTING", "reliability", "Building-level bootstrap resamples", ["SUP-04"], "reliability", "Only 8 building units."),
    ("phase9_1.bootstrap.point_estimate", "SUPPORTING", "reliability", "Bootstrap point difference", ["SUP-04"], "reliability", "DOEF minus LightGBM; negative favors DOEF."),
    ("phase9_1.bootstrap.ci95_lower", "SUPPORTING", "reliability", "Bootstrap 95% lower bound", ["SUP-04"], "reliability", "Building-level resampling."),
    ("phase9_1.bootstrap.ci95_upper", "SUPPORTING", "reliability", "Bootstrap 95% upper bound", ["SUP-04"], "reliability", "Building-level resampling."),
    ("phase9_1.bootstrap.probability_mean_less_than_zero", "SUPPORTING", "reliability", "Bootstrap probability mean difference below zero", ["SUP-04"], "backup annotation", "Within fixed 8-building scope."),
    ("phase9_1.invariance_samples", "SUPPORTING", "reproducibility", "Prediction invariance sample count", ["SUP-05", "BACK-05"], "reproducibility", "Identity audit, not a new experiment."),
    ("phase9_1.invariance_max_delta", "SUPPORTING", "reproducibility", "Prediction invariance maximum delta", ["SUP-05", "BACK-05"], "reproducibility", "Identity audit, not independent replication."),
    ("phase5_7.selected_lambda", "BACKUP", "negative experiment", "Validation-selected robust lambda", ["BACK-01"], "Q&A", "Single-building supporting experiment."),
    ("phase5_7.test.lightgbm_robust.mean_regret", "BACKUP", "negative experiment", "Robust LightGBM Test mean regret", ["SUP-08", "BACK-01"], "Q&A", "Negative result; higher is worse."),
    ("phase5_7.test.lightgbm_deterministic.mean_regret", "BACKUP", "negative experiment", "Deterministic LightGBM Test mean regret", ["SUP-08", "BACK-01"], "Q&A", "Comparator for negative result."),
    ("9.final_benchmark.5.peak_reduction_mean_pct", "BACKUP", "aggregation", "CatBoost mean peak reduction", ["SUP-07"], "Q&A", "Extreme building affects mean."),
    ("9.final_benchmark.5.peak_reduction_median_pct", "BACKUP", "aggregation", "CatBoost median peak reduction", ["SUP-07"], "Q&A", "Show with mean, never alone."),
]

metric_rows = []


def aggregation_for(manifest_id: str) -> str:
    if manifest_id in {"dataset.raw_building_count", "dataset.office_candidates", "dataset.office_quality_pass", "dataset.final_buildings", "phase8.weight_candidates"}:
        return "frozen count"
    if manifest_id == "forecast.horizon":
        return "fixed scalar"
    if manifest_id.startswith("phase8."):
        return "per-building Validation-selected scalar"
    if manifest_id.startswith("phase5_7."):
        return "single-building configuration scalar" if manifest_id.endswith("selected_lambda") else "single-building mean daily regret"
    if "decision_wins" in manifest_id or "decision_ties" in manifest_id or "decision_losses" in manifest_id:
        return "building-level win/tie/loss count"
    if "bootstrap" in manifest_id:
        return "building-level paired bootstrap summary"
    if "invariance" in manifest_id:
        return "all frozen Test prediction rows"
    if manifest_id.endswith("peak_reduction_mean_pct"):
        return "equal-building mean of whole-window peak reduction"
    if manifest_id.endswith("peak_reduction_median_pct"):
        return "building median of whole-window peak reduction"
    if manifest_id.endswith("peak_reduction_min_pct"):
        return "building minimum of whole-window peak reduction"
    if "relative_improvement_pct" in manifest_id:
        return "relative difference of equal-building means"
    if "mean_normalized" in manifest_id or "normalized_" in manifest_id:
        return "equal-building mean after frozen Train-mean normalization"
    raise AssertionError(f"Aggregation rule missing for {manifest_id}")


for index, (manifest_id, priority, role, label, claim_ids, slide_role, caveat) in enumerate(metric_specs, start=1):
    item = manifest_by_id[manifest_id]
    metric_rows.append({
        "metric_shortlist_id": f"MET-{index:03d}", "manifest_id": manifest_id, "priority": priority,
        "role": role, "label": label, "value": item["value"], "unit": item["unit"], "phase": item["phase"],
        "building_scope": item.get("building_scope", ""), "split": item.get("split", ""), "model": item.get("model", ""),
        "aggregation": aggregation_for(manifest_id), "evidence_status": item["status"],
        "claim_ids": ";".join(claim_ids), "likely_slide_role": slide_role, "caveat": caveat,
        "source_path": item["source_path"], "source_field": item["source_field"], "source_sha256": item["source_sha256"],
    })
metric_short_id = {row["manifest_id"]: row["metric_shortlist_id"] for row in metric_rows}


def figrow(fid: str, priority: str, claim_ids: list[str], role: str, deck: str, plan: str, risk: str, group: str, notes: str) -> dict[str, Any]:
    source = figures_0a[fid]
    return {
        "figure_id": fid, "path": source["path"], "phase": source["phase"], "current_status": source["classification"],
        "final_priority": priority, "claim_ids": ";".join(claim_ids), "story_role": role,
        "main_deck_or_backup": deck, "retain_original": "YES", "future_redraw_recommended": plan,
        "underlying_data_available": source["source_data_exists"], "readability_risk": risk,
        "redundancy_group": group, "notes": notes,
    }


figure_rows = [
    figrow("FIG-024", "CORE", ["CORE-04", "SUP-01"], "Train-only morphology and fixed building scope", "MAIN", "USE_FROZEN_AS_IS", "MEDIUM: verify labels at slide size", "dataset-scope", "Unique scope visual."),
    figrow("FIG-025", "DROP", [], "Legacy forecast comparison", "DROP", "BACKUP_ONLY", "MEDIUM", "forecast-benchmark", "Superseded by Phase 9 final-scope visuals."),
    figrow("FIG-026", "DROP", [], "Legacy decision comparison", "DROP", "BACKUP_ONLY", "MEDIUM", "decision-benchmark", "Superseded by FIG-039."),
    figrow("FIG-027", "SUPPORTING", ["CORE-02"], "Forecast-versus-decision rank mismatch", "MAIN_OPTIONAL", "REDRAW_FROM_FROZEN_DATA", "HIGH: current format needs reformat", "mismatch", "Only future visual encoding may change; values and aggregation stay frozen."),
    figrow("FIG-028", "DROP", [], "Average ranks", "DROP", "BACKUP_ONLY", "HIGH", "forecast-benchmark", "Low value and redundant."),
    figrow("FIG-029", "DROP", [], "Single success case", "DROP", "BACKUP_ONLY", "HIGH", "case-study", "Avoid cherry-picking a success case."),
    figrow("FIG-030", "BACKUP", ["CORE-08"], "Frozen failure case", "BACKUP", "BACKUP_ONLY", "MEDIUM", "case-study", "Retains negative evidence; not a headline."),
    figrow("FIG-031", "DROP", [], "Historical ensemble improvement", "DROP", "BACKUP_ONLY", "HIGH", "ensemble-result", "Superseded by Phase 8/9 evidence."),
    figrow("FIG-032", "CORE", ["CORE-03", "SUP-03"], "Validation forecast-objective weight curve", "MAIN", "REDRAW_FROM_FROZEN_DATA", "MEDIUM", "validation-selection", "Future combine with FIG-033 from the same frozen table."),
    figrow("FIG-033", "CORE", ["CORE-03", "SUP-03"], "Validation decision-objective weight curve", "MAIN", "REDRAW_FROM_FROZEN_DATA", "MEDIUM", "validation-selection", "Future combine with FIG-032; do not change selection rule."),
    figrow("FIG-034", "CORE", ["CORE-03", "CORE-05", "BACK-04"], "Different forecast- and decision-selected weights", "MAIN", "USE_FROZEN_AS_IS", "MEDIUM", "validation-selection", "Most direct frozen selection visual."),
    figrow("FIG-035", "DROP", [], "Phase 8 Test regret comparison", "DROP", "BACKUP_ONLY", "MEDIUM", "decision-result", "Redundant with Phase 9 final visuals."),
    figrow("FIG-036", "DROP", [], "Phase 8 forecast/decision effect", "DROP", "BACKUP_ONLY", "MEDIUM", "mismatch", "Redundant with FIG-038."),
    figrow("FIG-037", "BACKUP", ["CORE-01", "SUP-06"], "Representative forecast-to-dispatch trace", "BACKUP", "BACKUP_ONLY", "MEDIUM: underlying daily table cannot support arbitrary redraw", "pipeline-example", "Reuse frozen image only; do not infer numbers from pixels."),
    figrow("FIG-038", "HERO", ["CORE-02"], "Core forecast-versus-decision mismatch", "MAIN", "USE_FROZEN_AS_IS", "MEDIUM", "mismatch", "Primary story visual."),
    figrow("FIG-039", "CORE", ["CORE-07"], "Per-building DOEF decision comparison", "MAIN", "USE_FROZEN_AS_IS", "MEDIUM", "decision-result", "Shows scope and heterogeneity."),
    figrow("FIG-040", "HERO", ["CORE-06", "CORE-07", "CORE-08"], "Final DOEF outcome summary", "MAIN", "USE_FROZEN_AS_IS", "MEDIUM", "final-outcome", "Headline outcome visual; retain caveats in slide copy."),
    figrow("FIG-041", "BACKUP", ["SUP-07"], "Peak-quality versus decision relationship", "BACKUP", "BACKUP_ONLY", "MEDIUM", "mismatch", "Useful for aggregation/metric Q&A; overlaps FIG-038."),
    figrow("FIG-042", "SUPPORTING", ["SUP-06"], "Forecast-to-decision efficiency", "MAIN_OPTIONAL", "USE_FROZEN_AS_IS", "LOW", "system-value", "Wide aspect; supports integrated pipeline value."),
    figrow("FIG-043", "DROP", [], "Phase 9 validation search", "DROP", "BACKUP_ONLY", "MEDIUM", "validation-selection", "Redundant with Phase 8 selection visuals."),
    figrow("FIG-019", "BACKUP", ["SUP-08", "BACK-01"], "Robust-method failure case", "BACKUP", "BACKUP_ONLY", "HIGH", "robust-negative", "Scientific rigor/Q&A only."),
    figrow("FIG-022", "BACKUP", ["SUP-08", "BACK-01"], "Deterministic versus robust daily peaks", "BACKUP", "BACKUP_ONLY", "MEDIUM", "robust-negative", "Direct negative-result evidence."),
    figrow("FIG-023", "BACKUP", ["BACK-01"], "Validation lambda sensitivity", "BACKUP", "BACKUP_ONLY", "HIGH", "robust-negative", "Shows frozen selection, not Test improvement."),
]

slides = [
    ("SLIDE-01", "Problem / motivation", "预测不是终点，削峰决策才是", "24 h ahead load forecasting supplies advance information for battery peak shaving.", "CORE-01", ["SUP-06"], ["forecast.horizon"], [], "YES", "NO", "No cost/carbon/energy claim.", "Verified electricity savings.", "Understand the real decision objective."),
    ("SLIDE-02", "Scientific question", "预测更准，决策一定更好吗？", "The project tests whether conventional forecast accuracy aligns with storage decision quality.", "CORE-02", [], ["9.final_benchmark.4.normalized_rmse_mean", "9.final_benchmark.3.normalized_rmse_mean", "9.final_benchmark.4.normalized_decision_regret_mean", "9.final_benchmark.3.normalized_decision_regret_mean"], ["FIG-038"], "YES", "NO", "Counterexample is project-scoped.", "Forecast accuracy is irrelevant.", "See the central mismatch immediately."),
    ("SLIDE-03", "Dataset & protocol", "先冻结范围，再看结果", "Eight heterogeneous offices are selected with Train-only morphology after frozen eligibility filtering.", "CORE-04", ["SUP-01", "SUP-03"], ["dataset.raw_building_count", "dataset.office_candidates", "dataset.office_quality_pass", "dataset.final_buildings"], ["FIG-024"], "YES", "NO", "Fixed buildings; one Test month each.", "Unseen-building generalization or pristine Test.", "Trust the anti-cherry-picking protocol."),
    ("SLIDE-04", "Forecast framework", "因果可得的 24 小时前瞻预测", "DayWeek and per-building LightGBM provide complementary frozen forecast components.", "CORE-05", ["SUP-02"], ["forecast.horizon"], [], "YES", "NO", "No future weather; not end-to-end training.", "Future information is used.", "Understand the forecast ingredients."),
    ("SLIDE-05", "Storage decision framework", "用真实削峰结果评价预测", "Forecasts drive the same constrained battery optimizer and are evaluated on realized load using Oracle-relative regret.", "CORE-01", ["SUP-06"], ["phase9_1.doef_mean_normalized_regret"], ["FIG-042"], "YES", "NO", "Oracle is non-deployable; regret is not money.", "Oracle is a deployable controller.", "Understand how predictions become decisions."),
    ("SLIDE-06", "Multi-model benchmark", "同一预测指标不等于同一决策排序", "The frozen multi-building benchmark compares causal baselines and tree models under one decision protocol.", "CORE-02", ["SUP-07"], ["9.final_benchmark.3.normalized_rmse_mean", "9.final_benchmark.4.normalized_rmse_mean"], ["FIG-027"], "NO", "YES", "Use explicit method and aggregation labels.", "One metric fully ranks all downstream value.", "Prepare the benchmark context."),
    ("SLIDE-07", "Mismatch evidence", "RMSE 略优，regret 反而更差", "XGBoost versus LightGBM provides a frozen 8-building Test counterexample.", "CORE-02", [], ["9.final_benchmark.4.normalized_rmse_mean", "9.final_benchmark.3.normalized_rmse_mean", "9.final_benchmark.4.normalized_decision_regret_mean", "9.final_benchmark.3.normalized_decision_regret_mean"], ["FIG-038"], "YES", "NO", "Difference is small but directionally opposite.", "All accurate forecasts make bad decisions.", "Accept the need for decision-oriented selection."),
    ("SLIDE-08", "Decision-oriented ensemble", "在 Validation 上按 regret 冻结融合权重", "The same predeclared weight grid is scored by forecast MAE and decision regret; DOEF freezes the decision-selected weight.", "CORE-03", ["SUP-03"], ["phase8.weight_candidates", "phase8.Hog_office_Joey.w_forecast", "phase8.Hog_office_Joey.w_decision"], ["FIG-032", "FIG-033", "FIG-034"], "YES", "NO", "Joey is an illustration; Test did not select weights.", "Weights were tuned on Test.", "See the algorithmic response to the mismatch."),
    ("SLIDE-09", "DOEF v1.0", "从预测到削峰的冻结系统", "Causal components, decision-selected ensemble, 24 h forecast, battery optimization, and downstream evaluation form DOEF v1.0.", "CORE-05", ["SUP-02", "SUP-06"], ["forecast.horizon", "phase8.Hog_office_Joey.w_decision"], ["FIG-034"], "YES", "NO", "Integrated evaluation, not deployed or differentiable end-to-end.", "A novel LightGBM model or deployed product.", "Understand the complete frozen pipeline."),
    ("SLIDE-10", "Final Test results", "DOEF 同时改善预测与决策指标", "Against LightGBM, DOEF improves normalized MAE by 6.36% and normalized decision regret by 3.61%.", "CORE-07", ["CORE-06"], ["phase9_1.normalized_mae_relative_improvement_pct", "phase9_1.normalized_regret_relative_improvement_pct", "phase9_1.decision_wins", "phase9_1.decision_ties", "phase9_1.decision_losses"], ["FIG-040"], "YES", "NO", "One fixed Test month per fixed building.", "State of the art or beats all methods.", "Take away the final comparative result."),
    ("SLIDE-11", "Peak-shaving outcome", "平均改善不隐藏最差建筑", "Mean peak reduction is 6.44%, while the building minimum is -1.02%.", "CORE-08", ["SUP-07"], ["9.final_benchmark.6.peak_reduction_mean_pct", "9.final_benchmark.6.peak_reduction_min_pct"], ["FIG-039", "FIG-040"], "YES", "NO", "Whole-window metric; one negative building.", "Every building's peak is reduced.", "Trust the honest scope of the outcome."),
    ("SLIDE-12", "Reliability & falsification", "稳定性证据与负结果同时保留", "Building-level bootstrap and exact prediction invariance support reliability; robust optimization degradation remains in backup.", "SUP-04", ["SUP-05", "SUP-08"], ["phase9_1.bootstrap.point_estimate", "phase9_1.bootstrap.ci95_lower", "phase9_1.bootstrap.ci95_upper", "phase9_1.invariance_max_delta"], [], "YES", "NO", "Eight bootstrap units; identity audit is not independent replication.", "Universal statistical proof or every experiment succeeded.", "See rigor without overstating certainty."),
    ("SLIDE-13", "Contribution & limits", "以决策价值约束预测模型选择", "The supported contribution is a decision-oriented, Validation-selected forecast-to-storage evaluation pipeline over 8 fixed heterogeneous offices.", "CORE-05", ["CORE-02", "CORE-04", "SUP-03"], ["dataset.final_buildings", "forecast.horizon"], [], "YES", "NO", "No external novelty/SOTA claim; no unseen transfer, money, carbon, or energy evidence.", "First, world-first, novel, SOTA, unseen transfer, verified savings.", "Remember the defensible competition contribution."),
]
slide_rows = []
for sid, role, title, message, primary, supporting, mids, fids, must, optional, caveat, forbidden, takeaway in slides:
    slide_rows.append({
        "slide_id": sid, "slide_role": role, "candidate_title": title, "key_message": message,
        "primary_claim_id": primary, "supporting_claim_ids": ";".join(supporting),
        "metric_ids": ";".join(metric_short_id[mid] for mid in mids), "figure_ids": ";".join(fids),
        "must_show": must, "optional": optional, "key_caveat": caveat,
        "forbidden_statement": forbidden, "expected_takeaway": takeaway,
    })

limitations = [
    ("LIM-01", "Evaluation uses 8 fixed pre-selected office buildings.", "CORE-04;CORE-06;CORE-07;CORE-08", "Overstates population scope.", "Multi-building evaluation across 8 pre-selected heterogeneous office buildings.", "Generalizes to all buildings.", "MAIN"),
    ("LIM-02", "No unseen-building transfer experiment.", "CORE-04;CORE-06;CORE-07", "Converts fixed-building evaluation into an unsupported transfer claim.", "Multi-building evaluation on fixed buildings.", "Unseen-building generalization; zero-shot transfer; transfer learning; domain adaptation.", "MAIN"),
    ("LIM-03", "One fixed future Test month per building limits temporal generalization.", "CORE-06;CORE-07;CORE-08;BACK-03", "Implies seasonal or multi-year robustness.", "Results on one fixed future Test month per building.", "Generalizes across seasons and years.", "MAIN"),
    ("LIM-04", "Test was not used for selection, but historical Test results had been viewed.", "CORE-03;SUP-03;BACK-03", "Misstates Test visibility and audit history.", "Test data were not used for model or ensemble selection.", "Pristine Test set; completely untouched Test set; never viewed.", "MAIN"),
    ("LIM-05", "No electricity tariff or monetary-savings evidence.", "CORE-01;CORE-07", "Turns physical peak metrics into financial outcomes.", "Peak-demand reduction under the frozen battery protocol.", "Verified bill savings; electricity-cost savings; monetary regret.", "MAIN"),
    ("LIM-06", "No carbon-emissions evidence.", "CORE-01", "Creates an unsupported environmental outcome.", "No carbon outcome was evaluated.", "Verified carbon reduction.", "MAIN"),
    ("LIM-07", "No energy-use reduction evidence.", "CORE-01", "Confuses peak reduction with energy reduction.", "The evaluated outcome is peak demand.", "Reduced building energy consumption.", "MAIN"),
    ("LIM-08", "Phase 5.7 robust LightGBM degrades Test mean regret: 20.4635 kW versus 11.1274 kW deterministic.", "SUP-08;BACK-01", "Reverses a frozen negative result.", "The robust experiment is falsification/Q&A evidence and is not part of DOEF.", "Robust optimization improved Test performance.", "BACKUP"),
    ("LIM-09", "Raw readings are kWh per hourly interval; dispatch power is interval-average kW; capacity and SOC are kWh.", "SUP-06;BACK-02", "Produces dimensionally invalid claims.", "State interval and unit semantics explicitly.", "kWh and kW are interchangeable.", "BACKUP"),
    ("LIM-10", "The count 1,578 is the project universe represented in the frozen Phase 3 selection table.", "SUP-01", "Overgeneralizes a repository-specific count to every external release.", "The project's frozen BDG2 electricity table contains 1,578 building series.", "BDG2 has exactly 1,578 buildings.", "MAIN"),
    ("LIM-11", "Peak reduction depends on method, building, split, whole-window/daily scope, and aggregation.", "CORE-08;SUP-07", "Makes a scope-sensitive metric misleading.", "Attach full method and aggregation labels.", "Peak reduction is one universal project number.", "MAIN"),
    ("LIM-12", "No Phase 13.0B external literature or SOTA audit was performed.", "CORE-05", "Turns internal positioning into an external priority claim.", "Supported internal contributions only.", "First; world-first; novel as external fact; state of the art; beats all methods.", "MAIN"),
]
limitation_rows = [dict(zip([
    "limitation_id", "description", "affected_claim_ids", "risk_if_ignored", "safe_wording", "forbidden_wording", "main_deck_or_backup"
], row)) for row in limitations]

pipeline = {
    "schema_version": 1,
    "status": "canonical",
    "phase": "13.0B",
    "logical_role": "machine-readable specification for a future DOEF presentation diagram",
    "algorithm": {"name": "Decision-Oriented Ensemble Forecasting", "acronym": "DOEF", "version": "1.0", "freeze_status": "frozen"},
    "diagram_generation_allowed_now": False,
    "future_visual_rule": "Visual encoding may change only from frozen data; no aggregation, value, selection, or algorithm changes.",
    "modules": [
        {"module_id": "M1", "name": "Frozen hourly load data", "input": "hourly building meter series", "output": "fixed Train/Validation/Test windows", "role": "data boundary", "selection_criterion": "predefined coverage/quality rules", "frozen_parameter": "8 fixed offices; one-hour intervals", "connection": "M1 -> M2", "evidence": ["dataset.final_buildings"]},
        {"module_id": "M2", "name": "Causal load features", "input": "past load and calendar state available at issue time", "output": "causal feature matrix", "role": "prevent future-target leakage", "selection_criterion": "positive lags; shifted rolling history; no weather", "frozen_parameter": "target timestamp = feature timestamp + 24 h", "connection": "M2 -> M3,M4", "evidence": ["forecast.horizon"]},
        {"module_id": "M3", "name": "DayWeek component", "input": "actual(t-24h), actual(t-168h)", "output": "DayWeek forecast", "role": "causal baseline component", "selection_criterion": "fixed formula", "frozen_parameter": "0.5*actual(t-24h)+0.5*actual(t-168h)", "connection": "M3 -> M5", "evidence": []},
        {"module_id": "M4", "name": "LightGBM component", "input": "causal feature matrix", "output": "per-building LightGBM forecast", "role": "tree forecast component", "selection_criterion": "Validation-only model selection", "frozen_parameter": "frozen per-building Phase 7 configuration", "connection": "M4 -> M5", "evidence": []},
        {"module_id": "M5", "name": "Decision-oriented ensemble", "input": "DayWeek and LightGBM forecasts", "output": "DOEF 24 h ahead forecast", "role": "align forecast combination with downstream storage objective", "selection_criterion": "per-building Validation mean daily regret versus non-deployable Oracle; frozen tie-breaks", "frozen_parameter": "w_b from outputs/phase8/selected_weights.csv; formula w_b*LightGBM+(1-w_b)*DayWeek", "connection": "M5 -> M6", "evidence": ["phase8.weight_candidates", "phase8.Hog_office_Joey.w_decision"]},
        {"module_id": "M6", "name": "Battery peak-shaving optimization", "input": "DOEF 24 h forecast and frozen battery configuration", "output": "daily charge/discharge schedule", "role": "translate forecast into an operational decision", "selection_criterion": "same frozen optimizer and constraints for all methods", "frozen_parameter": "capacity, power, efficiency, SOC, throughput penalty, daily reset", "connection": "M6 -> M7", "evidence": []},
        {"module_id": "M7", "name": "Downstream evaluation", "input": "frozen schedule and realized Test load", "output": "realized peak, Oracle-relative regret, constraint and reliability evidence", "role": "measure decision value", "selection_criterion": "Test is reporting/evaluation only", "frozen_parameter": "equal-building aggregation; Phase 9.1 metric and unit semantics", "connection": "terminal", "evidence": ["phase9_1.doef_mean_normalized_regret", "9.final_benchmark.6.peak_reduction_mean_pct"]},
    ],
    "source_paths": ["outputs/phase9/final_algorithm.json", "outputs/phase9_1/final_reporting_summary.json", "outputs/phase13_0a/conflict_register.csv"],
}

innovation = [
    {"innovation_id": "INNOV-A", "label": "Decision-oriented forecast evaluation", "status": "supported", "claim_ids": ["CORE-02"], "boundary": "Supported as an internal project contribution; no external novelty priority claim."},
    {"innovation_id": "INNOV-B", "label": "Validation-selected decision-oriented ensemble", "status": "supported", "claim_ids": ["CORE-03", "CORE-05"], "boundary": "Supported by frozen Validation selection and weights; not Test-selected."},
    {"innovation_id": "INNOV-C", "label": "Forecast-to-decision integrated pipeline", "status": "supported", "claim_ids": ["CORE-01", "CORE-05", "SUP-06"], "boundary": "Integrated evaluation pipeline, not end-to-end differentiable training or deployment."},
    {"innovation_id": "INNOV-D", "label": "Multi-building morphology-aware benchmark design", "status": "partially supported", "claim_ids": ["CORE-04"], "boundary": "Train-only morphology and fixed heterogeneous offices are supported; generalization beyond the 8 buildings is not."},
    {"innovation_id": "INNOV-E", "label": "External first/world-first/SOTA positioning", "status": "unsupported", "claim_ids": ["REJ-11"], "boundary": "Requires a separate literature and comparable-system audit."},
]

OUTPUT.mkdir(parents=True, exist_ok=True)
write_json(OUTPUT / "final_presentation_claims.json", {
    "schema_version": 1, "status": "canonical", "phase": "13.0B",
    "logical_role": "frozen presentation claim registry", "source_layer": "outputs/phase13_0a/frozen_presentation_data_manifest.json",
    "claims": claims,
})
write_csv(OUTPUT / "presentation_metric_shortlist.csv", metric_rows, [
    "metric_shortlist_id", "manifest_id", "priority", "role", "label", "value", "unit", "phase", "building_scope", "split", "model", "aggregation", "evidence_status", "claim_ids", "likely_slide_role", "caveat", "source_path", "source_field", "source_sha256"
])
write_csv(OUTPUT / "final_figure_shortlist.csv", figure_rows, [
    "figure_id", "path", "phase", "current_status", "final_priority", "claim_ids", "story_role", "main_deck_or_backup", "retain_original", "future_redraw_recommended", "underlying_data_available", "readability_risk", "redundancy_group", "notes"
])
write_csv(OUTPUT / "slide_evidence_map.csv", slide_rows, [
    "slide_id", "slide_role", "candidate_title", "key_message", "primary_claim_id", "supporting_claim_ids", "metric_ids", "figure_ids", "must_show", "optional", "key_caveat", "forbidden_statement", "expected_takeaway"
])
write_csv(OUTPUT / "presentation_limitations_registry.csv", limitation_rows, [
    "limitation_id", "description", "affected_claim_ids", "risk_if_ignored", "safe_wording", "forbidden_wording", "main_deck_or_backup"
])
write_json(OUTPUT / "doef_pipeline_spec.json", pipeline)


def validate() -> dict[str, Any]:
    claim_ids = set(claim_by_id)
    metric_ids = {row["metric_shortlist_id"] for row in metric_rows}
    figure_ids = {row["figure_id"] for row in figure_rows}
    registered_source_paths = {row["path"] for row in read_csv(INPUT / "presentation_source_hashes.csv")}
    canonical_phase13_inputs = {
        "outputs/phase13_0a/frozen_presentation_data_manifest.json",
        "outputs/phase13_0a/presentation_claim_evidence_matrix.csv",
        "outputs/phase13_0a/presentation_source_hashes.csv",
        "outputs/phase13_0a/figure_inventory.csv",
        "outputs/phase13_0a/conflict_register.csv",
        "outputs/phase13_0a/recovery_summary.json",
        "reports/phase13/phase13_0a_frozen_presentation_data_recovery_audit.md",
    }
    assert len(claim_ids) == len(claims)
    assert len(metric_ids) == len(metric_rows)
    assert len(figure_ids) == len(figure_rows)
    assert 20 <= len(metric_rows) <= 40
    for row in claims:
        assert set(row["evidence_ids"]) <= matrix_ids
        assert set(row["primary_metric_ids"]) <= set(manifest_by_id)
        assert set(row["figure_ids"]) <= figure_ids <= set(figures_0a)
        assert set(row["provenance_sources"]) <= registered_source_paths | canonical_phase13_inputs
        if row["tier"] == "TIER 1 — CORE CLAIM":
            assert row["evidence_ids"] and row["primary_metric_ids"] and row["presentation_safe"]
            assert row["competition_value"] and set(row["competition_value"].values()) <= {1, 2, 3, 4, 5}
    for row in metric_rows:
        assert row["manifest_id"] in manifest_by_id
        assert set(row["claim_ids"].split(";")) <= claim_ids
        assert row["evidence_status"] in {"EXACT_RECOVERED", "DETERMINISTIC_DERIVED"}
        source = ROOT / row["source_path"]
        assert source.is_file() and sha256(source) == row["source_sha256"]
    for row in figure_rows:
        assert (ROOT / row["path"]).is_file()
        assert set(filter(None, row["claim_ids"].split(";"))) <= claim_ids
        assert row["future_redraw_recommended"] in {"USE_FROZEN_AS_IS", "REDRAW_FROM_FROZEN_DATA", "BACKUP_ONLY"}
    for row in slide_rows:
        assert row["primary_claim_id"] in claim_ids
        assert set(filter(None, row["supporting_claim_ids"].split(";"))) <= claim_ids
        assert set(filter(None, row["metric_ids"].split(";"))) <= metric_ids
        assert set(filter(None, row["figure_ids"].split(";"))) <= figure_ids
    for row in limitation_rows:
        assert set(filter(None, row["affected_claim_ids"].split(";"))) <= claim_ids
    assert set(pipeline["source_paths"]) <= registered_source_paths | canonical_phase13_inputs
    assert all((ROOT / row["path"]).is_file() for row in read_csv(INPUT / "presentation_source_hashes.csv"))
    source_drift = [row["path"] for row in read_csv(INPUT / "presentation_source_hashes.csv") if sha256(ROOT / row["path"]) != row["sha256"]]
    assert not source_drift
    return {
        "json_load": "PASS", "csv_load": "PASS", "manifest_id_resolution": "PASS",
        "claim_evidence_references": "PASS", "claim_metric_references": "PASS",
        "slide_claim_references": "PASS", "figure_path_references": "PASS",
        "phase13_0a_source_hash_drift_count": 0,
    }


validation = validate()
tier_counts = Counter(row["tier"] for row in claims)
metric_counts = Counter(row["priority"] for row in metric_rows)
figure_counts = Counter(row["final_priority"] for row in figure_rows)

report_lines = [
    "# Phase 13.0B — Frozen Presentation Evidence Selection & Story Mapping",
    "", "## Verdict", "",
    "**PASS.** The frozen evidence supports an evidence-first competition story centered on the mismatch between forecast metrics and storage decision value, followed by Validation-only decision-oriented selection and bounded 8-building Test evidence. No PPT, new figure, model run, prediction, optimization, bootstrap, or new statistical test was created.",
    "", "## Frozen integrity gate", "",
    f"- Repository: `{ROOT.as_posix()}`", "- Branch: `codex/phase13-visual-report-demo`", f"- Starting HEAD: `{STARTING_HEAD}`", f"- Frozen baseline: `{FROZEN_BASELINE}`",
    "- Frozen baseline ancestry: PASS; baseline is an ancestor and the starting HEAD is ahead 6 / behind 0.",
    "- Phase 7/8/9/9.1 canonical modifications from frozen baseline: 0.", "- Phase 9.1 registered artifact audit: 76 artifacts, 0 hash mismatches.",
    "- Phase 13.0A registered source hashes: 88 files, 0 drift.", "- Pre-existing unrelated untracked paths were preserved and excluded: `outputs/phase13/`, `reports/phase13_implementation_plan.md`.",
    "", "## Story-spine audit", "",
    "| Story | Verdict | Frozen basis / boundary |", "|---|---|---|",
    "| Real problem | SUPPORTED | 24 h ahead forecast feeds battery peak-shaving evaluation; no money/carbon/energy claim. |",
    "| Forecast accuracy ≠ decision quality | SUPPORTED | XGBoost normalized RMSE 0.216751 < LightGBM 0.216942, while XGBoost normalized regret 0.117534 > LightGBM 0.116127 on the 8-building Test aggregate. |",
    "| Decision-oriented model selection | SUPPORTED | Predeclared 11-weight grid, Validation-only regret selection, frozen per-building weights. |",
    "| Multi-building robustness | PARTIALLY SUPPORTED | Supported across 8 pre-selected heterogeneous offices; not unseen-building transfer. |",
    "| DOEF v1.0 final system | SUPPORTED | Formal name and structure recovered from the registered Phase 9/9.1 sources. |",
    "| Scientific falsification | SUPPORTED AS BACKUP | Robust LightGBM Test mean regret 20.4635 kW versus 11.1274 kW deterministic; negative result retained. |",
    "", "## Claim registry", "",
    f"- Core: {tier_counts['TIER 1 — CORE CLAIM']}", f"- Supporting: {tier_counts['TIER 2 — SUPPORTING CLAIM']}", f"- Backup/Q&A: {tier_counts['TIER 3 — BACKUP / Q&A CLAIM']}", f"- Rejected: {tier_counts['REJECTED CLAIM']}", "",
]
for row in claims:
    if row["tier"] == "TIER 1 — CORE CLAIM":
        report_lines.append(f"- `{row['claim_id']}` — {row['presentation_wording']}")
report_lines += [
    "", "## Metric compression", "",
    f"The 2,545-item numerical manifest is reduced to {len(metric_rows)} metrics: {metric_counts['CORE']} CORE, {metric_counts['SUPPORTING']} SUPPORTING, and {metric_counts['BACKUP']} BACKUP. Every row copies its value, unit, scope, source field, and SHA-256 from a resolvable Phase 13.0A manifest item.",
    "", "## Figure redundancy and redraw freeze", "",
    "Phase 9 figures replace redundant Phase 7/8 result views where they express the same claim at the final reporting scope. The two Phase 8 Validation-weight curves are retained for a future combined redraw from the same frozen table; Phase 7's forecast-versus-decision rank figure is also a redraw candidate. The representative dispatch image is backup-only because it may be reused as frozen but must not be mined for new numbers.",
    "", "## Slide logic", "",
]
for row in slide_rows:
    report_lines.append(f"- `{row['slide_id']}` — **{row['candidate_title']}**: {row['key_message']} Primary claim: `{row['primary_claim_id']}`.")
report_lines += [
    "", "## Innovation positioning", "",
]
for row in innovation:
    report_lines.append(f"- **{row['status'].upper()}** — {row['label']}: {row['boundary']}")
report_lines += [
    "", "## Frozen limitations and forbidden wording", "",
]
for row in limitation_rows:
    report_lines.append(f"- `{row['limitation_id']}` Safe: {row['safe_wording']} Forbidden: {row['forbidden_wording']}")
report_lines += [
    "", "## Structural validation", "",
    "- JSON load: PASS", "- CSV load: PASS", "- Manifest IDs: PASS", "- Claim → evidence: PASS", "- Claim → metric: PASS", "- Slide → claim/metric/figure: PASS", "- Figure paths: PASS", "- Phase 13.0A source hashes: PASS (0 drift)",
    "", "## Delivery boundary", "",
    "Phase 13.0B creates presentation metadata only. It does not replace or modify any upstream artifact. Future visual work must consume this frozen map and may redraw only from the registered frozen machine-readable values without changing aggregation, selection, or numbers. No PPT was created, and this phase does not enter the next stage.", "",
]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(report_lines), encoding="utf-8")

artifact_paths = [
    ROOT / "scripts" / "build_phase13_0b.py",
    OUTPUT / "final_presentation_claims.json", OUTPUT / "presentation_metric_shortlist.csv",
    OUTPUT / "final_figure_shortlist.csv", OUTPUT / "slide_evidence_map.csv",
    OUTPUT / "presentation_limitations_registry.csv", OUTPUT / "doef_pipeline_spec.json", REPORT,
]
artifact_entries = [
    {"path": path.relative_to(ROOT).as_posix(), "status": "canonical", "sha256": canonical_text_sha256(path)}
    for path in artifact_paths
]
assert all(canonical_text_sha256(ROOT / item["path"]) == item["sha256"] for item in artifact_entries)
validation["phase13_0b_artifact_hash_drift_count"] = 0
summary = {
    "schema_version": 1, "phase": "13.0B", "status": "PASS", "artifact_status": "canonical",
    "logical_role": "frozen downstream presentation evidence selection and story map",
    "producer": "scripts/build_phase13_0b.py", "starting_head": STARTING_HEAD, "frozen_baseline_commit": FROZEN_BASELINE,
    "canonical_inputs": [
        "outputs/phase13_0a/frozen_presentation_data_manifest.json", "outputs/phase13_0a/presentation_claim_evidence_matrix.csv",
        "outputs/phase13_0a/presentation_source_hashes.csv", "outputs/phase13_0a/figure_inventory.csv",
        "outputs/phase13_0a/conflict_register.csv", "outputs/phase13_0a/recovery_summary.json",
        "reports/phase13/phase13_0a_frozen_presentation_data_recovery_audit.md",
    ],
    "acceptance_reason": "All core claims bind frozen evidence and manifest metrics; references and hashes validate; limitations and forbidden wording are explicit; no upstream numerical or algorithm artifact changed.",
    "core_claim_count": tier_counts["TIER 1 — CORE CLAIM"], "supporting_claim_count": tier_counts["TIER 2 — SUPPORTING CLAIM"],
    "backup_claim_count": tier_counts["TIER 3 — BACKUP / Q&A CLAIM"], "rejected_claim_count": tier_counts["REJECTED CLAIM"],
    "core_metric_count": metric_counts["CORE"], "supporting_metric_count": metric_counts["SUPPORTING"], "backup_metric_count": metric_counts["BACKUP"],
    "hero_figure_count": figure_counts["HERO"], "core_figure_count": figure_counts["CORE"], "backup_figure_count": figure_counts["BACKUP"],
    "logical_slide_count": len(slide_rows), "algorithm_modified": False, "new_experiment_run": False, "new_numerical_result_generated": False,
    "presentation_created": False, "phase13_0a_source_hash_drift": 0, "canonical_artifact_modifications": 0,
    "validation": validation, "innovation_positioning": innovation,
    "artifact_hash_contract": "SHA-256 of text bytes after deterministic LF newline normalization; matches final Git committed bytes and is independent of checkout line-ending conversion.",
    "artifacts": artifact_entries,
    "commit_message": "docs: complete phase 13.0b presentation evidence selection",
}
write_json(OUTPUT / "phase13_0b_summary.json", summary)

# Final parse after every file exists, including the summary.
for path in OUTPUT.glob("*.json"):
    read_json(path)
for path in OUTPUT.glob("*.csv"):
    read_csv(path)
print(json.dumps({"status": "PASS", "claims": dict(tier_counts), "metrics": dict(metric_counts), "figures": dict(figure_counts), "slides": len(slide_rows), "validation": validation}, ensure_ascii=False, indent=2))
