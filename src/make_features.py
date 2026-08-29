"""Leakage-safe feature construction for a 24-hour-ahead load forecast."""

from __future__ import annotations

import numpy as np
import pandas as pd

ONE_HOUR = np.timedelta64(1, "h")
HORIZON = np.timedelta64(24, "h")

FEATURE_COLUMNS = [
    "current_load",
    "hour", "day_of_week", "month", "day_of_year", "is_weekend",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "lag_1", "lag_2", "lag_3", "lag_24", "lag_48", "lag_72", "lag_168",
    "rolling_mean_24", "rolling_std_24", "rolling_min_24", "rolling_max_24",
    "rolling_mean_168", "rolling_std_168",
]


def make_supervised_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[["timestamp", "load"]].copy().sort_values("timestamp").reset_index(drop=True)
    if data["timestamp"].duplicated().any():
        raise ValueError("存在重复时间戳")
    if len(data) > 1 and not data["timestamp"].diff().dropna().eq(ONE_HOUR).all():
        raise ValueError("特征构造前必须补齐为连续小时索引")

    ts = data["timestamp"]
    load = data["load"]
    data["current_load"] = load
    data["hour"] = ts.dt.hour
    data["day_of_week"] = ts.dt.dayofweek
    data["month"] = ts.dt.month
    data["day_of_year"] = ts.dt.dayofyear
    data["is_weekend"] = (data["day_of_week"] >= 5).astype(np.int8)
    data["hour_sin"] = np.sin(2 * np.pi * data["hour"] / 24)
    data["hour_cos"] = np.cos(2 * np.pi * data["hour"] / 24)
    data["dow_sin"] = np.sin(2 * np.pi * data["day_of_week"] / 7)
    data["dow_cos"] = np.cos(2 * np.pi * data["day_of_week"] / 7)
    data["month_sin"] = np.sin(2 * np.pi * (data["month"] - 1) / 12)
    data["month_cos"] = np.cos(2 * np.pi * (data["month"] - 1) / 12)
    for lag in (1, 2, 3, 24, 48, 72, 168):
        data[f"lag_{lag}"] = load.shift(lag)

    # shift(1) is mandatory: every rolling window ends at t-1, so it cannot use
    # the current row or any future load. load.rolling(...) would include t.
    history = load.shift(1)
    for window in (24, 168):
        rolling = history.rolling(window=window, min_periods=window)
        data[f"rolling_mean_{window}"] = rolling.mean()
        data[f"rolling_std_{window}"] = rolling.std()
        if window == 24:
            data["rolling_min_24"] = rolling.min()
            data["rolling_max_24"] = rolling.max()

    data["target_timestamp"] = ts + HORIZON
    data["target"] = load.shift(-24)
    data["yesterday_pred"] = load  # target_time - 24h = feature time t
    data["last_week_pred"] = load.shift(144)  # target_time - 168h = t - 144h
    required = FEATURE_COLUMNS + ["target", "yesterday_pred", "last_week_pred"]
    result = data.dropna(subset=required).copy()
    if not (result["target_timestamp"] == result["timestamp"] + HORIZON).all():
        raise AssertionError("target timestamp 对齐失败")
    source = data.set_index("timestamp")["load"]
    expected = result["target_timestamp"].map(source)
    if not np.allclose(result["target"], expected, equal_nan=False):
        raise AssertionError("target load 未严格对应 t+24h")
    if not np.isfinite(result[FEATURE_COLUMNS + ["target"]].to_numpy()).all():
        raise ValueError("监督学习数据含 NaN 或 inf")
    return result.reset_index(drop=True)
