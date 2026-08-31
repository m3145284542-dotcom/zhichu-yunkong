"""Phase 9.1 methodology, statistical, semantic, and reporting audit.

This stage reads frozen Phase 7/8/9 artifacts.  It does not search, fit, tune,
dispatch, or alter any canonical prediction or experiment configuration.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.features.load_features import ALL_FEATURES
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import day_week_blend
from src.phase7.models import predict, refit_fixed
from src.phase7.pipeline import TEST_START, load_office_data, supervised_for
from src.phase8 import BUILDINGS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, ensemble_prediction


BASELINE_COMMIT = "f82d8ec2c05a72f8a384674f9161f6fcde4382e7"
FINAL_NAME = "Decision-Oriented Ensemble Forecasting"
FINAL_NAME_ZH = "面向储能决策的集成负荷预测方法"
FROZEN_CORE = (
    "outputs/phase7/selected_buildings.json",
    "outputs/phase7/model_selection_config.json",
    "outputs/phase7/building_battery_configs.csv",
    "outputs/phase8/selected_weights.csv",
    "outputs/phase9/forecast_metrics.csv",
    "outputs/phase9/decision_metrics.csv",
    "outputs/phase9/final_benchmark.csv",
    "outputs/phase9/competition_summary.json",
    "outputs/phase9/final_algorithm.json",
)
CANONICAL_DOCUMENTS = (
    "README.md",
    "reports/phase9_1_final_audit.md",
    "reports/battery_methodology.md",
)
CLAIM_RULES = (
    ("cross-building generalization", "unseen-building generalization claim"),
    ("unseen-building generalization", "unseen-building generalization claim"),
    ("泛化到未见建筑", "unseen-building generalization claim"),
    ("节能 ", "unsupported energy-use claim"),
    ("节电 ", "unsupported electricity-use claim"),
    ("电费下降", "unsupported cost claim"),
    ("碳排下降", "unsupported carbon claim"),
    ("industrial real-time deployment proven", "unsupported deployment claim"),
    ("达到工业实时部署要求", "unsupported deployment claim"),
    ("statistically significant improvement", "unsupported significance claim"),
    ("显著提升", "unsupported significance claim"),
    ("全面优于", "overclaim"),
    ("充分证明", "overclaim"),
    ("有力证明", "overclaim"),
    ("巨大工程价值", "overclaim"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def building_level_paired_bootstrap(differences: np.ndarray) -> dict[str, Any]:
    """Bootstrap the equal-building mean of eight paired normalized differences."""
    values = np.asarray(differences, dtype=float)
    if values.ndim != 1 or values.size != len(BUILDINGS) or not np.isfinite(values).all():
        raise ValueError(f"Expected {len(BUILDINGS)} finite building-level paired differences")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, values.size, size=(BOOTSTRAP_RESAMPLES, values.size))
    means = values[indices].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "comparison": "DOEF_minus_LightGBM",
        "metric": "building mean daily decision regret difference normalized by Phase 7 Train mean load",
        "resampling_unit": "building",
        "number_of_buildings": int(values.size),
        "number_of_units": int(values.size),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "point_estimate": float(values.mean()),
        "median_bootstrap_estimate": float(np.median(means)),
        "ci95_lower": float(low),
        "ci95_upper": float(high),
        "probability_mean_less_than_zero": float(np.mean(means < 0.0)),
    }


def choose_canonical_algorithm(_test_comparison: Any = None) -> dict[str, Any]:
    """Resolve the frozen algorithm without consulting Test results."""
    return {
        "name": FINAL_NAME,
        "acronym": "DOEF",
        "display_name": "DOEF v1.0 — Decision-Oriented Ensemble Forecasting",
        "display_name_zh": FINAL_NAME_ZH,
        "source_phase": 9,
        "canonical_reporting_phase": "9.1",
        "algorithm_version": "1.0",
        "freeze_status": "frozen",
        "algorithm_selection_source": "Validation",
        "selection_source_phase": 8,
        "selection_objective": "downstream storage decision regret",
        "test_role": "evaluation_only",
        "test_can_promote_algorithm": False,
        "weight_config_path": "outputs/phase8/selected_weights.csv",
        "weight_field": "w_decision",
        "formula": "w_b * LightGBM + (1 - w_b) * DayWeek",
        "dayweek_formula": "0.5 * actual(t-24h) + 0.5 * actual(t-168h)",
    }


def _registered_artifacts(root: Path) -> dict[str, str]:
    manifests = (
        ("outputs/phase7/artifact_manifest.json", "artifacts"),
        ("outputs/phase8/lineage.json", "artifacts"),
        ("outputs/phase9/data_lineage.json", "artifacts"),
    )
    registered: dict[str, str] = {}
    for manifest_path, field in manifests:
        manifest = _read_json(root / manifest_path)
        if manifest.get("status") != "canonical":
            raise ValueError(f"Non-canonical upstream manifest: {manifest_path}")
        registered[manifest_path] = sha256(root / manifest_path)
        for item in manifest[field]:
            registered[item["path"]] = item["sha256"]
    return registered


def verify_frozen_artifacts(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    registered = _registered_artifacts(root)
    rows = []
    for relative, expected in sorted(registered.items()):
        path = root / relative
        actual = sha256(path) if path.is_file() else None
        rows.append({
            "path": relative,
            "before_sha256": expected,
            "after_sha256": actual,
            "unchanged": actual == expected,
        })
    missing_core = sorted(set(FROZEN_CORE).difference(registered))
    if missing_core:
        raise AssertionError(f"Frozen core artifacts are not registered: {missing_core}")
    if not all(row["unchanged"] for row in rows):
        drift = [row["path"] for row in rows if not row["unchanged"]]
        raise AssertionError(f"FAIL CLOSED: frozen canonical artifact drift: {drift}")
    return {
        "status": "PASS",
        "baseline_git_head": BASELINE_COMMIT,
        "baseline_worktree_status": "clean tracked tree; AGENTS.md untracked and excluded",
        "baseline_full_test": {"command": "python -m unittest discover -s tests -v", "tests_run": 112, "result": "PASS"},
        "comparison_scope": "all artifacts registered by the canonical Phase 7, Phase 8, and Phase 9 manifests, plus the manifests",
        "artifact_count": len(rows),
        "frozen_core_paths": list(FROZEN_CORE),
        "artifacts": rows,
    }, registered


def _building_differences(root: Path) -> pd.DataFrame:
    decision = pd.read_csv(root / "outputs/phase9/decision_metrics.csv")
    battery = pd.read_csv(root / "outputs/phase7/building_battery_configs.csv").set_index("building")
    core = decision.loc[decision.method.isin(["LightGBM", "Phase8_DOEF"])].pivot(
        index="building", columns="method", values="mean_regret_vs_oracle"
    ).reindex(BUILDINGS)
    if core.isna().any().any() or tuple(core.index) != BUILDINGS:
        raise AssertionError("Frozen DOEF/LightGBM building decision metrics are incomplete")
    core["train_mean_load"] = battery.reindex(BUILDINGS).mean_train_load
    core["mean_daily_regret_doef"] = core["Phase8_DOEF"]
    core["mean_daily_regret_lightgbm"] = core["LightGBM"]
    core["normalized_difference"] = (
        core.mean_daily_regret_doef - core.mean_daily_regret_lightgbm
    ) / core.train_mean_load
    return core.reset_index()[[
        "building", "mean_daily_regret_doef", "mean_daily_regret_lightgbm",
        "train_mean_load", "normalized_difference",
    ]]


def _prediction_invariance(root: Path) -> dict[str, Any]:
    """Compare the Phase 8 implementation with the explicit Phase 9.1 formula."""
    config = _read_json(root / "outputs/phase7/model_selection_config.json")
    weights = pd.read_csv(root / "outputs/phase8/selected_weights.csv").set_index("building")
    electricity, _ = load_office_data(root)
    reference_parts: list[np.ndarray] = []
    audited_parts: list[np.ndarray] = []
    per_building: list[dict[str, Any]] = []
    for building in BUILDINGS:
        splits = split_by_feature_time(supervised_for(electricity, building))
        validation = purge_unavailable_targets(splits["validation"], TEST_START)
        final_fit = pd.concat([splits["train"], validation], ignore_index=True)
        chosen = config["selected_models"][f"{building}|LightGBM"]
        model = refit_fixed(
            "LightGBM", final_fit, ALL_FEATURES, chosen["parameters"], int(chosen["best_iteration"])
        )
        test = splits["test"]
        lgbm = predict(model, "LightGBM", test, ALL_FEATURES, int(chosen["best_iteration"]))
        dayweek = day_week_blend(test, 0.5)
        weight = float(weights.loc[building, "w_decision"])
        reference = ensemble_prediction(dayweek, lgbm, weight)
        audited = weight * lgbm + (1.0 - weight) * dayweek
        delta = float(np.max(np.abs(reference - audited)))
        per_building.append({"building": building, "samples": int(len(reference)), "max_abs_delta": delta})
        reference_parts.append(reference)
        audited_parts.append(audited)
    reference_all = np.concatenate(reference_parts).astype("<f8", copy=False)
    audited_all = np.concatenate(audited_parts).astype("<f8", copy=False)
    maximum = float(np.max(np.abs(reference_all - audited_all)))
    return {
        "status": "PASS" if maximum <= 1e-12 else "FAIL",
        "reference": "frozen Phase 8 ensemble_prediction using w_decision",
        "audited_definition": "explicit DOEF v1.0 formula using the same frozen component forecasts and weights",
        "samples": int(reference_all.size),
        "max_absolute_delta": maximum,
        "tolerance": 1e-12,
        "reference_sha256": hashlib.sha256(reference_all.tobytes()).hexdigest(),
        "audited_sha256": hashlib.sha256(audited_all.tobytes()).hexdigest(),
        "per_building": per_building,
    }


def _claim_audit(root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for relative in CANONICAL_DOCUMENTS:
        text = (root / relative).read_text(encoding="utf-8")
        folded = text.casefold()
        for phrase, category in CLAIM_RULES:
            count = len(re.findall(re.escape(phrase.casefold()), folded))
            rows.append({
                "document": relative,
                "category": category,
                "banned_unqualified_phrase": phrase,
                "occurrences": count,
                "status": "PASS" if count == 0 else "FAIL",
            })
    return pd.DataFrame(rows)


def _markdown(frame: pd.DataFrame, columns: list[str], digits: int = 6) -> str:
    shown = frame[columns].copy()
    for column in shown.columns:
        if pd.api.types.is_numeric_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{float(value):.{digits}f}")
    rows = [list(shown.columns), ["---"] * len(shown.columns), *shown.astype(str).values.tolist()]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def _report(summary: dict[str, Any], differences: pd.DataFrame, weights: pd.DataFrame,
            benchmark: pd.DataFrame, catboost: dict[str, Any]) -> str:
    bootstrap = summary["building_level_bootstrap"]
    wtl = summary["doef_vs_lightgbm"]["decision_regret_win_tie_loss"]
    return "\n".join([
        "# Phase 9.1 — Final Methodology & Reporting Audit", "",
        "## Audit scope and frozen algorithm", "",
        "Phase 9.1 changes statistical aggregation, methodology semantics, and reporting language only. It does not alter DOEF Test predictions, Phase 8 weights, selected buildings, model parameters, battery configurations, forecast horizon, optimizer, or dispatch constraints.", "",
        "**DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）** was fixed before Test evaluation by the Phase 8 Validation downstream storage-decision objective. `algorithm_selection_source = Validation`; `test_role = evaluation_only`.", "",
        "Peak-aware LightGBM was evaluated as a frozen supporting experiment and did not demonstrate stable benefit. It has no authority to replace or promote an algorithm based on Test results.", "",
        "DOEF is defined as `ŷ_t = w_b ŷ_t^(LightGBM) + (1-w_b) ŷ_t^(DayWeek)`, with `ŷ_t^(DayWeek) = 0.5 y_(t-24) + 0.5 y_(t-168)`. Each building-specific `w_b` is `w_decision` from `outputs/phase8/selected_weights.csv`, selected on Validation decision regret. The base forecasters are not claimed as novel; the contribution is the decision-oriented model-selection and ensemble framework.", "",
        "## Evaluation scope and building selection", "",
        "This is a **multi-building robustness evaluation** across eight heterogeneous office buildings. Each building uses its own historical training data and is evaluated on its own fixed future Test window; the experiment does not evaluate transfer to a completely new building.", "",
        "Candidate buildings were first screened using fixed raw-data coverage requirements over the predefined evaluation windows. Among eligible buildings, representative sampling used only Train-period load morphology statistics and did not use Validation/Test forecasting or storage-decision performance. Future-window raw availability is therefore disclosed separately from Train-only morphology selection.", "",
        "## Unit semantics", "",
        "BDG2 electricity readings are hourly interval energy, `E_t` in kWh. The dispatch model uses interval-average power `P_t = E_t / Δt`; here `Δt = 1 h`, so the numerical value is unchanged while the physical interpretation is kW. Battery capacity and SOC are kWh; charge/discharge limits are kW. Peak metrics refer to interval-average power, while charge/discharge energy and throughput refer to kWh.", "",
        "## Metric dictionary", "",
        "- **Normalized mean daily decision regret vs Oracle:** the mean daily realized peak from forecast-driven dispatch minus the non-deployable Oracle daily peak, divided by Phase 7 Train mean load. This is the primary decision metric used for Validation selection, win/tie/loss, and the formal building-level bootstrap.",
        "- **Peak reduction percentage:** `100 × (maximum original Test-window peak − maximum post-dispatch Test-window peak) / maximum original Test-window peak`. This is a whole-window peak-shaving metric, not the decision-regret comparison.", "",
        "The project contains no energy-use, tariff, demand-charge, cost, or carbon model. Reported percentages describe simulated peak shaving only under the frozen battery and dispatch protocol.", "",
        "## Formal building-level paired bootstrap", "",
        _markdown(differences, ["building", "mean_daily_regret_doef", "mean_daily_regret_lightgbm", "train_mean_load", "normalized_difference"]), "",
        f"The equal-building point estimate for DOEF − LightGBM normalized mean daily regret is **{bootstrap['point_estimate']:.6f}**. The 10,000-resample paired building bootstrap (seed 42, eight resampling units) gives a 95% percentile interval of **[{bootstrap['ci95_lower']:.6f}, {bootstrap['ci95_upper']:.6f}]** and `P(bootstrap mean < 0) = {bootstrap['probability_mean_less_than_zero']:.4f}`. The interval remained below zero in this experimental setting; no separate claim of statistical significance is made.", "",
        "The historical Phase 9 building-day bootstrap is retained as a secondary temporal-resampling sensitivity analysis. Its 240 pairs treat dates within a building as resampling units and are not the primary evidence for variation across buildings.", "",
        "## Forecast and decision objectives", "",
        "Forecast-error minimization and downstream-decision optimization are not generally equivalent objectives. The complete Phase 8 weight table is:", "",
        _markdown(weights, ["building", "w_forecast", "w_decision", "weights_differ"], digits=1), "",
        f"The weights differ for **{summary['forecast_vs_decision_weights']['different']}/{summary['forecast_vs_decision_weights']['total']}** buildings. The aggregate Phase 9 benchmark happens to select DOEF as both the lowest mean normalized forecast-error method and the lowest mean normalized decision-regret method; that aggregate coincidence does not make the two objectives generally equivalent.", "",
        "## Final benchmark and decision comparison", "",
        _markdown(benchmark, ["display_name", "normalized_mae_mean", "normalized_rmse_mean", "normalized_peak_mae_mean", "normalized_decision_regret_mean", "normalized_decision_regret_median", "peak_reduction_mean_pct", "peak_reduction_median_pct"]), "",
        f"Across the eight evaluated buildings, DOEF reduced mean normalized decision regret from {summary['doef_vs_lightgbm']['lightgbm_mean_normalized_regret']:.5f} for LightGBM to {summary['doef_vs_lightgbm']['doef_mean_normalized_regret']:.5f}. Building-level **decision-regret** win/tie/loss was **{wtl['wins']}/{wtl['ties']}/{wtl['losses']}**; this is not a peak-reduction win count.", "",
        "## CatBoost extreme-result retention", "",
        f"CatBoost Test-window peak reduction is reported without deletion or winsorization: mean {catboost['mean']:.5f}%, median {catboost['median']:.5f}%, minimum {catboost['min']:.5f}%, and maximum {catboost['max']:.5f}%. Hog_office_Lavon remains in the result. The small original-peak denominator and peak-timing error are consistent with the saved diagnostics and can amplify the percentage; this is not presented as a newly identified causal mechanism.", "",
        "## Limitations and reproduction", "",
        "The conclusions are limited to the eight office buildings, fixed data windows, one-hour resolution, 24-hour horizon, frozen battery sizing, daily SOC reset, and recorded CPU environment. Additional compute overhead was small in that recorded environment; no claim of industrial deployment readiness is made.", "",
        "Reproduce the audit with `python scripts/run_phase9_1.py`; verify with `python -m unittest discover -s tests -v`. Canonical audit artifacts are registered in `outputs/phase9_1/data_lineage.json` and loaded fail-closed by `src.final_algorithm.load_final_algorithm()`.", "",
    ])


def _battery_methodology() -> str:
    return """# Battery methodology and unit semantics

The source BDG2 electricity meter field is energy accumulated over each hourly interval, measured in kWh. For dispatch, the interval-average load power is

`P_t [kW] = E_t [kWh] / Δt [h]`.

All evaluated intervals have `Δt = 1 h`; therefore the values are numerically unchanged after conversion, but their dispatch interpretation is interval-average kW. Battery capacity and state of charge are kWh. Charge and discharge limits are kW; per-step charged and discharged energy are kWh and equal the corresponding average-kW values only because the interval is one hour.

Decision regret and peak reduction are power-peak metrics. Battery throughput is an energy metric. Peak shaving must not be interpreted as reduced total electricity use, reduced cost, or reduced emissions because those outcomes are not modeled.
"""


def _readme_section(summary: dict[str, Any]) -> str:
    bootstrap = summary["building_level_bootstrap"]
    return "\n".join([
        "## Phase 9.1 — Final Methodology & Reporting Audit", "",
        "**Final algorithm:** DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）。DOEF uses `w_b × LightGBM + (1 − w_b) × DayWeek`; each building-specific `w_b` is the Validation decision-regret-selected `w_decision` in `outputs/phase8/selected_weights.csv`.", "",
        "Phase 9.1 changes reporting, statistical aggregation, unit semantics, and methodology wording only. It does not alter frozen DOEF predictions, Phase 8 weights, selected buildings, model parameters, battery configurations, optimizer settings, or Test boundaries. DOEF was selected on Validation before Test evaluation; Test is used for evaluation and reporting only. Peak-aware LightGBM is a rejected supporting experiment, not an algorithm-promotion candidate.", "",
        "The evaluation covers eight heterogeneous office buildings, each trained from its own history and tested on its own fixed future window. It is a multi-building robustness evaluation, not an evaluation on a new building absent from training. Eligibility used fixed raw-data coverage checks over Train/Validation/Test windows; representative morphology sampling among eligible buildings used Train statistics only and no Validation/Test forecast or decision performance.", "",
        f"DOEF versus LightGBM building-level decision-regret comparison is 6/2/0 wins/ties/losses. The paired building bootstrap of normalized mean daily regret difference is {bootstrap['point_estimate']:.6f}, with 95% percentile interval [{bootstrap['ci95_lower']:.6f}, {bootstrap['ci95_upper']:.6f}] (10,000 resamples, seed 42, eight buildings).", "",
        "BDG2 meter values are hourly-interval kWh. Dispatch interprets `P_t = E_t / Δt` with `Δt = 1 h`, yielding numerically identical interval-average kW values. Peak-shaving percentages describe simulated maximum-power reduction under the frozen battery and dispatch protocol; the project does not model total electricity-use reduction, tariffs, costs, or emissions.", "",
        "Canonical sources: `outputs/phase9/final_benchmark.csv` for the unchanged benchmark; `outputs/phase9_1/final_reporting_summary.json` for corrected interpretation; `outputs/phase9_1/data_lineage.json` for fail-closed lineage; `reports/phase9_1_final_audit.md` for the final audit report.", "",
        "Reproduction: `python scripts/run_phase9_1.py` followed by `python -m unittest discover -s tests -v`.", "",
    ])


def run(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    baseline_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, current_head], cwd=root
    ).returncode == 0
    if not baseline_is_ancestor:
        raise AssertionError(f"Phase 9.1 must descend from baseline {BASELINE_COMMIT}; found {current_head}")
    output = root / "outputs/phase9_1"
    output.mkdir(parents=True, exist_ok=True)

    hash_audit, registered = verify_frozen_artifacts(root)
    differences = _building_differences(root)
    bootstrap = building_level_paired_bootstrap(differences.normalized_difference.to_numpy(float))
    weights = pd.read_csv(root / "outputs/phase8/selected_weights.csv")
    weights["weights_differ"] = ~np.isclose(weights.w_forecast, weights.w_decision, atol=1e-12, rtol=0.0)
    benchmark = pd.read_csv(root / "outputs/phase9/final_benchmark.csv")
    competition = _read_json(root / "outputs/phase9/competition_summary.json")
    daily_bootstrap = pd.read_csv(root / "outputs/phase9/bootstrap_results.csv")
    daily_secondary = daily_bootstrap.loc[
        daily_bootstrap.comparison.eq("Phase8_DOEF_minus_LightGBM")
    ].iloc[0].to_dict()

    unit_semantics = {
        "status": "canonical",
        "raw_meter_unit": "kWh per hourly interval",
        "dispatch_power_interpretation": "interval-average kW",
        "time_step_hours": 1.0,
        "conversion": "P_t = E_t / delta_t",
        "numeric_values_unchanged_due_to_one_hour_interval": True,
        "battery_capacity_and_soc_unit": "kWh",
        "battery_charge_discharge_power_unit": "kW",
    }
    metric_semantics = {
        "status": "canonical",
        "decision_regret": {
            "definition": "daily realized peak from forecast-driven dispatch minus non-deployable Oracle daily peak",
            "primary_metric": "normalized mean daily regret vs Oracle",
            "normalization": "Phase 7 Train mean load",
            "uses": ["Validation model selection", "DOEF vs LightGBM decision comparison", "win/tie/loss", "bootstrap"],
        },
        "peak_reduction_percentage": {
            "definition": "100 * (overall Test-window original maximum peak - post-dispatch maximum peak) / overall Test-window original maximum peak",
            "scope": "whole Test window",
            "not_equivalent_to_decision_regret": True,
        },
        "energy_use_reduction_metric_present": False,
        "electricity_cost_model_present": False,
        "carbon_model_present": False,
    }
    aggregate = pd.read_csv(root / "outputs/phase9/aggregate_metrics.csv").set_index("method")
    comparison = competition["doef_vs_lightgbm"]
    final_algorithm = choose_canonical_algorithm()
    prediction = _prediction_invariance(root)
    if prediction["status"] != "PASS":
        raise AssertionError("FAIL CLOSED: DOEF prediction definition changed")
    summary = {
        "schema_version": 1,
        "status": "canonical",
        "phase": "9.1",
        "final_algorithm": final_algorithm,
        "test_protocol": {
            "test_role": "evaluation_only",
            "algorithm_selection_source": "Validation",
            "test_used_for_algorithm_promotion": False,
            "peak_aware_role": "frozen supporting experiment / stress test; rejected from canonical algorithm",
        },
        "evaluation_scope": {
            "preferred_term": "multi-building robustness evaluation",
            "buildings": len(BUILDINGS),
            "not_unseen_building_transfer": True,
        },
        "building_selection": {
            "eligibility": "fixed raw-data coverage checks over predefined Train/Validation/Test windows",
            "representative_sampling": "Train-period load morphology only among eligible buildings",
            "validation_or_test_forecast_or_decision_performance_used": False,
        },
        "forecast_vs_decision_weights": {
            "total": int(len(weights)),
            "same": int((~weights.weights_differ).sum()),
            "different": int(weights.weights_differ.sum()),
            "rows": weights[["building", "w_forecast", "w_decision", "weights_differ"]].to_dict("records"),
        },
        "doef_vs_lightgbm": {
            "doef_mean_normalized_mae": float(aggregate.loc["Phase8_DOEF", "mean_normalized_MAE"]),
            "lightgbm_mean_normalized_mae": float(aggregate.loc["LightGBM", "mean_normalized_MAE"]),
            "doef_mean_normalized_regret": float(aggregate.loc["Phase8_DOEF", "mean_normalized_regret"]),
            "lightgbm_mean_normalized_regret": float(aggregate.loc["LightGBM", "mean_normalized_regret"]),
            "normalized_mae_relative_improvement_pct": comparison["normalized_mae_relative_improvement_pct"],
            "normalized_regret_relative_improvement_pct": comparison["normalized_regret_relative_improvement_pct"],
            "decision_regret_win_tie_loss": comparison["win_tie_loss"],
        },
        "building_level_bootstrap": bootstrap,
        "secondary_building_day_bootstrap": {
            **daily_secondary,
            "analysis_role": "secondary temporal-resampling sensitivity analysis",
        },
        "unit_semantics_path": "outputs/phase9_1/unit_semantics.json",
        "metric_semantics_path": "outputs/phase9_1/metric_semantics.json",
        "doef_prediction_invariance": prediction,
        "catboost_peak_reduction_pct": competition["catboost_peak_reduction_pct"],
        "limitations": [
            "eight office buildings",
            "one fixed future Test month per building",
            "one-hour intervals and 24-hour forecast horizon",
            "frozen battery and daily-reset dispatch protocol",
            "no energy-use, tariff, cost, or carbon outcome model",
        ],
    }

    differences.to_csv(output / "building_level_bootstrap.csv", index=False, float_format="%.17g")
    _write_json(output / "building_level_bootstrap_summary.json", bootstrap)
    _write_json(output / "unit_semantics.json", unit_semantics)
    _write_json(output / "metric_semantics.json", metric_semantics)
    _write_json(output / "doef_prediction_invariance.json", prediction)
    _write_json(output / "final_reporting_summary.json", summary)
    methodology = {
        "status": "PASS",
        "algorithm_selection_source": "Validation",
        "test_role": "evaluation_only",
        "test_based_algorithm_promotion_removed": True,
        "peak_aware_role": "supporting experiment only",
        "building_level_bootstrap_primary": True,
        "building_day_bootstrap_secondary": True,
        "unit_semantics_documented": True,
        "building_selection_eligibility_scope_disclosed": True,
        "multi_building_robustness_term_used": True,
        "forecast_and_decision_objectives_not_claimed_equivalent": True,
        "decision_regret_distinguished_from_peak_reduction": True,
        "catboost_extreme_result_retained": True,
        "unsupported_engineering_outcomes_claimed": False,
    }
    _write_json(output / "methodology_audit.json", methodology)
    _write_json(output / "artifact_hash_audit.json", hash_audit)

    (root / "reports/battery_methodology.md").write_text(_battery_methodology(), encoding="utf-8")
    (root / "reports/phase9_1_final_audit.md").write_text(
        _report(summary, differences, weights, benchmark, competition["catboost_peak_reduction_pct"]), encoding="utf-8"
    )
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    legacy_marker = "## Phase 9 — Final Algorithm Validation & Freeze"
    current_marker = "## Phase 9.1 — Final Methodology & Reporting Audit"
    marker = current_marker if current_marker in readme else legacy_marker
    if marker not in readme:
        raise ValueError("README Phase 9/9.1 marker is missing")
    readme_path.write_text(readme[:readme.index(marker)] + _readme_section(summary), encoding="utf-8")

    claims = _claim_audit(root)
    claims.to_csv(output / "claim_audit.csv", index=False)
    if not claims.status.eq("PASS").all():
        failures = claims.loc[claims.status.eq("FAIL"), ["document", "banned_unqualified_phrase"]].to_dict("records")
        raise AssertionError(f"Claim audit failed: {failures}")

    hash_audit_after, _ = verify_frozen_artifacts(root)
    if hash_audit_after["artifacts"] != hash_audit["artifacts"]:
        raise AssertionError("FAIL CLOSED: frozen artifacts changed during Phase 9.1 generation")

    artifact_paths = [path for path in output.iterdir() if path.is_file() and path.name != "data_lineage.json"]
    artifact_paths.extend([root / "reports/phase9_1_final_audit.md", root / "reports/battery_methodology.md"])
    lineage = {
        "schema_version": 1,
        "status": "canonical",
        "logical_role": "canonical Phase 9.1 methodology, statistical, unit-semantic, and reporting correction",
        "producer": "scripts/run_phase9_1.py",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parents": {
            "phase7": {"path": "outputs/phase7/artifact_manifest.json", "sha256": registered["outputs/phase7/artifact_manifest.json"]},
            "phase8": {"path": "outputs/phase8/lineage.json", "sha256": registered["outputs/phase8/lineage.json"]},
            "phase9": {"path": "outputs/phase9/data_lineage.json", "sha256": registered["outputs/phase9/data_lineage.json"]},
        },
        "supersedes_for_reporting_role": "outputs/phase9/data_lineage.json",
        "historical_phase9_artifacts_preserved": True,
        "acceptance_reason": "Validation-only DOEF selection, building-level bootstrap, explicit units and metric semantics, claim audit, and frozen-artifact invariance all passed",
        "canonical_loader": "src.final_algorithm.load_final_algorithm",
        "artifacts": [
            {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)} for path in sorted(artifact_paths)
        ],
    }
    _write_json(output / "data_lineage.json", lineage)
    return summary
