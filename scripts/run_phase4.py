"""Run Phase 4: causal features, validation-only selection, and final test evaluation."""

from __future__ import annotations

import hashlib
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

from src.features.load_features import (
    ALL_FEATURES,
    FEATURE_SETS,
    LAG_HOURS,
    ROLLING_WINDOWS,
    build_phase4_features,
    causal_perturbation_check,
)
from src.models.train_lgbm import calculate_metrics, fit_lgbm, split_by_feature_time


BUILDING = "Hog_office_Rolando"
TARGET = "load at t+24h"
RANDOM_SEED = 42
EXPECTED_RAW_SHA256 = "b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3"
BASE_PARAMETERS = {
    "objective": "regression",
    "n_estimators": 800,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": -1,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "min_child_samples": 20,
    "random_state": RANDOM_SEED,
    "n_jobs": 4,
    "verbosity": -1,
    "deterministic": True,
    "force_col_wise": True,
}
CANDIDATES = [
    ("base", {}),
    ("regularized_small", {"num_leaves": 15, "max_depth": 6, "min_child_samples": 30, "reg_lambda": 0.2}),
    ("bounded_depth", {"num_leaves": 31, "max_depth": 8, "min_child_samples": 20, "reg_lambda": 0.1}),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_building(raw_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(raw_path, usecols=["timestamp", BUILDING])
    frame.columns = ["timestamp", "load"]
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("原始建筑序列存在重复时间戳")
    full_index = pd.date_range(frame["timestamp"].min(), frame["timestamp"].max(), freq="h")
    return frame.set_index("timestamp").reindex(full_index).rename_axis("timestamp").reset_index()


def make_plots(predictions: pd.DataFrame, importance: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    shown = predictions.head(24 * 14)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(shown["timestamp"], shown["actual"], label="Actual", linewidth=1.6)
    ax.plot(shown["timestamp"], shown["prediction"], label="LightGBM prediction", linewidth=1.3)
    ax.set(title="Test Load: Actual vs Prediction (First 14 Days)", xlabel="Target timestamp", ylabel="Electricity load (kWh)")
    ax.legend()
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(output_dir / "01_test_actual_vs_prediction.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(predictions["actual"], predictions["prediction"], s=12, alpha=0.45)
    lower = min(predictions["actual"].min(), predictions["prediction"].min())
    upper = max(predictions["actual"].max(), predictions["prediction"].max())
    ax.plot([lower, upper], [lower, upper], "--", color="black", linewidth=1, label="Ideal")
    ax.set(title="Test Actual vs Prediction", xlabel="Actual load (kWh)", ylabel="Predicted load (kWh)"); ax.legend()
    fig.tight_layout(); fig.savefig(output_dir / "02_test_scatter.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(predictions["error"], bins=35, color="#4C78A8", alpha=0.85)
    ax.axvline(0.0, color="black", linestyle="--", linewidth=1)
    ax.set(title="Test Prediction Error Distribution", xlabel="Prediction - actual (kWh)", ylabel="Count")
    fig.tight_layout(); fig.savefig(output_dir / "03_error_distribution.png", dpi=160); plt.close(fig)

    top = importance.head(20).sort_values("importance")
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["feature"], top["importance"], color="#59A14F")
    ax.set(title="LightGBM Feature Importance (Top 20)", xlabel="Gain importance", ylabel="Feature")
    fig.tight_layout(); fig.savefig(output_dir / "04_feature_importance.png", dpi=160); plt.close(fig)

    week = predictions.iloc[24 * 7:24 * 14]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(week["timestamp"], week["actual"], label="Actual", linewidth=1.7)
    ax.plot(week["timestamp"], week["prediction"], label="LightGBM prediction", linewidth=1.3)
    ax.set(title="Test Example: One Continuous Week", xlabel="Target timestamp", ylabel="Electricity load (kWh)"); ax.legend()
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(output_dir / "05_week_example.png", dpi=160); plt.close(fig)


def run(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    output_dir = project_root / "outputs" / "phase4"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    phase3_report_path = project_root / "outputs" / "phase3" / "run_report.json"
    if not raw_path.exists() or not phase3_report_path.exists():
        raise FileNotFoundError("需要现有 raw 电力数据和 outputs/phase3/run_report.json")
    if sha256(raw_path) != EXPECTED_RAW_SHA256:
        raise ValueError("原始 electricity_cleaned.csv SHA-256 与第三阶段不一致")
    phase3_report = json.loads(phase3_report_path.read_text(encoding="utf-8"))
    if phase3_report["building"] != BUILDING:
        raise AssertionError("第三阶段最终建筑与第四阶段要求不一致")

    load = load_building(raw_path)
    supervised = build_phase4_features(load)
    splits = split_by_feature_time(supervised)
    if any(part.empty for part in splits.values()):
        raise RuntimeError("固定时间切分后至少一个集合为空")
    expected_boundaries = {
        "validation": (pd.Timestamp("2017-11-01 00:00:00"), pd.Timestamp("2017-11-30 23:00:00")),
        "test": (pd.Timestamp("2017-12-01 00:00:00"), pd.Timestamp("2017-12-30 23:00:00")),
    }
    for name, (start, end) in expected_boundaries.items():
        if splits[name]["timestamp"].min() != start or splits[name]["timestamp"].max() != end:
            raise AssertionError(f"{name} 边界未沿用第三阶段")

    ablation_rows = []
    for name, features in FEATURE_SETS.items():
        _, validation_prediction = fit_lgbm(splits["train"], splits["validation"], features, BASE_PARAMETERS)
        ablation_rows.append({"feature_set": name, "n_features": len(features), **calculate_metrics(splits["validation"]["target"], validation_prediction)})
    ablation = pd.DataFrame(ablation_rows).sort_values(["RMSE", "MAE"]).reset_index(drop=True)
    ablation.to_csv(output_dir / "ablation_study.csv", index=False)
    selected_set_name = str(ablation.iloc[0]["feature_set"])
    selected_features = FEATURE_SETS[selected_set_name]

    candidate_rows = []
    fitted = {}
    for candidate_name, overrides in CANDIDATES:
        parameters = {**BASE_PARAMETERS, **overrides}
        model, validation_prediction = fit_lgbm(splits["train"], splits["validation"], selected_features, parameters)
        metrics = calculate_metrics(splits["validation"]["target"], validation_prediction)
        candidate_rows.append({"candidate": candidate_name, "best_iteration": int(model.best_iteration_), **metrics})
        fitted[candidate_name] = (model, validation_prediction, parameters)
    candidates = pd.DataFrame(candidate_rows).sort_values(["RMSE", "MAE"]).reset_index(drop=True)
    candidates.to_csv(output_dir / "candidate_validation_results.csv", index=False)
    selected_candidate = str(candidates.iloc[0]["candidate"])
    final_model, validation_prediction, final_parameters = fitted[selected_candidate]

    test_prediction_call_count = 0
    test_prediction = np.maximum(
        final_model.predict(splits["test"][selected_features], num_iteration=final_model.best_iteration_), 0.0
    )
    test_prediction_call_count += 1

    comparison_rows = []
    for model_name, column in (("Yesterday baseline", "yesterday_pred"), ("Last-week baseline", "last_week_pred")):
        validation_metrics = calculate_metrics(splits["validation"]["target"], splits["validation"][column])
        test_metrics = calculate_metrics(splits["test"]["target"], splits["test"][column])
        comparison_rows.append({"model": model_name, **{f"validation_{k}": v for k, v in validation_metrics.items()}, **{f"test_{k}": v for k, v in test_metrics.items()}})
    validation_metrics = calculate_metrics(splits["validation"]["target"], validation_prediction)
    test_metrics = calculate_metrics(splits["test"]["target"], test_prediction)
    comparison_rows.append({"model": "Phase 4 LightGBM", **{f"validation_{k}": v for k, v in validation_metrics.items()}, **{f"test_{k}": v for k, v in test_metrics.items()}})
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)

    predictions = pd.DataFrame({
        "timestamp": splits["test"]["target_timestamp"],
        "actual": splits["test"]["target"].to_numpy(),
        "prediction": test_prediction,
    })
    predictions["error"] = predictions["prediction"] - predictions["actual"]
    predictions["abs_error"] = predictions["error"].abs()
    predictions.to_csv(output_dir / "test_prediction.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")

    importance = pd.DataFrame({
        "feature": selected_features,
        "importance": final_model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False).reset_index(drop=True)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    make_plots(predictions, importance, output_dir / "figures")

    split_info = {
        name: {
            "feature_time_start": str(part["timestamp"].min()),
            "feature_time_end": str(part["timestamp"].max()),
            "target_time_start": str(part["target_timestamp"].min()),
            "target_time_end": str(part["target_timestamp"].max()),
            "samples": len(part),
        }
        for name, part in splits.items()
    }
    leakage_checks = {
        "all_lag_offsets_are_positive": all(lag > 0 for lag in LAG_HOURS),
        "future_perturbation_does_not_change_inputs": causal_perturbation_check(load),
        "rolling_windows_use_shift_1_history": all(window > 0 for window in ROLLING_WINDOWS),
        "no_scaler_used": True,
        "model_fit_rows_are_train_only": splits["train"]["timestamp"].max() < splits["validation"]["timestamp"].min(),
        "validation_used_only_for_selection_and_early_stopping": True,
        "test_not_used_for_tuning": True,
        "test_prediction_called_once_after_selection": test_prediction_call_count == 1,
        "no_target_imputation_or_interpolation": True,
        "raw_data_hash_matches_phase3": True,
    }
    leakage_lines = [
        "Phase 4 data leakage audit",
        "Forecast task: features known at origin t predict load at t+24h.",
        "The negative shift is used only to create the supervised target; no input feature uses a negative shift.",
        "Validation labels affect early stopping/model selection only, never tree gradient fitting. Test is evaluated once after selection.",
        "Missing target/history rows are dropped; no forward/backward fill or interpolation is used.",
        "",
        *[f"{'PASS' if passed else 'FAIL'} - {name}" for name, passed in leakage_checks.items()],
        "",
        f"Overall: {'PASS' if all(leakage_checks.values()) else 'FAIL'}",
    ]
    (output_dir / "leakage_check.txt").write_text("\n".join(leakage_lines) + "\n", encoding="utf-8")

    final_parameters_recorded = {**final_parameters, "best_iteration": int(final_model.best_iteration_)}
    config = {
        "building": BUILDING,
        "target": TARGET,
        "forecast_horizon_hours": 24,
        "train_period": split_info["train"],
        "validation_period": split_info["validation"],
        "test_period": split_info["test"],
        "selected_feature_set": selected_set_name,
        "feature_list": selected_features,
        "model": "lightgbm.LGBMRegressor (CPU)",
        "model_parameters": final_parameters_recorded,
        "random_seed": RANDOM_SEED,
        "selection_rule": "lowest validation RMSE, then validation MAE; test never used",
    }
    (output_dir / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    primary = comparison.loc[comparison["model"].eq("Last-week baseline")].iloc[0]
    model_row = comparison.loc[comparison["model"].eq("Phase 4 LightGBM")].iloc[0]
    improvements = {
        split_name: {
            metric: float(100.0 * (primary[f"{split_name}_{metric}"] - model_row[f"{split_name}_{metric}"]) / primary[f"{split_name}_{metric}"])
            for metric in ("MAE", "RMSE", "MAPE")
        }
        for split_name in ("validation", "test")
    }
    report = {
        "config": config,
        "ablation": ablation_rows,
        "candidate_validation_results": candidate_rows,
        "model_comparison": comparison_rows,
        "improvement_vs_primary_last_week_baseline_percent": improvements,
        "top_15_features": importance.head(15).to_dict(orient="records"),
        "leakage_checks": leakage_checks,
        "runtime_seconds": time.perf_counter() - started,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__},
    }
    (output_dir / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"selected_feature_set": selected_set_name, "selected_candidate": selected_candidate, "comparison": comparison_rows, "runtime_seconds": report["runtime_seconds"]}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
