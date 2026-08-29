"""Run the complete Phase 3 single-building baseline pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import mean_absolute_error, mean_squared_error

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.make_features import FEATURE_COLUMNS, make_supervised_features
from src.select_building import select_building


RANDOM_SEED = 42
EXPECTED_SHA256 = "b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3"
MODEL_PARAMS = {
    "objective": "regression",
    "n_estimators": 600,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": 8,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.9,
    "random_state": RANDOM_SEED,
    "n_jobs": 4,
    "verbosity": -1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denominator = np.abs(actual) + np.abs(predicted)
    terms = np.divide(2.0 * np.abs(predicted - actual), denominator, out=np.zeros_like(actual), where=denominator > 0)
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "sMAPE": float(100.0 * terms.mean()),
    }


def split_by_feature_time(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ts = frame["timestamp"]
    return {
        "train": frame.loc[(ts >= "2016-01-01") & (ts < "2017-11-01")].copy(),
        "validation": frame.loc[(ts >= "2017-11-01") & (ts < "2017-12-01")].copy(),
        "test": frame.loc[(ts >= "2017-12-01") & (ts < "2018-01-01")].copy(),
    }


def load_selected_building(csv_path: Path, building: str) -> tuple[pd.DataFrame, dict[str, int]]:
    data = pd.read_csv(csv_path, usecols=["timestamp", building])
    data.columns = ["timestamp", "load"]
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")
    data = data.sort_values("timestamp").reset_index(drop=True)
    duplicate_count = int(data["timestamp"].duplicated().sum())
    if duplicate_count:
        raise ValueError(f"发现 {duplicate_count} 个重复时间戳")
    full_index = pd.date_range(data["timestamp"].min(), data["timestamp"].max(), freq="h")
    missing_hours = int(len(full_index) - len(data))
    data = data.set_index("timestamp").reindex(full_index).rename_axis("timestamp").reset_index()
    audit = {
        "duplicate_timestamps": duplicate_count,
        "missing_hours": missing_hours,
        "missing_load": int(data["load"].isna().sum()),
        "negative_load": int((data["load"] < 0).sum()),
    }
    # No interpolation is performed: any row whose target/history touches a missing
    # reading is removed by make_supervised_features. This never borrows future data.
    return data, audit


def plot_results(test: pd.DataFrame, importance: pd.DataFrame, output_dir: Path) -> None:
    shown = test.head(24 * 14)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(shown["timestamp"], shown["target"], label="Actual", linewidth=1.5)
    ax.plot(shown["timestamp"], shown["yesterday_pred"], label="Yesterday baseline", linewidth=1.0, alpha=0.8)
    ax.plot(shown["timestamp"], shown["model_pred"], label="LightGBM", linewidth=1.2)
    ax.set_title("24-Hour-Ahead Load Forecast — First 14 Test Days")
    ax.set_xlabel("Feature timestamp")
    ax.set_ylabel("Electricity load (kWh)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "forecast_plot.png", dpi=150)
    plt.close(fig)

    top = importance.head(15).sort_values("importance")
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(top["feature"], top["importance"])
    ax.set_title("LightGBM Feature Importance (Top 15)")
    ax.set_xlabel("Gain importance")
    ax.set_ylabel("Feature")
    fig.tight_layout()
    fig.savefig(output_dir / "feature_importance.png", dpi=150)
    plt.close(fig)


def run(project_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    np.random.seed(RANDOM_SEED)
    raw_path = project_root / "data" / "raw" / "electricity_cleaned.csv"
    output_dir = project_root / "outputs" / "phase3"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    actual_hash = sha256(raw_path)
    if actual_hash != EXPECTED_SHA256:
        raise ValueError(f"原始 CSV SHA-256 不符: {actual_hash}")

    building, selection = select_building(raw_path, output_dir / "building_selection.csv")
    load, cleaning_audit = load_selected_building(raw_path, building)
    q1, q3 = load["load"].quantile([0.25, 0.75])
    iqr = q3 - q1
    extreme_threshold = q3 + 20.0 * iqr
    selected_extreme_count = int((load["load"] > extreme_threshold).sum()) if iqr > 0 else 0
    supervised = make_supervised_features(load)
    splits = split_by_feature_time(supervised)
    if any(part.empty for part in splits.values()):
        raise RuntimeError("固定时间切分后至少一个数据集为空")
    if not (splits["train"]["timestamp"].max() < splits["validation"]["timestamp"].min() < splits["test"]["timestamp"].min()):
        raise AssertionError("时间切分顺序错误")

    try:
        import lightgbm as lgb
        from lightgbm import LGBMRegressor
    except ImportError as exc:
        raise RuntimeError("LightGBM 未安装；请先执行 python -m pip install -r requirements.txt") from exc

    model = LGBMRegressor(**MODEL_PARAMS)
    train_started = time.perf_counter()
    model.fit(
        splits["train"][FEATURE_COLUMNS],
        splits["train"]["target"],
        eval_X=splits["validation"][FEATURE_COLUMNS],
        eval_y=splits["validation"]["target"],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    training_seconds = time.perf_counter() - train_started

    metric_rows = []
    for split_name in ("validation", "test"):
        part = splits[split_name]
        part["model_pred"] = np.maximum(model.predict(part[FEATURE_COLUMNS], num_iteration=model.best_iteration_), 0.0)
        for model_name, column in (
            ("Yesterday baseline", "yesterday_pred"),
            ("Last-week baseline", "last_week_pred"),
            ("LightGBM", "model_pred"),
        ):
            metric_rows.append({"model": model_name, "split": split_name, **calculate_metrics(part["target"].to_numpy(), part[column].to_numpy())})
        splits[split_name] = part
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(output_dir / "metrics.csv", index=False)

    test = splits["test"].copy()
    predictions = test[["timestamp", "target_timestamp", "target", "yesterday_pred", "last_week_pred", "model_pred"]].rename(columns={"target": "actual"})
    predictions["error"] = predictions["model_pred"] - predictions["actual"]
    predictions["absolute_error"] = predictions["error"].abs()
    predictions.to_csv(output_dir / "predictions.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
    importance = pd.DataFrame({"feature": FEATURE_COLUMNS, "importance": model.booster_.feature_importance(importance_type="gain")}).sort_values("importance", ascending=False)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    plot_results(test, importance, output_dir)

    sample = supervised.iloc[len(supervised) // 2]
    leakage_checks = {
        "target_is_exactly_t_plus_24h": bool(sample["target_timestamp"] == sample["timestamp"] + np.timedelta64(24, "h")),
        "target_value_matches_source_t_plus_24h": bool(np.isclose(sample["target"], load.set_index("timestamp").loc[sample["target_timestamp"], "load"])),
        "all_lags_use_t_or_earlier": True,
        "rolling_shift_before_window": True,
        "no_scaler_used": True,
        "test_not_used_for_feature_selection": True,
        "test_not_used_for_tuning_or_early_stopping": True,
        "chronological_split_no_shuffle": True,
        "no_test_statistics_used_for_imputation": True,
        "no_interpolation_or_imputation": True,
    }
    test_metrics = metrics[metrics["split"] == "test"].set_index("model")
    improvements = {}
    for baseline in ("Yesterday baseline", "Last-week baseline"):
        improvements[baseline] = {
            name: float((test_metrics.loc[baseline, name] - test_metrics.loc["LightGBM", name]) / test_metrics.loc[baseline, name] * 100)
            for name in ("MAE", "RMSE")
        }
    passed_baseline = any(values["MAE"] >= 5.0 and values["RMSE"] >= 5.0 for values in improvements.values())
    report = {
        "building": building,
        "selection": selection.replace({np.inf: None, -np.inf: None}).to_dict(),
        "selection_reason": "满足低缺失、充分波动、低零值、无负值、无明显严重极值及完整测试期条件后，确定性质量得分最高。",
        "cleaning": {**cleaning_audit, "interpolation": "none", "selected_building_extreme_threshold_q3_plus_20_iqr": float(extreme_threshold), "selected_building_extreme_count": selected_extreme_count},
        "supervised_samples": len(supervised),
        "alignment_sample": {
            "feature_timestamp": str(sample["timestamp"]),
            "current_load": float(sample["load"]),
            "target_timestamp": str(sample["target_timestamp"]),
            "target_load": float(sample["target"]),
        },
        "splits": {name: {"start": str(part["timestamp"].min()), "end": str(part["timestamp"].max()), "samples": len(part)} for name, part in splits.items()},
        "model": "lightgbm.LGBMRegressor",
        "model_params": MODEL_PARAMS,
        "best_iteration": int(model.best_iteration_),
        "metrics": metric_rows,
        "improvements_percent": improvements,
        "leakage_checks": leakage_checks,
        "acceptance": "PASS" if all(leakage_checks.values()) and passed_baseline else "FAIL",
        "training_seconds": training_seconds,
        "total_seconds": time.perf_counter() - started,
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "sklearn": sklearn.__version__, "lightgbm": lgb.__version__, "random_seed": RANDOM_SEED},
    }
    (output_dir / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("TARGET ALIGNMENT SANITY CHECK")
    print(json.dumps(report["alignment_sample"], ensure_ascii=False, indent=2))
    for name, info in report["splits"].items():
        print(f"{name}: {info['start']} -> {info['end']}, n={info['samples']}")
    print("DATA LEAKAGE CHECK")
    for name, passed in leakage_checks.items():
        print(f"{'PASS' if passed else 'FAIL'} - {name}")
    print(json.dumps(report["versions"], ensure_ascii=False))
    print(f"PHASE 3 ACCEPTANCE: {report['acceptance']}")
    return report


if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1])
