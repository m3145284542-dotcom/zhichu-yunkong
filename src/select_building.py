"""Memory-conscious deterministic selection of one load-bearing building column."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def profile_buildings(csv_path: Path, chunksize: int = 2048) -> pd.DataFrame:
    """Profile every building without converting the wide file to a long table."""
    header = pd.read_csv(csv_path, nrows=0).columns.tolist()
    if not header or header[0] != "timestamp":
        raise ValueError("electricity_cleaned.csv 的首列必须是 timestamp")
    buildings = header[1:]
    n = len(buildings)
    count = np.zeros(n, dtype=np.int64)
    missing = np.zeros(n, dtype=np.int64)
    total = np.zeros(n, dtype=np.float64)
    total_sq = np.zeros(n, dtype=np.float64)
    minimum = np.full(n, np.inf)
    maximum = np.full(n, -np.inf)
    zeros = np.zeros(n, dtype=np.int64)
    negatives = np.zeros(n, dtype=np.int64)
    split_counts = {name: np.zeros(n, dtype=np.int64) for name in ("train", "validation", "test")}
    row_count = 0

    for chunk in pd.read_csv(csv_path, chunksize=chunksize, low_memory=False):
        timestamps = pd.to_datetime(chunk.pop("timestamp"), errors="raise")
        values = chunk.to_numpy(dtype=np.float64, copy=False)
        valid = ~np.isnan(values)
        row_count += len(chunk)
        count += valid.sum(axis=0)
        missing += (~valid).sum(axis=0)
        safe = np.where(valid, values, 0.0)
        total += safe.sum(axis=0)
        total_sq += np.square(safe).sum(axis=0)
        minimum = np.minimum(minimum, np.where(valid, values, np.inf).min(axis=0))
        maximum = np.maximum(maximum, np.where(valid, values, -np.inf).max(axis=0))
        zeros += ((values == 0.0) & valid).sum(axis=0)
        negatives += ((values < 0.0) & valid).sum(axis=0)
        masks = {
            "train": timestamps < pd.Timestamp("2017-11-01"),
            "validation": (timestamps >= pd.Timestamp("2017-11-01")) & (timestamps < pd.Timestamp("2017-12-01")),
            "test": timestamps >= pd.Timestamp("2017-12-01"),
        }
        for name, mask in masks.items():
            split_counts[name] += valid[np.asarray(mask)].sum(axis=0)

    mean = np.divide(total, count, out=np.full(n, np.nan), where=count > 0)
    variance = np.divide(total_sq, count, out=np.full(n, np.nan), where=count > 0) - np.square(mean)
    std = np.sqrt(np.maximum(variance, 0.0))
    zero_ratio = np.divide(zeros, count, out=np.full(n, np.nan), where=count > 0)
    missing_rate = missing / row_count
    # A deliberately conservative global rule. It marks only maxima over 30 standard
    # deviations above the mean as an obvious severe extreme; flagged columns are not selected.
    obvious_extreme = (std > 0) & (maximum > mean + 30.0 * std)
    cv = np.divide(std, np.abs(mean), out=np.zeros(n), where=np.abs(mean) > 1e-12)
    eligible = (
        (missing_rate <= 0.01)
        & (std > 1e-6)
        & (zero_ratio <= 0.20)
        & (negatives == 0)
        & (~obvious_extreme)
        & (split_counts["test"] >= 24 * 30)
    )
    score = (
        60.0 * (1.0 - missing_rate)
        + 15.0 * np.minimum(cv, 2.0) / 2.0
        + 15.0 * (1.0 - np.nan_to_num(zero_ratio, nan=1.0))
        + 10.0 * np.minimum(split_counts["test"] / (24.0 * 31.0), 1.0)
    )
    score = np.where(eligible, score, -np.inf)
    if not np.isfinite(score).any():
        raise RuntimeError("没有建筑满足低缺失、非零、无负值、无严重极值及完整测试期的最低条件")
    selected_index = int(np.argmax(score))

    result = pd.DataFrame(
        {
            "building": buildings,
            "non_null_count": count,
            "missing_count": missing,
            "missing_rate": missing_rate,
            "mean": mean,
            "std": std,
            "min": np.where(np.isfinite(minimum), minimum, np.nan),
            "max": np.where(np.isfinite(maximum), maximum, np.nan),
            "zero_ratio": zero_ratio,
            "negative_count": negatives,
            "obvious_extreme": obvious_extreme,
            "train_non_null": split_counts["train"],
            "validation_non_null": split_counts["validation"],
            "test_non_null": split_counts["test"],
            "selection_score": score,
            "selected": np.arange(n) == selected_index,
        }
    )
    return result.sort_values(["selected", "selection_score", "building"], ascending=[False, False, True]).reset_index(drop=True)


def select_building(csv_path: Path, output_path: Path) -> tuple[str, pd.Series]:
    profile = profile_buildings(csv_path).rename(columns={"selection_score": "screening_score"})
    profile["selection_score"] = np.nan
    profile["train_daily_autocorrelation"] = np.nan
    profile["train_weekly_autocorrelation"] = np.nan
    profile["train_robust_extreme_rate"] = np.nan
    profile["train_cv"] = np.nan

    # Refine only a bounded candidate set, using training-period loads only. This
    # rejects low-base/spike-dominated series without loading all 1,578 columns again.
    preliminary = profile[
        (profile["missing_rate"] <= 0.01)
        & (profile["negative_count"] == 0)
        & (profile["zero_ratio"] <= 0.10)
        & (~profile["obvious_extreme"])
        & (profile["mean"] >= 5.0)
        & (profile["std"] / profile["mean"].abs()).between(0.15, 1.50)
        & (profile["test_non_null"] >= 24 * 30)
    ].sort_values(["missing_rate", "zero_ratio", "building"]).head(128)
    if preliminary.empty:
        raise RuntimeError("没有建筑通过训练期稳健质量初筛")
    names = preliminary["building"].tolist()
    candidate_data = pd.read_csv(csv_path, usecols=["timestamp", *names])
    timestamps = pd.to_datetime(candidate_data.pop("timestamp"), errors="raise")
    train = candidate_data.loc[timestamps < pd.Timestamp("2017-11-01")]
    for name in names:
        series = train[name]
        valid = series.dropna()
        if len(valid) < 24 * 365:
            continue
        mean = float(valid.mean())
        std = float(valid.std(ddof=0))
        cv = std / abs(mean) if abs(mean) > 1e-12 else np.inf
        q1, q3 = valid.quantile([0.25, 0.75])
        iqr = float(q3 - q1)
        extreme_rate = float((valid > q3 + 20.0 * iqr).mean()) if iqr > 0 else 1.0
        daily_corr = float(series.corr(series.shift(24)))
        weekly_corr = float(series.corr(series.shift(168)))
        row = profile["building"].eq(name)
        profile.loc[row, ["train_daily_autocorrelation", "train_weekly_autocorrelation", "train_robust_extreme_rate", "train_cv"]] = [daily_corr, weekly_corr, extreme_rate, cv]

    refined = profile[
        profile["train_cv"].between(0.15, 1.50)
        & (profile["train_robust_extreme_rate"] <= 0.005)
        & profile["train_daily_autocorrelation"].notna()
        & profile["train_weekly_autocorrelation"].notna()
    ].copy()
    if refined.empty:
        raise RuntimeError("没有建筑通过训练期稳健极值与自相关检查")
    refined["selection_score"] = (
        50.0 * (1.0 - refined["missing_rate"])
        + 10.0 * (1.0 - refined["zero_ratio"])
        + 25.0 * (refined["train_daily_autocorrelation"].clip(-1, 1) + 1.0) / 2.0
        + 15.0 * (refined["train_weekly_autocorrelation"].clip(-1, 1) + 1.0) / 2.0
        - 1000.0 * refined["train_robust_extreme_rate"]
    )
    chosen_name = str(refined.sort_values(["selection_score", "building"], ascending=[False, True]).iloc[0]["building"])
    profile["selected"] = profile["building"].eq(chosen_name)
    profile.loc[profile["building"].isin(refined["building"]), "selection_score"] = refined.set_index("building")["selection_score"].reindex(profile.loc[profile["building"].isin(refined["building"]), "building"]).to_numpy()
    profile.loc[profile["building"].isin(names) & (profile["train_robust_extreme_rate"] > 0.005), "obvious_extreme"] = True
    profile = profile.sort_values(["selected", "selection_score", "building"], ascending=[False, False, True]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile.to_csv(output_path, index=False)
    chosen = profile.loc[profile["selected"]].iloc[0]
    return str(chosen["building"]), chosen
