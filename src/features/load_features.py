"""Causal load features for the existing Phase 3 24-hour-ahead task."""

from __future__ import annotations

import numpy as np
import pandas as pd

FORECAST_HORIZON_HOURS = 24
LAG_HOURS = (1, 2, 3, 24, 48, 72, 168, 336)
ROLLING_WINDOWS = (3, 6, 24, 48, 168)

CALENDAR_FEATURES = [
    "hour", "day_of_week", "day_of_month", "month", "day_of_year",
    "week_of_year", "is_weekend", "hour_sin", "hour_cos", "dow_sin",
    "dow_cos", "month_sin", "month_cos",
]
LAG_FEATURES = [f"lag_{lag}" for lag in LAG_HOURS]
ROLLING_FEATURES = [
    "rolling_mean_3", "rolling_mean_6", "rolling_mean_24",
    "rolling_mean_48", "rolling_mean_168", "rolling_std_24",
    "rolling_std_168", "rolling_min_24", "rolling_max_24",
]
ALL_FEATURES = ["current_load", *CALENDAR_FEATURES, *LAG_FEATURES, *ROLLING_FEATURES]
FEATURE_SETS = {
    "A: Calendar only": CALENDAR_FEATURES,
    "B: Calendar + lag": ["current_load", *CALENDAR_FEATURES, *LAG_FEATURES],
    "C: Calendar + lag + rolling": ALL_FEATURES,
}


def build_phase4_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build features known at forecast origin t for the Phase 3 target t+24h."""
    data = frame[["timestamp", "load"]].copy().sort_values("timestamp").reset_index(drop=True)
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")
    if data["timestamp"].duplicated().any():
        raise ValueError("存在重复时间戳")
    if len(data) > 1 and not data["timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise ValueError("特征构造前必须补齐为连续小时索引")

    timestamp = data["timestamp"]
    load = data["load"].astype("float64")
    data["current_load"] = load
    data["hour"] = timestamp.dt.hour.astype("int8")
    data["day_of_week"] = timestamp.dt.dayofweek.astype("int8")
    data["day_of_month"] = timestamp.dt.day.astype("int8")
    data["month"] = timestamp.dt.month.astype("int8")
    data["day_of_year"] = timestamp.dt.dayofyear.astype("int16")
    data["week_of_year"] = timestamp.dt.isocalendar().week.astype("int8")
    data["is_weekend"] = (data["day_of_week"] >= 5).astype("int8")
    data["hour_sin"] = np.sin(2.0 * np.pi * data["hour"] / 24.0)
    data["hour_cos"] = np.cos(2.0 * np.pi * data["hour"] / 24.0)
    data["dow_sin"] = np.sin(2.0 * np.pi * data["day_of_week"] / 7.0)
    data["dow_cos"] = np.cos(2.0 * np.pi * data["day_of_week"] / 7.0)
    data["month_sin"] = np.sin(2.0 * np.pi * (data["month"] - 1) / 12.0)
    data["month_cos"] = np.cos(2.0 * np.pi * (data["month"] - 1) / 12.0)

    for lag in LAG_HOURS:
        data[f"lag_{lag}"] = load.shift(lag)

    history = load.shift(1)
    for window in ROLLING_WINDOWS:
        rolling = history.rolling(window=window, min_periods=window)
        data[f"rolling_mean_{window}"] = rolling.mean()
    for window in (24, 168):
        rolling = history.rolling(window=window, min_periods=window)
        data[f"rolling_std_{window}"] = rolling.std()
    rolling_24 = history.rolling(window=24, min_periods=24)
    data["rolling_min_24"] = rolling_24.min()
    data["rolling_max_24"] = rolling_24.max()

    data["target_timestamp"] = timestamp + pd.Timedelta(hours=FORECAST_HORIZON_HOURS)
    data["target"] = load.shift(-FORECAST_HORIZON_HOURS)
    data["yesterday_pred"] = load
    data["last_week_pred"] = load.shift(168 - FORECAST_HORIZON_HOURS)
    required = [*ALL_FEATURES, "target", "yesterday_pred", "last_week_pred"]
    result = data.dropna(subset=required).copy()
    if not np.isfinite(result[[*ALL_FEATURES, "target"]].to_numpy(dtype=float)).all():
        raise ValueError("监督学习数据包含 NaN 或 inf")
    return result.reset_index(drop=True)


def causal_perturbation_check(frame: pd.DataFrame) -> bool:
    """Verify future-load perturbations cannot change any input feature at t."""
    base = build_phase4_features(frame)
    if len(base) < 10:
        raise ValueError("因果扰动检查需要至少 10 个有效监督样本")
    row = base.iloc[len(base) // 2]
    changed = frame.copy()
    changed.loc[changed["timestamp"] > row["timestamp"], "load"] += 1_000_000.0
    perturbed = build_phase4_features(changed)
    other = perturbed.loc[perturbed["timestamp"].eq(row["timestamp"])].iloc[0]
    return bool(np.allclose(row[ALL_FEATURES].to_numpy(float), other[ALL_FEATURES].to_numpy(float)))
