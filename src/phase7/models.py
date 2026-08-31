"""Fixed-budget, deterministic tree model adapters."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


RANDOM_SEED = 42
MAX_TREES = 500
MODEL_CANDIDATES: dict[str, tuple[tuple[str, dict[str, Any]], ...]] = {
    "LightGBM": (
        ("balanced", {"num_leaves": 31, "max_depth": -1, "min_child_samples": 20, "reg_lambda": 0.0}),
        ("small_regularized", {"num_leaves": 15, "max_depth": 6, "min_child_samples": 30, "reg_lambda": 0.2}),
    ),
    "XGBoost": (
        ("balanced", {"max_depth": 6, "min_child_weight": 1.0, "reg_lambda": 1.0}),
        ("small_regularized", {"max_depth": 4, "min_child_weight": 5.0, "reg_lambda": 2.0}),
    ),
    "CatBoost": (
        ("balanced", {"depth": 6, "l2_leaf_reg": 3.0}),
        ("small_regularized", {"depth": 4, "l2_leaf_reg": 5.0}),
    ),
}


def fit_candidate(family: str, train: pd.DataFrame, validation: pd.DataFrame, features: list[str], overrides: dict[str, Any]) -> tuple[Any, int]:
    if family == "LightGBM":
        import lightgbm as lgb
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(
            objective="regression", n_estimators=MAX_TREES, learning_rate=0.03,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
            random_state=RANDOM_SEED, n_jobs=4, verbosity=-1, deterministic=True,
            force_col_wise=True, **overrides,
        )
        model.fit(train[features], train["target"], eval_set=[(validation[features], validation["target"])],
                  eval_metric="rmse", callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
        return model, int(model.best_iteration_)
    if family == "XGBoost":
        from xgboost import XGBRegressor
        model = XGBRegressor(
            objective="reg:squarederror", n_estimators=MAX_TREES, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_SEED,
            n_jobs=4, tree_method="hist", early_stopping_rounds=50, **overrides,
        )
        model.fit(train[features], train["target"], eval_set=[(validation[features], validation["target"])], verbose=False)
        return model, int(model.best_iteration + 1)
    if family == "CatBoost":
        from catboost import CatBoostRegressor
        model = CatBoostRegressor(
            loss_function="RMSE", iterations=MAX_TREES, learning_rate=0.03,
            random_seed=RANDOM_SEED, thread_count=4, verbose=False,
            allow_writing_files=False, random_strength=0.0, **overrides,
        )
        model.fit(train[features], train["target"], eval_set=(validation[features], validation["target"]),
                  early_stopping_rounds=50, verbose=False)
        return model, int(model.get_best_iteration() + 1)
    raise ValueError(family)


def predict(model: Any, family: str, frame: pd.DataFrame, features: list[str], iteration: int) -> np.ndarray:
    if family == "LightGBM":
        values = model.predict(frame[features], num_iteration=iteration)
    elif family == "XGBoost":
        values = model.predict(frame[features], iteration_range=(0, iteration))
    elif family == "CatBoost":
        values = model.predict(frame[features], ntree_end=iteration)
    else:
        raise ValueError(family)
    return np.maximum(np.asarray(values, float), 0.0)


def refit_fixed(family: str, frame: pd.DataFrame, features: list[str], overrides: dict[str, Any], iteration: int) -> Any:
    if family == "LightGBM":
        from lightgbm import LGBMRegressor
        model = LGBMRegressor(objective="regression", n_estimators=iteration, learning_rate=0.03,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=RANDOM_SEED,
            n_jobs=4, verbosity=-1, deterministic=True, force_col_wise=True, **overrides)
    elif family == "XGBoost":
        from xgboost import XGBRegressor
        model = XGBRegressor(objective="reg:squarederror", n_estimators=iteration, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_SEED, n_jobs=4,
            tree_method="hist", **overrides)
    elif family == "CatBoost":
        from catboost import CatBoostRegressor
        model = CatBoostRegressor(loss_function="RMSE", iterations=iteration, learning_rate=0.03,
            random_seed=RANDOM_SEED, thread_count=4, verbose=False, allow_writing_files=False,
            random_strength=0.0, **overrides)
    else:
        raise ValueError(family)
    if family == "LightGBM":
        model.fit(frame[features], frame["target"])
    else:
        model.fit(frame[features], frame["target"], verbose=False)
    return model
