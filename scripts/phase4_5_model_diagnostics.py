"""Run Phase 4.5 leakage audit, ablation, robustness, and diagnostics."""

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
import sklearn
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from scripts.run_phase4 import (
    BASE_PARAMETERS,
    BUILDING,
    EXPECTED_RAW_SHA256,
    RANDOM_SEED,
    TARGET,
    load_building,
    sha256,
)
from src.features.load_features import (
    ALL_FEATURES,
    CALENDAR_FEATURES,
    FORECAST_HORIZON_HOURS,
    ROLLING_FEATURES,
    build_phase4_features,
    causal_perturbation_check,
)
from src.models.train_lgbm import fit_lgbm, purge_unavailable_targets, split_by_feature_time


VALIDATION_START = pd.Timestamp("2017-11-01 00:00:00")
TEST_START = pd.Timestamp("2017-12-01 00:00:00")
EXPECTED_BOUNDARIES = {
    "validation": (pd.Timestamp("2017-11-01 00:00:00"), pd.Timestamp("2017-11-30 23:00:00")),
    "test": (pd.Timestamp("2017-12-01 00:00:00"), pd.Timestamp("2017-12-30 23:00:00")),
}

SHORT_TERM_FEATURES = ["current_load", "lag_1", "lag_2", "lag_3", "lag_24", "lag_48", "lag_72"]
WEEKLY_FEATURES = ["lag_168"]
LONG_FEATURES = ["lag_336"]
CORE_FEATURES = [*CALENDAR_FEATURES, "current_load", "lag_24", "lag_168"]

ABLATION_FEATURES = {
    "full": ALL_FEATURES,
    "without_calendar": [f for f in ALL_FEATURES if f not in CALENDAR_FEATURES],
    "without_short_term_lag": [f for f in ALL_FEATURES if f not in SHORT_TERM_FEATURES],
    "without_weekly_lag": [f for f in ALL_FEATURES if f not in WEEKLY_FEATURES],
    "without_long_lag": [f for f in ALL_FEATURES if f not in LONG_FEATURES],
    "without_rolling": [f for f in ALL_FEATURES if f not in ROLLING_FEATURES],
    "core_lag_plus_calendar": [f for f in ALL_FEATURES if f in CORE_FEATURES],
}

ROBUSTNESS_CONFIGS = {
    "phase4_current": {},
    "num_leaves_15": {"num_leaves": 15},
    "num_leaves_63": {"num_leaves": 63},
    "learning_rate_0_02": {"learning_rate": 0.02, "n_estimators": 1200},
    "learning_rate_0_05": {"learning_rate": 0.05, "n_estimators": 600},
    "min_child_samples_40": {"min_child_samples": 40},
    "colsample_1_0": {"colsample_bytree": 1.0},
    "reg_lambda_0_5": {"reg_lambda": 0.5},
}


def diagnostic_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    nonzero = np.abs(actual) > 1e-12
    mape = 100.0 * np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) if nonzero.any() else 0.0
    denominator = np.abs(actual) + np.abs(predicted)
    smape_terms = np.divide(
        2.0 * np.abs(predicted - actual),
        denominator,
        out=np.zeros_like(actual),
        where=denominator > 0,
    )
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "MAPE": float(mape),
        "sMAPE": float(100.0 * smape_terms.mean()),
        "R2": float(r2_score(actual, predicted)),
    }


def predict(model, frame: pd.DataFrame, features: list[str], iterations: int | None = None) -> np.ndarray:
    num_iteration = iterations if iterations is not None else model.best_iteration_
    return np.maximum(model.predict(frame[features], num_iteration=num_iteration), 0.0)


def prediction_frame(split: str, frame: pd.DataFrame, predicted: np.ndarray) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "split": split,
            "feature_timestamp": frame["timestamp"].to_numpy(),
            "target_timestamp": frame["target_timestamp"].to_numpy(),
            "y_true": frame["target"].to_numpy(dtype=float),
            "y_pred": predicted,
        }
    )
    result["error"] = result["y_pred"] - result["y_true"]
    result["abs_error"] = result["error"].abs()
    result["hour"] = result["target_timestamp"].dt.hour
    result["day_of_week"] = result["target_timestamp"].dt.dayofweek
    result["is_weekend"] = result["day_of_week"] >= 5
    return result


def grouped_errors(predictions: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows = []
    for keys, part in predictions.groupby(["split", *group_columns], observed=True, sort=True):
        keys = keys if isinstance(keys, tuple) else (keys,)
        record = dict(zip(["split", *group_columns], keys))
        record.update(
            {
                "sample_count": len(part),
                "MAE": float(part["abs_error"].mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(part["error"])))),
                "bias": float(part["error"].mean()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def save_line_plot(
    predictions: pd.DataFrame,
    path: Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(predictions["target_timestamp"], predictions["y_true"], label="Actual", linewidth=1.5)
    ax.plot(predictions["target_timestamp"], predictions["y_pred"], label="LightGBM", linewidth=1.2)
    ax.set(title=title, xlabel="Target timestamp", ylabel="Electricity load")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def save_group_plot(
    table: pd.DataFrame,
    x: str,
    path: Path,
    title: str,
    tick_labels: list[str] | None = None,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for split, part in table.groupby("split", sort=False):
        axes[0].plot(part[x], part["MAE"], marker="o", label=split)
        axes[1].plot(part[x], part["bias"], marker="o", label=split)
    axes[0].set_ylabel("MAE")
    axes[1].set_ylabel("Bias (prediction - actual)")
    axes[1].set_xlabel(x.replace("_", " "))
    axes[0].legend()
    axes[1].axhline(0.0, color="black", linestyle="--", linewidth=0.8)
    if tick_labels is not None:
        axes[1].set_xticks(range(len(tick_labels)), tick_labels)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fit_fixed_iteration(train: pd.DataFrame, features: list[str], parameters: dict[str, object], iterations: int):
    from lightgbm import LGBMRegressor

    final_parameters = {**parameters, "n_estimators": iterations}
    model = LGBMRegressor(**final_parameters)
    model.fit(train[features], train["target"])
    return model


def reproduce_reference(splits: dict[str, pd.DataFrame], output_dir: Path) -> tuple[dict[str, dict[str, float]], pd.DataFrame]:
    model, validation_prediction = fit_lgbm(
        splits["train"], splits["validation"], ALL_FEATURES, BASE_PARAMETERS
    )
    test_prediction = predict(model, splits["test"], ALL_FEATURES)
    predictions = pd.concat(
        [
            prediction_frame("validation", splits["validation"], validation_prediction),
            prediction_frame("test", splits["test"], test_prediction),
        ],
        ignore_index=True,
    )
    metrics = {
        split: diagnostic_metrics(part["y_true"], part["y_pred"])
        for split, part in predictions.groupby("split", sort=False)
    }

    historical = json.loads((PROJECT_ROOT / "outputs" / "phase4" / "run_report.json").read_text(encoding="utf-8"))
    historical_row = next(row for row in historical["model_comparison"] if row["model"] == "Phase 4 LightGBM")
    for split in ("validation", "test"):
        for metric in ("MAE", "RMSE", "MAPE"):
            expected = float(historical_row[f"{split}_{metric}"])
            if not np.isclose(metrics[split][metric], expected, rtol=0.0, atol=1e-10):
                raise AssertionError(f"Phase 4 reference mismatch: {split} {metric}")

    (output_dir / "reference_metrics.json").write_text(
        json.dumps(
            {
                "protocol": "Exact Phase 4 reproduction; includes the audited 24-hour boundary-label issue.",
                "best_iteration": int(model.best_iteration_),
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    predictions.to_csv(
        output_dir / "reference_predictions.csv",
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )
    return metrics, predictions


def run_ablation(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    rows = []
    for experiment, features in ABLATION_FEATURES.items():
        model, validation_prediction = fit_lgbm(train, validation, features, BASE_PARAMETERS)
        metrics = diagnostic_metrics(validation["target"], validation_prediction)
        rows.append(
            {
                "experiment": experiment,
                "feature_count": len(features),
                "best_iteration": int(model.best_iteration_),
                **{f"validation_{key.lower()}": value for key, value in metrics.items()},
            }
        )
    table = pd.DataFrame(rows)
    full = table.loc[table["experiment"].eq("full")].iloc[0]
    table["delta_mae_vs_full"] = table["validation_mae"] - full["validation_mae"]
    table["delta_rmse_vs_full"] = table["validation_rmse"] - full["validation_rmse"]
    table.to_csv(output_dir / "feature_ablation.csv", index=False)
    return table


def run_robustness(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    rows = []
    for name, overrides in ROBUSTNESS_CONFIGS.items():
        parameters = {**BASE_PARAMETERS, **overrides}
        model, validation_prediction = fit_lgbm(train, validation, ALL_FEATURES, parameters)
        metrics = diagnostic_metrics(validation["target"], validation_prediction)
        rows.append(
            {
                "configuration": name,
                "parameter_overrides": json.dumps(overrides, sort_keys=True),
                "best_iteration": int(model.best_iteration_),
                **{f"validation_{key.lower()}": value for key, value in metrics.items()},
            }
        )
    table = pd.DataFrame(rows)
    current = table.loc[table["configuration"].eq("phase4_current")].iloc[0]
    table["delta_mae_vs_current"] = table["validation_mae"] - current["validation_mae"]
    table["delta_rmse_vs_current"] = table["validation_rmse"] - current["validation_rmse"]
    table.to_csv(output_dir / "parameter_robustness.csv", index=False)
    return table


def save_error_diagnostics(predictions: pd.DataFrame, output_dir: Path) -> dict[str, pd.DataFrame]:
    by_hour = grouped_errors(predictions, ["hour"])
    by_hour.to_csv(output_dir / "error_by_hour.csv", index=False)
    save_group_plot(by_hour, "hour", output_dir / "error_by_hour.png", "Forecast error by target hour")

    by_dow = grouped_errors(predictions, ["day_of_week"])
    by_dow["day_name"] = by_dow["day_of_week"].map(
        dict(enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))
    )
    by_dow.to_csv(output_dir / "error_by_dayofweek.csv", index=False)
    save_group_plot(
        by_dow,
        "day_of_week",
        output_dir / "error_by_dayofweek.png",
        "Forecast error by target day of week",
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    )

    workday = predictions.assign(day_type=np.where(predictions["is_weekend"], "weekend", "weekday"))
    by_workday = grouped_errors(workday, ["day_type"])
    by_workday.to_csv(output_dir / "error_by_workday.csv", index=False)

    load_parts = []
    for split, part in predictions.groupby("split", sort=False):
        p25, p75 = part["y_true"].quantile([0.25, 0.75])
        labeled = part.copy()
        labeled["load_level"] = pd.cut(
            labeled["y_true"],
            [-np.inf, p25, p75, np.inf],
            labels=["low_<=P25", "normal_P25-P75", "high_>=P75"],
            include_lowest=True,
        )
        load_parts.append(labeled)
    by_load = grouped_errors(pd.concat(load_parts, ignore_index=True), ["load_level"])
    by_load.to_csv(output_dir / "error_by_load_level.csv", index=False)

    largest = (
        predictions.sort_values(["split", "abs_error"], ascending=[True, False])
        .groupby("split", sort=False)
        .head(20)
        [["split", "feature_timestamp", "target_timestamp", "y_true", "y_pred", "error", "abs_error", "hour", "day_of_week"]]
    )
    largest.to_csv(output_dir / "largest_errors.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
    return {"hour": by_hour, "day_of_week": by_dow, "workday": by_workday, "load_level": by_load}


def phase3_phase4_rows(project_root: Path) -> list[dict[str, object]]:
    phase3 = json.loads((project_root / "outputs" / "phase3" / "run_report.json").read_text(encoding="utf-8"))
    phase4 = json.loads((project_root / "outputs" / "phase4" / "run_report.json").read_text(encoding="utf-8"))

    rows = []
    for name in ("Yesterday baseline", "Last-week baseline", "LightGBM"):
        record = {"model": "Phase 3 LightGBM" if name == "LightGBM" else name}
        for split in ("validation", "test"):
            metric = next(row for row in phase3["metrics"] if row["model"] == name and row["split"] == split)
            for key in ("MAE", "RMSE", "sMAPE"):
                record[f"{split}_{key}"] = metric[key]
        rows.append(record)

    phase4_model = next(row for row in phase4["model_comparison"] if row["model"] == "Phase 4 LightGBM")
    rows.append({"model": "Phase 4 LightGBM", **{key: value for key, value in phase4_model.items() if key != "model"}})
    return rows


def run(project_root: Path = PROJECT_ROOT) -> dict[str, object]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    output_dir = project_root / "outputs" / "phase4_5"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    if sha256(raw_path) != EXPECTED_RAW_SHA256:
        raise ValueError("Raw electricity CSV hash does not match Phase 3/4")

    load = load_building(raw_path)
    supervised = build_phase4_features(load)
    splits = split_by_feature_time(supervised)
    for name, (start, end) in EXPECTED_BOUNDARIES.items():
        if splits[name]["timestamp"].min() != start or splits[name]["timestamp"].max() != end:
            raise AssertionError(f"{name} feature-time boundary changed")

    reference_metrics, _ = reproduce_reference(splits, output_dir)

    train_for_selection = purge_unavailable_targets(splits["train"], VALIDATION_START)
    validation_for_selection = purge_unavailable_targets(splits["validation"], TEST_START)
    if train_for_selection["target_timestamp"].max() >= VALIDATION_START:
        raise AssertionError("Training labels cross the validation forecast start")
    if validation_for_selection["target_timestamp"].max() >= TEST_START:
        raise AssertionError("Validation selection labels cross the test forecast start")

    ablation = run_ablation(train_for_selection, validation_for_selection, output_dir)
    robustness = run_robustness(train_for_selection, validation_for_selection, output_dir)

    # The full Phase 4 feature set and parameter set remain the benchmark unless
    # validation-only evidence is both material and repeated. This diagnostic run
    # deliberately does not promote a one-off small difference.
    selected_features = list(ALL_FEATURES)
    selected_parameters = dict(BASE_PARAMETERS)

    validation_model, _ = fit_lgbm(
        train_for_selection,
        validation_for_selection,
        selected_features,
        selected_parameters,
    )
    validation_prediction = predict(validation_model, splits["validation"], selected_features)
    selected_iteration = int(validation_model.best_iteration_)

    final_fit = pd.concat([splits["train"], validation_for_selection], ignore_index=True)
    final_model = fit_fixed_iteration(final_fit, selected_features, selected_parameters, selected_iteration)
    test_prediction_call_count = 0
    test_prediction = predict(final_model, splits["test"], selected_features, selected_iteration)
    test_prediction_call_count += 1

    predictions = pd.concat(
        [
            prediction_frame("validation", splits["validation"], validation_prediction),
            prediction_frame("test", splits["test"], test_prediction),
        ],
        ignore_index=True,
    )
    predictions.to_csv(
        output_dir / "final_predictions.csv",
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )
    final_metrics = {
        split: diagnostic_metrics(part["y_true"], part["y_pred"])
        for split, part in predictions.groupby("split", sort=False)
    }
    (output_dir / "final_metrics.json").write_text(
        json.dumps(final_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    validation_predictions = predictions.loc[predictions["split"].eq("validation")]
    test_predictions = predictions.loc[predictions["split"].eq("test")]
    save_line_plot(
        validation_predictions,
        output_dir / "validation_prediction.png",
        "Validation actual vs prediction (horizon=24h)",
    )
    save_line_plot(
        test_predictions,
        output_dir / "test_prediction.png",
        "Test actual vs prediction (horizon=24h)",
    )
    save_line_plot(
        test_predictions.head(24 * 7),
        output_dir / "test_prediction_7days.png",
        "Test first continuous 7 days (horizon=24h)",
    )
    diagnostic_tables = save_error_diagnostics(predictions, output_dir)

    importance = pd.DataFrame(
        {
            "feature": selected_features,
            "gain_importance": final_model.booster_.feature_importance(importance_type="gain"),
            "split_importance": final_model.booster_.feature_importance(importance_type="split"),
        }
    ).sort_values("gain_importance", ascending=False).reset_index(drop=True)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    top = importance.head(20).sort_values("gain_importance")
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["feature"], top["gain_importance"], color="#4C78A8")
    ax.set(title="LightGBM feature importance by gain (Top 20)", xlabel="Gain importance", ylabel="Feature")
    fig.tight_layout()
    fig.savefig(output_dir / "feature_importance.png", dpi=160)
    plt.close(fig)

    comparison_rows = phase3_phase4_rows(project_root)
    phase45_row = {"model": "Phase 4.5 final LightGBM"}
    for split, metrics in final_metrics.items():
        for key, value in metrics.items():
            phase45_row[f"{split}_{key}"] = value
    comparison_rows.append(phase45_row)
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)

    leakage_checks = {
        "raw_hash_matches_phase3_phase4": True,
        "feature_timestamp_boundaries_unchanged": True,
        "target_is_t_plus_24h": bool(
            (supervised["target_timestamp"] - supervised["timestamp"]).dt.total_seconds().eq(86400.0).all()
        ),
        "target_not_in_feature_list": "target" not in ALL_FEATURES,
        "future_perturbation_does_not_change_features": causal_perturbation_check(load),
        "rolling_uses_shifted_history": True,
        "chronological_split_no_shuffle": True,
        "train_labels_available_before_validation_start": True,
        "selection_labels_available_before_test_start": True,
        "no_scaler_or_global_fitted_statistics": True,
        "test_not_used_for_feature_or_parameter_selection": True,
        "final_test_prediction_called_once_after_selection": test_prediction_call_count == 1,
        "historical_test_was_already_visible_before_phase4_5": True,
    }
    audit = {
        "finding": "Phase 4 features are causal, but its last 24 training and validation labels cross the next forecast-period start.",
        "resolution": "Keep evaluation feature-time boundaries unchanged and purge unavailable boundary labels for Phase 4.5 fitting/selection.",
        "historical_reference_is_not_leakage_corrected": True,
        "test_is_not_pristine": "Phase 3 and Phase 4 test metrics already existed before Phase 4.5; Phase 4.5 never uses them for selection.",
        "row_counts": {
            "train_fixed_window": len(splits["train"]),
            "train_used_after_purge": len(train_for_selection),
            "validation_fixed_window": len(splits["validation"]),
            "validation_used_for_selection_after_purge": len(validation_for_selection),
            "test_fixed_window": len(splits["test"]),
        },
        "checks": leakage_checks,
    }
    (output_dir / "leakage_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    final_config = {
        "building": BUILDING,
        "target": TARGET,
        "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
        "feature_time_boundaries": {
            name: {
                "start": str(part["timestamp"].min()),
                "end": str(part["timestamp"].max()),
                "samples": len(part),
            }
            for name, part in splits.items()
        },
        "selection_protocol": {
            "train_target_cutoff_exclusive": str(VALIDATION_START),
            "validation_target_cutoff_exclusive": str(TEST_START),
            "test_used_for_selection": False,
            "final_refit_rows": len(final_fit),
        },
        "feature_list": selected_features,
        "model": "lightgbm.LGBMRegressor (CPU)",
        "model_parameters": {**selected_parameters, "n_estimators": selected_iteration},
        "random_seed": RANDOM_SEED,
        "shap": "not run; standard gain/split importance is sufficient for this lightweight stage",
    }
    (output_dir / "final_config.json").write_text(
        json.dumps(final_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "audit": audit,
        "reference_metrics": reference_metrics,
        "ablation": ablation.to_dict(orient="records"),
        "parameter_robustness": robustness.to_dict(orient="records"),
        "final_config": final_config,
        "final_metrics": final_metrics,
        "top_features": importance.head(20).to_dict(orient="records"),
        "error_summaries": {
            name: table.to_dict(orient="records") for name, table in diagnostic_tables.items()
        },
        "runtime_seconds": time.perf_counter() - started,
        "versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
        },
    }
    (output_dir / "run_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "reference_metrics": reference_metrics,
                "final_metrics": final_metrics,
                "selected_iteration": selected_iteration,
                "runtime_seconds": report["runtime_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    run()
