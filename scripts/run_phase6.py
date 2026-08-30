"""Run Phase 6: decision-oriented peak-aware forecasting for battery peak shaving.

Phase 6 is deliberately lightweight. It keeps the Phase 4.5 causal feature set,
24-hour horizon, time boundaries, fixed LightGBM complexity and Phase 5 Medium
battery. Two ideas from the project review are tested:

1. a yesterday / same-hour-last-week blended baseline; and
2. peak-aware LightGBM training that upweights high-load labels.

All blend/model candidate choices are frozen on leakage-corrected Validation
using realized battery peak as the primary criterion. Test is evaluated only
after ``selected_config.json`` has been written.
"""

from __future__ import annotations

import json
import os
import platform
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
from lightgbm import LGBMRegressor

from scripts.run_phase4 import BUILDING, EXPECTED_RAW_SHA256, load_building, sha256
from src.features.load_features import ALL_FEATURES, build_phase4_features
from src.forecast_artifacts import load_canonical_test_forecast
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import (
    PEAK_QUANTILE,
    PEAK_SAMPLE_MULTIPLIERS,
    WEEKLY_BLEND_WEIGHTS,
    battery_config_dict,
    day_week_blend,
    forecast_metrics,
    load_medium_battery,
    peak_sample_weights,
    run_dispatch,
    select_validation_candidate,
    summarize_dispatch,
    worst_fraction_mean,
)


RANDOM_SEED = 42
VALIDATION_START = pd.Timestamp("2017-11-01 00:00:00")
TEST_START = pd.Timestamp("2017-12-01 00:00:00")
TEST_TARGET_START = pd.Timestamp("2017-12-02 00:00:00")
TEST_TARGET_END = pd.Timestamp("2017-12-31 23:00:00")


def fit_fixed_model(
    frame: pd.DataFrame,
    features: list[str],
    parameters: dict[str, object],
    sample_weight: np.ndarray | None = None,
) -> LGBMRegressor:
    model = LGBMRegressor(**parameters)
    model.fit(frame[features], frame["target"], sample_weight=sample_weight)
    return model


def predict_nonnegative(model: LGBMRegressor, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.maximum(model.predict(frame[features]), 0.0)


def candidate_row(
    parameter_name: str,
    parameter_value: float,
    timestamps: pd.Series,
    actual: np.ndarray,
    prediction: np.ndarray,
    battery,
    method: str,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fmetrics = forecast_metrics(actual, prediction, timestamps)
    dispatch, daily, audit = run_dispatch(timestamps, actual, prediction, method, battery)
    dmetrics = summarize_dispatch(daily, dispatch)
    row: dict[str, object] = {
        parameter_name: float(parameter_value),
        **{f"validation_{key}": value for key, value in fmetrics.items()},
        **{f"validation_{key}": value for key, value in dmetrics.items()},
        "days": int(daily["date"].nunique()),
    }
    return row, dispatch, daily, audit


def no_battery_daily(timestamps: pd.Series, actual: np.ndarray) -> pd.DataFrame:
    frame = pd.DataFrame({"timestamp": pd.to_datetime(timestamps), "actual": actual})
    frame["date"] = frame["timestamp"].dt.normalize()
    rows = []
    for date, part in frame.groupby("date", sort=True):
        peak = float(part["actual"].max())
        rows.append(
            {
                "date": date.date().isoformat(),
                "method": "No Battery",
                "original_peak": peak,
                "realized_peak": peak,
                "peak_reduction": 0.0,
                "peak_reduction_pct": 0.0,
                "total_charge": 0.0,
                "total_discharge": 0.0,
                "throughput": 0.0,
                "forecast_peak": np.nan,
                "solver_success": True,
            }
        )
    return pd.DataFrame(rows)


def add_regret_and_summary(
    daily: pd.DataFrame,
    dispatch_by_method: dict[str, pd.DataFrame],
    actual: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    oracle = daily.loc[daily["method"].eq("Oracle"), ["date", "realized_peak"]].rename(
        columns={"realized_peak": "oracle_realized_peak"}
    )
    daily = daily.merge(oracle, on="date", how="left", validate="many_to_one")
    daily["decision_regret"] = daily["realized_peak"] - daily["oracle_realized_peak"]

    no_battery_mean = float(daily.loc[daily["method"].eq("No Battery"), "realized_peak"].mean())
    oracle_mean = float(daily.loc[daily["method"].eq("Oracle"), "realized_peak"].mean())
    original_overall_peak = float(np.max(actual))
    rows: list[dict[str, object]] = []
    for method, part in daily.groupby("method", sort=False):
        if method == "No Battery":
            max_peak = original_overall_peak
            throughput = 0.0
        else:
            dispatch = dispatch_by_method[method]
            max_peak = float(dispatch["realized_grid_load"].max())
            throughput = float(part["throughput"].sum())
        mean_peak = float(part["realized_peak"].mean())
        available_gain = no_battery_mean - oracle_mean
        capture = (no_battery_mean - mean_peak) / available_gain if abs(available_gain) > 1e-12 else np.nan
        rows.append(
            {
                "method": method,
                "post_dispatch_peak": max_peak,
                "absolute_peak_reduction": original_overall_peak - max_peak,
                "peak_reduction_percentage": 100.0 * (original_overall_peak - max_peak) / original_overall_peak,
                "mean_daily_peak": mean_peak,
                "worst_10pct_day_metric": worst_fraction_mean(part["realized_peak"].to_numpy(float), 0.10),
                "mean_regret": float(part["decision_regret"].mean()),
                "p90_regret": float(np.quantile(part["decision_regret"], 0.90)),
                "max_regret": float(part["decision_regret"].max()),
                "mean_peak_reduction": float(part["peak_reduction"].mean()),
                "oracle_capture_ratio": float(capture),
                "throughput": throughput,
            }
        )
    return daily, pd.DataFrame(rows)


def make_figures(
    output_dir: Path,
    blend_candidates: pd.DataFrame,
    peak_candidates: pd.DataFrame,
    daily: pd.DataFrame,
    dispatch_by_method: dict[str, pd.DataFrame],
    selected_peak_method: str,
    selected_blend_method: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(
        blend_candidates["weekly_weight"],
        blend_candidates["validation_mean_daily_peak"],
        marker="o",
        label="Day-week blend",
    )
    ax.set(
        title="Validation decision value of day-week blend",
        xlabel="Weekly weight (0=yesterday, 1=last week)",
        ylabel="Mean realized daily peak (kW)",
    )
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "01_validation_day_week_blend.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(
        peak_candidates["peak_multiplier"],
        peak_candidates["validation_mean_daily_peak"],
        marker="o",
        label="Peak-aware LightGBM",
    )
    ax.set(
        title="Validation decision value of peak-aware training",
        xlabel="High-load sample multiplier",
        ylabel="Mean realized daily peak (kW)",
    )
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "02_validation_peak_weighting.png", dpi=160)
    plt.close(fig)

    methods = ["Canonical LightGBM", selected_peak_method, selected_blend_method, "Persistence", "Oracle"]
    shown = daily.loc[daily["method"].isin(methods)].copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    for method, part in shown.groupby("method", sort=False):
        ax.plot(pd.to_datetime(part["date"]), part["realized_peak"], marker="o", markersize=3, label=method)
    ax.set(title="Test daily realized peaks", xlabel="Date", ylabel="Realized daily peak (kW)")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "03_test_daily_realized_peaks.png", dpi=160)
    plt.close(fig)

    canonical = daily.loc[daily["method"].eq("Canonical LightGBM"), ["date", "realized_peak"]].set_index("date")
    primary = daily.loc[daily["method"].eq(selected_peak_method), ["date", "realized_peak"]].set_index("date")
    difference = canonical["realized_peak"] - primary["realized_peak"]
    case_date = str(difference.abs().idxmax())
    cdispatch = dispatch_by_method["Canonical LightGBM"]
    pdispatch = dispatch_by_method[selected_peak_method]
    cday = cdispatch.loc[cdispatch["date"].eq(case_date)]
    pday = pdispatch.loc[pdispatch["date"].eq(case_date)]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(pd.to_datetime(cday["timestamp"]), cday["actual_load"], label="Actual", linewidth=1.8)
    ax.plot(pd.to_datetime(cday["timestamp"]), cday["forecast_load"], label="Canonical forecast", linewidth=1.2)
    ax.plot(pd.to_datetime(pday["timestamp"]), pday["forecast_load"], label="Phase 6 forecast", linewidth=1.2)
    ax.plot(pd.to_datetime(cday["timestamp"]), cday["realized_grid_load"], label="Canonical grid", linewidth=1.2)
    ax.plot(pd.to_datetime(pday["timestamp"]), pday["realized_grid_load"], label="Phase 6 grid", linewidth=1.2)
    ax.set(title=f"Representative Test day: {case_date}", xlabel="Hour", ylabel="Load / grid power (kW)")
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "04_representative_day.png", dpi=160)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame, digits: int = 4) -> str:
    """Render a compact Markdown table without optional tabulate dependency."""
    shown = frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.{digits}f}")
        else:
            shown[column] = shown[column].map(lambda value: "" if pd.isna(value) else str(value))
    headers = [str(column) for column in shown.columns]
    rows = [headers, ["---"] * len(headers)]
    rows.extend(shown.astype(str).values.tolist())
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def build_report(
    output_dir: Path,
    report_path: Path,
    selected: dict[str, object],
    blend_candidates: pd.DataFrame,
    peak_candidates: pd.DataFrame,
    forecast_table: pd.DataFrame,
    decision_table: pd.DataFrame,
    reproduction: dict[str, float],
) -> None:
    weekly_weight = float(selected["day_week_blend"]["weekly_weight"])
    multiplier = float(selected["peak_aware_lightgbm"]["peak_multiplier"])
    peak_method = str(selected["test_method_names"]["peak_aware"])
    blend_method = str(selected["test_method_names"]["day_week_blend"])

    decision = decision_table.set_index("method")
    canonical_peak = float(decision.loc["Canonical LightGBM", "mean_daily_peak"])
    primary_peak = float(decision.loc[peak_method, "mean_daily_peak"])
    primary_delta = primary_peak - canonical_peak
    canonical_regret = float(decision.loc["Canonical LightGBM", "mean_regret"])
    primary_regret = float(decision.loc[peak_method, "mean_regret"])
    blend_peak = float(decision.loc[blend_method, "mean_daily_peak"])
    persistence_peak = float(decision.loc["Persistence", "mean_daily_peak"])
    last_week_peak = float(decision.loc["Last-week", "mean_daily_peak"])

    if primary_delta < -1e-9:
        primary_conclusion = (
            f"预先在 Validation 上冻结的峰值感知模型在 Test 将平均日峰值相对 canonical LightGBM "
            f"降低 {-primary_delta:.4f} kW，同时 mean regret 由 {canonical_regret:.4f} kW 降至 {primary_regret:.4f} kW。"
        )
    elif primary_delta > 1e-9:
        primary_conclusion = (
            f"预先在 Validation 上冻结的峰值感知模型在 Test 未能优于 canonical LightGBM，平均日峰值反而增加 "
            f"{primary_delta:.4f} kW；因此不能声称峰值加权带来 out-of-sample 改善。"
        )
    else:
        primary_conclusion = "峰值感知模型与 canonical LightGBM 的 Test 平均日峰值相同，未观察到可量化改善。"

    if weekly_weight > 0.5:
        weekly_interpretation = "Validation 选择了偏向上周同小时的组合，支持‘周规律值得更高权重’这一项目假设。"
    elif weekly_weight < 0.5:
        weekly_interpretation = "Validation 选择没有偏向上周同小时，因此当前窗口不支持预先假设的‘周权重应更高’。"
    else:
        weekly_interpretation = "Validation 选择了日、周等权组合，没有证据支持某一侧应占更高权重。"

    lines = [
        "# Phase 6 — 面向储能削峰决策的峰值感知负荷预测优化",
        "",
        "## 1. 为什么做 Phase 6",
        "",
        "前期复盘已经确认两个事实：第一，建筑负荷存在明显日/周规律，昨日 persistence 不应是唯一朴素参照；第二，全天 MAE 更低并不是储能削峰更好的必要条件，峰值附近的时序与排序更关键。Phase 5.7 又表明，单纯增加鲁棒优化复杂度并不会自动改善 Test。因此 Phase 6 不继续堆叠复杂控制器，而是把优化重点前移到‘对削峰决策真正有价值的预测’。",
        "",
        "## 2. 研究问题",
        "",
        "1. 昨日同小时与上周同小时的 Validation 决策价值如何组合，周规律是否应获得更高权重？",
        "2. 对训练集中高负荷样本加权，并直接按 Validation 储能 realized peak 选择权重，能否提高 Test 的削峰决策价值？",
        "",
        "## 3. 固定协议与防泄漏",
        "",
        "- 建筑仍为 `Hog_office_Rolando`，预测任务仍为 feature time `t` 预测 `t+24h`。",
        "- 完全沿用 Phase 4.5 的 31 个因果特征、LightGBM 参数和固定树数；不增加深度学习。",
        "- Train 选择期标签严格 purge 到 Validation feature start 之前；Validation 选择只使用 target `< 2017-12-01 00:00:00` 的 696 小时，即 29 个完整自然日。",
        "- 峰值阈值只由 purge 后 Train target 的 P75 计算并冻结。",
        "- Medium battery 的容量、功率、效率、SOC 与 daily reset 完全复用 Phase 5。",
        "- `selected_config.json` 在任何 canonical Test forecast loader 调用之前写出；Test 不参与 blend 权重或 peak multiplier 选择。",
        "- Test 不是 pristine blind set，因为历史 Phase 3–5.7 Test 结果已经存在；Phase 6 不利用这些历史 Test 数值调参。",
        "",
        "## 4. 日—周组合 baseline",
        "",
        "定义 `prediction = (1-w) * yesterday + w * last_week`，候选 `w = {0, 0.25, 0.5, 0.75, 1}`。选择标准不是 MAE，而是先最小化 Validation mean daily realized peak，再依次比较 worst-10% daily peak、MAE 和较小 w。",
        "",
        markdown_table(blend_candidates),
        "",
        f"最终冻结 `weekly_weight={weekly_weight:.2f}`。{weekly_interpretation}",
        "",
        "## 5. 峰值感知 LightGBM",
        "",
        f"以 purge 后 Train target 的 P{int(PEAK_QUANTILE*100)} 作为高负荷阈值。普通样本权重为 1，高负荷样本候选权重为 `{list(PEAK_SAMPLE_MULTIPLIERS)}`。模型结构、特征和树数均不变，因此改变的只是训练目标对高负荷样本的重视程度。候选仍按 Validation 下游储能 realized peak 选择。",
        "",
        markdown_table(peak_candidates),
        "",
        f"最终冻结 `peak_multiplier={multiplier:.2f}`。",
        "",
        "## 6. Test 预测结果",
        "",
        markdown_table(forecast_table),
        "",
        "这里同时保留 MAE/RMSE 与 peak-quartile MAE、daily peak-hour error、Top-3 hour overlap，避免再次把单一 MAE 当作控制价值的代理。",
        "",
        "## 7. Test 储能决策结果",
        "",
        markdown_table(decision_table),
        "",
        primary_conclusion,
        "",
        f"冻结的日—周组合 Test mean daily peak 为 {blend_peak:.4f} kW；Yesterday Persistence 为 {persistence_peak:.4f} kW；Last-week 为 {last_week_peak:.4f} kW。这些 Test 结果只用于最终评价，不用于反调 weekly weight。",
        "",
        "## 8. Canonical reproduction",
        "",
        f"Phase 6 用完全相同的 Phase 4.5 final-fit 协议重新训练未加权模型，与 canonical Test prediction 的最大绝对差为 `{reproduction['canonical_test_prediction_max_abs_delta']:.3e}` kW。该检查用于确认 Phase 6 的唯一实验变量确实是样本加权/选择规则，而不是偷偷改变模型结构或数据切分。",
        "",
        "## 9. 创新点如何表述",
        "",
        "本项目可以把 Phase 6 表述为一个**面向下游储能决策价值的轻量级预测优化**：不是追求更复杂模型，而是用峰值样本加权改变预测关注区域，并直接用无泄漏 Validation 的储能 realized peak 作为模型选择指标；同时把日—周组合 baseline 纳入公平对照。这个做法可作为本科竞赛项目中的方法设计亮点，但不应声称它是学术上首次提出的全新算法。",
        "",
        "## 10. 与 Phase 5.7 的关系",
        "",
        "Phase 5.7 的负面结果不是废实验：它说明‘给优化器增加风险项’不足以解决问题。Phase 6 因而针对误差来源本身，尝试让预测更重视峰值决策窗口。两阶段共同支持一个更成熟的结论：复杂度不是目标，真正目标是 out-of-sample decision value。",
        "",
        "## 11. 限制",
        "",
        "结果仍只覆盖单建筑、单个 30 日 Test、固定 Medium battery 与 daily SOC reset。Validation 只有 29 个可用于严格选择的完整日；高负荷 P75 和候选 multiplier 都是轻量方案，并未证明跨建筑、跨季节普适。没有扩展到全 BDG2 建筑，是为了控制本科竞赛工程量并保持完整可解释的实验链。",
        "",
        "## 12. Competition-report-safe conclusion",
        "",
        primary_conclusion,
        "无论结果正负，都只能描述为冻结协议下本建筑、本时间窗的实证结果；不得把 Oracle 描述为可部署方案，也不得根据 Test 结果继续反调权重。",
        "",
        "## 13. 输出",
        "",
        "- `validation_day_week_candidates.csv`：日—周组合 Validation 候选",
        "- `validation_peak_weight_candidates.csv`：峰值权重 Validation 候选",
        "- `selected_config.json`：Test 前冻结的选择记录",
        "- `test_forecast_metrics.csv`：Test 预测与峰值时序指标",
        "- `test_decision_metrics.csv`：Test 储能决策指标",
        "- `test_daily_metrics.csv` / `dispatch_*.csv` / `constraint_audit.csv`：逐日、逐小时与约束证据",
        "- `figures/`：Validation 选择曲线与 Test 案例图",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    root = Path(project_root)
    output_dir = root / "outputs" / "phase6"
    figure_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    raw_path = root / "data" / "raw" / "electricity_cleaned.csv"
    phase45_config_path = root / "outputs" / "phase4_5" / "final_config.json"
    if not raw_path.is_file() or not phase45_config_path.is_file():
        raise FileNotFoundError("Phase 6 requires raw electricity data and Phase 4.5 final_config.json")
    if sha256(raw_path) != EXPECTED_RAW_SHA256:
        raise ValueError("Raw electricity CSV hash does not match the frozen project dataset")

    phase45_config = json.loads(phase45_config_path.read_text(encoding="utf-8"))
    if phase45_config["building"] != BUILDING or phase45_config["forecast_horizon_hours"] != 24:
        raise AssertionError("Phase 4.5 canonical task changed")
    features = list(phase45_config["feature_list"])
    if features != list(ALL_FEATURES):
        raise AssertionError("Phase 6 must keep the Phase 4.5 full causal feature set")
    parameters = dict(phase45_config["model_parameters"])
    selected_iteration = int(parameters["n_estimators"])

    load = load_building(raw_path)
    supervised = build_phase4_features(load)
    splits = split_by_feature_time(supervised)
    train_for_selection = purge_unavailable_targets(splits["train"], VALIDATION_START)
    validation_for_selection = purge_unavailable_targets(splits["validation"], TEST_START)
    if len(validation_for_selection) != 696:
        raise AssertionError("Strict Phase 6 Validation selection must contain 696 rows / 29 days")
    if validation_for_selection["target_timestamp"].max() >= TEST_START:
        raise AssertionError("Validation selection labels cross Test forecast start")
    if validation_for_selection.groupby(validation_for_selection["target_timestamp"].dt.normalize()).size().ne(24).any():
        raise AssertionError("Validation selection must contain complete natural days")

    battery = load_medium_battery(root)
    validation_timestamps = validation_for_selection["target_timestamp"].reset_index(drop=True)
    validation_actual = validation_for_selection["target"].to_numpy(float)

    blend_rows: list[dict[str, object]] = []
    for weekly_weight in WEEKLY_BLEND_WEIGHTS:
        prediction = day_week_blend(validation_for_selection, weekly_weight)
        row, _, _, audit = candidate_row(
            "weekly_weight",
            weekly_weight,
            validation_timestamps,
            validation_actual,
            prediction,
            battery,
            method=f"blend_w_{weekly_weight:.2f}",
        )
        if not audit["solver_success"].all() or audit[["soc_violations", "power_violations", "simultaneous_charge_discharge_violations"]].to_numpy().sum() != 0:
            raise AssertionError("Validation blend battery constraint audit failed")
        blend_rows.append(row)
    blend_candidates = pd.DataFrame(blend_rows)
    selected_blend = select_validation_candidate(blend_candidates, "weekly_weight")
    blend_candidates["selected"] = np.isclose(
        blend_candidates["weekly_weight"].astype(float), float(selected_blend["weekly_weight"]), atol=0.0, rtol=0.0
    )
    blend_candidates.to_csv(output_dir / "validation_day_week_candidates.csv", index=False)

    peak_threshold = float(np.quantile(train_for_selection["target"].to_numpy(float), PEAK_QUANTILE))
    peak_rows: list[dict[str, object]] = []
    for multiplier in PEAK_SAMPLE_MULTIPLIERS:
        weights = peak_sample_weights(train_for_selection["target"].to_numpy(float), peak_threshold, multiplier)
        model = fit_fixed_model(train_for_selection, features, parameters, weights)
        prediction = predict_nonnegative(model, validation_for_selection, features)
        row, _, _, audit = candidate_row(
            "peak_multiplier",
            multiplier,
            validation_timestamps,
            validation_actual,
            prediction,
            battery,
            method=f"peak_multiplier_{multiplier:.2f}",
        )
        row["train_peak_threshold"] = peak_threshold
        row["high_load_train_fraction"] = float(np.mean(train_for_selection["target"].to_numpy(float) >= peak_threshold))
        if not audit["solver_success"].all() or audit[["soc_violations", "power_violations", "simultaneous_charge_discharge_violations"]].to_numpy().sum() != 0:
            raise AssertionError("Validation peak-aware battery constraint audit failed")
        peak_rows.append(row)
    peak_candidates = pd.DataFrame(peak_rows)
    selected_peak = select_validation_candidate(peak_candidates, "peak_multiplier")
    peak_candidates["selected"] = np.isclose(
        peak_candidates["peak_multiplier"].astype(float), float(selected_peak["peak_multiplier"]), atol=0.0, rtol=0.0
    )
    peak_candidates.to_csv(output_dir / "validation_peak_weight_candidates.csv", index=False)

    selected_peak_method = f"Peak-aware LightGBM (m={float(selected_peak['peak_multiplier']):g})"
    selected_blend_method = f"Day-week blend (w_week={float(selected_blend['weekly_weight']):g})"
    selected_config = {
        "phase": "Phase 6",
        "building": BUILDING,
        "research_goal": "Decision-oriented peak-aware forecasting for deterministic battery peak shaving",
        "random_seed": RANDOM_SEED,
        "selection_protocol": {
            "train_target_cutoff_exclusive": str(VALIDATION_START),
            "validation_target_cutoff_exclusive": str(TEST_START),
            "validation_rows": int(len(validation_for_selection)),
            "validation_complete_days": int(validation_for_selection["target_timestamp"].dt.normalize().nunique()),
            "primary_selection_metric": "Validation mean daily realized peak under frozen Phase 5 Medium battery",
            "tie_breakers": ["worst-10% daily realized peak", "forecast MAE", "smaller candidate parameter"],
            "test_used_for_selection": False,
            "selected_before_canonical_test_loader": True,
            "historical_test_already_visible_before_phase6": True,
        },
        "day_week_blend": {
            "formula": "(1-weekly_weight)*yesterday + weekly_weight*last_week",
            "candidate_weights": list(WEEKLY_BLEND_WEIGHTS),
            "weekly_weight": float(selected_blend["weekly_weight"]),
            "validation_mean_daily_peak": float(selected_blend["validation_mean_daily_peak"]),
        },
        "peak_aware_lightgbm": {
            "feature_list": features,
            "base_parameters": parameters,
            "selected_iteration": selected_iteration,
            "peak_quantile": PEAK_QUANTILE,
            "train_peak_threshold": peak_threshold,
            "candidate_multipliers": list(PEAK_SAMPLE_MULTIPLIERS),
            "peak_multiplier": float(selected_peak["peak_multiplier"]),
            "validation_mean_daily_peak": float(selected_peak["validation_mean_daily_peak"]),
        },
        "battery_config": battery_config_dict(battery),
        "test_method_names": {
            "peak_aware": selected_peak_method,
            "day_week_blend": selected_blend_method,
        },
        "test_accessed_during_selection": False,
    }
    (output_dir / "selected_config.json").write_text(
        json.dumps(selected_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    final_fit = pd.concat([splits["train"], validation_for_selection], ignore_index=True)
    if len(final_fit) != int(phase45_config["selection_protocol"]["final_refit_rows"]):
        raise AssertionError("Phase 6 final-fit rows must match Phase 4.5")

    selected_multiplier = float(selected_peak["peak_multiplier"])
    selected_weights = peak_sample_weights(final_fit["target"].to_numpy(float), peak_threshold, selected_multiplier)
    final_peak_model = fit_fixed_model(final_fit, features, parameters, selected_weights)
    phase6_test_prediction = predict_nonnegative(final_peak_model, splits["test"], features)

    canonical_reproduction_model = fit_fixed_model(final_fit, features, parameters, None)
    reproduced_canonical_prediction = predict_nonnegative(canonical_reproduction_model, splits["test"], features)

    canonical_test, canonical_lineage = load_canonical_test_forecast(root)
    test_timestamps = canonical_test["timestamp"].reset_index(drop=True)
    test_actual = canonical_test["actual"].to_numpy(float)
    canonical_prediction = canonical_test["prediction"].to_numpy(float)
    if test_timestamps.min() != TEST_TARGET_START or test_timestamps.max() != TEST_TARGET_END:
        raise AssertionError("Canonical Test target period changed")
    if not np.allclose(splits["test"]["target"].to_numpy(float), test_actual, atol=1e-10, rtol=0.0):
        raise AssertionError("Raw Test target and canonical actual do not align")
    canonical_delta = float(np.max(np.abs(reproduced_canonical_prediction - canonical_prediction)))
    if canonical_delta > 1e-6:
        raise AssertionError(f"Phase 4.5 canonical reproduction failed: {canonical_delta}")

    persistence_prediction = day_week_blend(splits["test"], 0.0)
    last_week_prediction = day_week_blend(splits["test"], 1.0)
    frozen_blend_prediction = day_week_blend(splits["test"], float(selected_blend["weekly_weight"]))

    forecast_by_method: dict[str, np.ndarray] = {
        "Persistence": persistence_prediction,
        "Last-week": last_week_prediction,
        selected_blend_method: frozen_blend_prediction,
        "Canonical LightGBM": canonical_prediction,
        selected_peak_method: phase6_test_prediction,
        "Oracle": test_actual,
    }

    forecast_rows = []
    for method, prediction in forecast_by_method.items():
        forecast_rows.append(
            {
                "method": method,
                **forecast_metrics(test_actual, prediction, test_timestamps),
            }
        )
    forecast_table = pd.DataFrame(forecast_rows)
    forecast_table.to_csv(output_dir / "test_forecast_metrics.csv", index=False)

    dispatch_by_method: dict[str, pd.DataFrame] = {}
    daily_parts = [no_battery_daily(test_timestamps, test_actual)]
    audit_parts = []
    safe_names = {
        "Persistence": "persistence",
        "Last-week": "last_week",
        selected_blend_method: "day_week_blend",
        "Canonical LightGBM": "canonical_lightgbm",
        selected_peak_method: "peak_aware_lightgbm",
        "Oracle": "oracle",
    }
    for method, prediction in forecast_by_method.items():
        dispatch, daily_part, audit = run_dispatch(test_timestamps, test_actual, prediction, method, battery)
        dispatch_by_method[method] = dispatch
        daily_parts.append(daily_part)
        audit_parts.append(audit)
        dispatch.to_csv(
            output_dir / f"dispatch_{safe_names[method]}.csv",
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
        )

    daily = pd.concat(daily_parts, ignore_index=True)
    audit = pd.concat(audit_parts, ignore_index=True)
    daily, decision_table = add_regret_and_summary(daily, dispatch_by_method, test_actual)
    daily.to_csv(output_dir / "test_daily_metrics.csv", index=False)
    decision_table.to_csv(output_dir / "test_decision_metrics.csv", index=False)
    audit.to_csv(output_dir / "constraint_audit.csv", index=False)

    if not audit["solver_success"].all():
        raise AssertionError("At least one Phase 6 Test battery solve failed")
    for column in (
        "soc_violations",
        "power_violations",
        "simultaneous_charge_discharge_violations",
        "soc_transition_violations",
        "nan_or_inf_count",
    ):
        if int(audit[column].sum()) != 0:
            raise AssertionError(f"Battery constraint audit failed: {column}")
    if (audit["initial_soc_error"].abs() > 1e-6).any() or (audit["terminal_soc_error"].abs() > 1e-6).any():
        raise AssertionError("Initial/terminal SOC audit failed")

    make_figures(
        figure_dir,
        blend_candidates,
        peak_candidates,
        daily,
        dispatch_by_method,
        selected_peak_method,
        selected_blend_method,
    )

    reproduction = {
        "canonical_test_prediction_max_abs_delta": canonical_delta,
        "rows": int(len(canonical_test)),
    }
    (output_dir / "canonical_reproduction.json").write_text(
        json.dumps(reproduction, indent=2), encoding="utf-8"
    )

    build_report(
        output_dir,
        root / "reports" / "phase6_report.md",
        selected_config,
        blend_candidates,
        peak_candidates,
        forecast_table,
        decision_table,
        reproduction,
    )

    summary = {
        "selected_config": selected_config,
        "canonical_lineage": canonical_lineage,
        "canonical_reproduction": reproduction,
        "forecast_metrics": forecast_table.to_dict(orient="records"),
        "decision_metrics": decision_table.to_dict(orient="records"),
        "constraint_violation_totals": {
            column: int(audit[column].sum())
            for column in (
                "soc_violations",
                "power_violations",
                "simultaneous_charge_discharge_violations",
                "soc_transition_violations",
                "nan_or_inf_count",
            )
        },
        "zero_test_leakage": bool(
            selected_config["selection_protocol"]["test_used_for_selection"] is False
            and selected_config["selection_protocol"]["selected_before_canonical_test_loader"] is True
        ),
        "runtime_seconds": time.perf_counter() - started,
        "versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "selected_weekly_weight": float(selected_blend["weekly_weight"]),
                "selected_peak_multiplier": selected_multiplier,
                "canonical_reproduction_max_delta": canonical_delta,
                "test_decision_metrics": decision_table.to_dict(orient="records"),
                "runtime_seconds": summary["runtime_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return summary


if __name__ == "__main__":
    run()
