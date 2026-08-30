"""Canonical forecast artifact loading and lineage checks.

Phase 4 is retained as a historical benchmark. Phase 4.5 is the authoritative
forecast artifact for downstream decision stages because it applies the audited
boundary-label purge before final model fitting.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BUILDING = "Hog_office_Rolando"
FORECAST_HORIZON_HOURS = 24
TEST_FEATURE_START = pd.Timestamp("2017-12-01 00:00:00")
TEST_FEATURE_END = pd.Timestamp("2017-12-30 23:00:00")
TEST_TARGET_START = pd.Timestamp("2017-12-02 00:00:00")
TEST_TARGET_END = pd.Timestamp("2017-12-31 23:00:00")
EXPECTED_TEST_ROWS = 720

CANONICAL_PREDICTION_RELATIVE_PATH = Path("outputs/phase4_5/final_predictions.csv")
CANONICAL_CONFIG_RELATIVE_PATH = Path("outputs/phase4_5/final_config.json")
HISTORICAL_PHASE4_PREDICTION_RELATIVE_PATH = Path("outputs/phase4/test_prediction.csv")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_phase45_config(config: dict[str, Any]) -> None:
    if config.get("building") != BUILDING:
        raise AssertionError("Phase 4.5 building changed")
    if int(config.get("forecast_horizon_hours", -1)) != FORECAST_HORIZON_HOURS:
        raise AssertionError("Phase 4.5 forecast horizon changed")
    if config.get("selection_protocol", {}).get("test_used_for_selection") is not False:
        raise AssertionError("Phase 4.5 must not use Test for model selection")

    test = config.get("feature_time_boundaries", {}).get("test", {})
    if pd.Timestamp(test.get("start")) != TEST_FEATURE_START:
        raise AssertionError("Phase 4.5 test feature start changed")
    if pd.Timestamp(test.get("end")) != TEST_FEATURE_END:
        raise AssertionError("Phase 4.5 test feature end changed")
    if int(test.get("samples", -1)) != EXPECTED_TEST_ROWS:
        raise AssertionError("Phase 4.5 test row count changed")


def load_canonical_test_forecast(project_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load the Phase 4.5 final Test forecast in the normalized Phase 5 schema.

    Returns a 720-row dataframe with columns:
    timestamp, actual, prediction, error, abs_error.
    """

    prediction_path = project_root / CANONICAL_PREDICTION_RELATIVE_PATH
    config_path = project_root / CANONICAL_CONFIG_RELATIVE_PATH
    if not prediction_path.exists():
        raise FileNotFoundError(prediction_path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    _validate_phase45_config(config)

    raw = pd.read_csv(prediction_path)
    required = {
        "split",
        "feature_timestamp",
        "target_timestamp",
        "y_true",
        "y_pred",
        "error",
        "abs_error",
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Phase 4.5 final prediction columns missing: {sorted(missing)}")

    raw["feature_timestamp"] = pd.to_datetime(raw["feature_timestamp"], errors="raise")
    raw["target_timestamp"] = pd.to_datetime(raw["target_timestamp"], errors="raise")
    test = raw.loc[raw["split"].eq("test")].copy()
    test = test.sort_values("target_timestamp").reset_index(drop=True)

    if len(test) != EXPECTED_TEST_ROWS:
        raise AssertionError(f"Expected {EXPECTED_TEST_ROWS} Phase 4.5 Test rows, got {len(test)}")
    if test["feature_timestamp"].min() != TEST_FEATURE_START or test["feature_timestamp"].max() != TEST_FEATURE_END:
        raise AssertionError("Phase 4.5 Test feature-time window changed")
    if test["target_timestamp"].min() != TEST_TARGET_START or test["target_timestamp"].max() != TEST_TARGET_END:
        raise AssertionError("Phase 4.5 Test target-time window changed")
    if test["target_timestamp"].duplicated().any():
        raise AssertionError("Duplicate Phase 4.5 Test target timestamps")
    if not test["target_timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise AssertionError("Phase 4.5 Test target timestamps are not hourly")
    if not (test["target_timestamp"] - test["feature_timestamp"]).eq(pd.Timedelta(hours=24)).all():
        raise AssertionError("Phase 4.5 target is not exactly t+24h")
    if test["target_timestamp"].dt.normalize().nunique() != 30:
        raise AssertionError("Phase 4.5 Test must contain 30 target days")
    if not test.groupby(test["target_timestamp"].dt.normalize()).size().eq(24).all():
        raise AssertionError("Every Phase 4.5 Test target day must contain 24 hours")
    if not np.isfinite(test[["y_true", "y_pred", "error", "abs_error"]].to_numpy(dtype=float)).all():
        raise AssertionError("Phase 4.5 Test prediction contains non-finite values")

    recomputed_error = test["y_pred"].to_numpy(dtype=float) - test["y_true"].to_numpy(dtype=float)
    if not np.allclose(recomputed_error, test["error"].to_numpy(dtype=float), atol=1e-10, rtol=0.0):
        raise AssertionError("Phase 4.5 saved error column is inconsistent")
    if not np.allclose(np.abs(recomputed_error), test["abs_error"].to_numpy(dtype=float), atol=1e-10, rtol=0.0):
        raise AssertionError("Phase 4.5 saved abs_error column is inconsistent")

    normalized = pd.DataFrame(
        {
            "timestamp": test["target_timestamp"].to_numpy(),
            "actual": test["y_true"].to_numpy(dtype=float),
            "prediction": test["y_pred"].to_numpy(dtype=float),
            "error": recomputed_error,
            "abs_error": np.abs(recomputed_error),
        }
    )

    metadata: dict[str, Any] = {
        "canonical_phase": "phase4_5",
        "canonical_prediction_file": CANONICAL_PREDICTION_RELATIVE_PATH.as_posix(),
        "canonical_config_file": CANONICAL_CONFIG_RELATIVE_PATH.as_posix(),
        "canonical_prediction_sha256": sha256(prediction_path),
        "canonical_config_sha256": sha256(config_path),
        "source_schema": list(raw.columns),
        "normalized_schema": list(normalized.columns),
        "test_split_filter": "split == 'test'",
        "timestamp_semantics": "normalized timestamp is Phase 4.5 target_timestamp (t+24h)",
        "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
        "rows": EXPECTED_TEST_ROWS,
        "days": 30,
        "hours_per_day": 24,
        "selection_protocol": config["selection_protocol"],
    }
    return normalized, metadata
