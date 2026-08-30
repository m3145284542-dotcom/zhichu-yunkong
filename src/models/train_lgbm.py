"""Small CPU LightGBM helpers shared by the Phase 4 runner and tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def split_by_feature_time(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    timestamp = frame["timestamp"]
    return {
        "train": frame.loc[(timestamp >= "2016-01-01") & (timestamp < "2017-11-01")].copy(),
        "validation": frame.loc[(timestamp >= "2017-11-01") & (timestamp < "2017-12-01")].copy(),
        "test": frame.loc[(timestamp >= "2017-12-01") & (timestamp < "2018-01-01")].copy(),
    }


def purge_unavailable_targets(frame: pd.DataFrame, forecast_start: str | pd.Timestamp) -> pd.DataFrame:
    """Keep rows whose labels are observable strictly before a forecast period starts."""
    cutoff = pd.Timestamp(forecast_start)
    if "target_timestamp" not in frame:
        raise KeyError("target_timestamp")
    return frame.loc[frame["target_timestamp"] < cutoff].copy()


def safe_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    nonzero = np.abs(actual) > 1e-12
    if not nonzero.any():
        return 0.0
    return float(100.0 * np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])))


def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "MAPE": safe_mape(actual, predicted),
    }


def fit_lgbm(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: list[str],
    parameters: dict[str, object],
    train_sample_weight: np.ndarray | pd.Series | None = None,
):
    """Fit LightGBM with the supported 4.x sklearn API.

    ``train_sample_weight`` is optional so historical Phase 4/4.5 callers keep the
    same behavior while Phase 6 can emphasize peak-load samples.
    """
    import lightgbm as lgb
    from lightgbm import LGBMRegressor

    if train_sample_weight is not None:
        weights = np.asarray(train_sample_weight, dtype=float)
        if weights.shape != (len(train),):
            raise ValueError("train_sample_weight must have one value per training row")
        if not np.isfinite(weights).all() or (weights <= 0).any():
            raise ValueError("train_sample_weight must contain finite positive values")
    else:
        weights = None

    model = LGBMRegressor(**parameters)
    model.fit(
        train[features],
        train["target"],
        sample_weight=weights,
        eval_set=[(validation[features], validation["target"])],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    prediction = np.maximum(model.predict(validation[features], num_iteration=model.best_iteration_), 0.0)
    return model, prediction
