"""Canonical forecast artifact loading and lineage validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CANONICAL_PHASE = "phase4_5"
CANONICAL_PREDICTION_RELATIVE_PATH = Path("outputs/phase4_5/final_predictions.csv")
CANONICAL_CONFIG_RELATIVE_PATH = Path("outputs/phase4_5/final_config.json")
BUILDING = "Hog_office_Rolando"
FORECAST_HORIZON_HOURS = 24
FEATURE_START = pd.Timestamp("2017-12-01 00:00:00")
FEATURE_END = pd.Timestamp("2017-12-30 23:00:00")
TARGET_START = pd.Timestamp("2017-12-02 00:00:00")
TARGET_END = pd.Timestamp("2017-12-31 23:00:00")
EXPECTED_ROWS = 720
EXPECTED_DAYS = 30
EXPECTED_HOURS_PER_DAY = 24


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_canonical_test_forecast(project_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load the leakage-audited Phase 4.5 Test forecast with strict lineage checks.

    The returned ``timestamp`` is the target timestamp, never the feature timestamp.
    There is intentionally no fallback to any historical Phase 4 artifact.
    """
    root = Path(project_root).resolve()
    prediction_path = root / CANONICAL_PREDICTION_RELATIVE_PATH
    config_path = root / CANONICAL_CONFIG_RELATIVE_PATH
    for path in (prediction_path, config_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    _require(config.get("building") == BUILDING, "Canonical forecast building mismatch")
    _require(
        config.get("forecast_horizon_hours") == FORECAST_HORIZON_HOURS,
        "Canonical forecast horizon must be 24 hours",
    )
    protocol = config.get("selection_protocol", {})
    _require(protocol.get("test_used_for_selection") is False, "Test must not participate in selection")
    boundaries = config.get("feature_time_boundaries", {}).get("test", {})
    _require(boundaries.get("start") == str(FEATURE_START), "Unexpected Test feature start")
    _require(boundaries.get("end") == str(FEATURE_END), "Unexpected Test feature end")
    _require(boundaries.get("samples") == EXPECTED_ROWS, "Unexpected Test feature row count")
    _require(
        protocol.get("train_target_cutoff_exclusive") == "2017-11-01 00:00:00",
        "Train boundary-label purge is not recorded",
    )
    _require(
        protocol.get("validation_target_cutoff_exclusive") == "2017-12-01 00:00:00",
        "Validation boundary-label purge is not recorded",
    )

    source = pd.read_csv(prediction_path)
    required = {
        "split", "feature_timestamp", "target_timestamp", "y_true", "y_pred", "error", "abs_error"
    }
    missing = required - set(source.columns)
    _require(not missing, f"Canonical prediction columns missing: {sorted(missing)}")
    test = source.loc[source["split"].eq("test"), list(required)].copy()
    test["feature_timestamp"] = pd.to_datetime(test["feature_timestamp"], errors="raise")
    test["target_timestamp"] = pd.to_datetime(test["target_timestamp"], errors="raise")
    test = test.sort_values("target_timestamp").reset_index(drop=True)

    _require(len(test) == EXPECTED_ROWS, "Canonical Test forecast must contain 720 rows")
    _require(not test["target_timestamp"].duplicated().any(), "Duplicate target timestamps")
    _require(not test["feature_timestamp"].duplicated().any(), "Duplicate feature timestamps")
    _require(test["feature_timestamp"].min() == FEATURE_START, "Unexpected Test feature start")
    _require(test["feature_timestamp"].max() == FEATURE_END, "Unexpected Test feature end")
    _require(test["target_timestamp"].min() == TARGET_START, "Unexpected Test target start")
    _require(test["target_timestamp"].max() == TARGET_END, "Unexpected Test target end")
    _require(
        test["target_timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all(),
        "Target timestamps must be continuous hourly values",
    )
    _require(
        test["feature_timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all(),
        "Feature timestamps must be continuous hourly values",
    )
    _require(
        (test["target_timestamp"] - test["feature_timestamp"])
        .eq(pd.Timedelta(hours=FORECAST_HORIZON_HOURS))
        .all(),
        "Every target timestamp must equal feature timestamp + 24 hours",
    )
    day_counts = test.groupby(test["target_timestamp"].dt.normalize()).size()
    _require(len(day_counts) == EXPECTED_DAYS, "Canonical Test forecast must cover 30 target days")
    _require(day_counts.eq(EXPECTED_HOURS_PER_DAY).all(), "Every target day must contain 24 hours")

    numeric = test[["y_true", "y_pred", "error", "abs_error"]].to_numpy(dtype=float)
    _require(np.isfinite(numeric).all(), "Canonical forecast contains non-finite values")
    expected_error = test["y_pred"].to_numpy(float) - test["y_true"].to_numpy(float)
    _require(np.allclose(test["error"], expected_error, atol=1e-12, rtol=0.0), "error is inconsistent")
    _require(
        np.allclose(test["abs_error"], np.abs(expected_error), atol=1e-12, rtol=0.0),
        "abs_error is inconsistent",
    )

    normalized = test.rename(
        columns={"target_timestamp": "timestamp", "y_true": "actual", "y_pred": "prediction"}
    )[["timestamp", "actual", "prediction", "error", "abs_error"]]
    lineage = {
        "canonical_phase": "Phase 4.5",
        "prediction_file": CANONICAL_PREDICTION_RELATIVE_PATH.as_posix(),
        "config_file": CANONICAL_CONFIG_RELATIVE_PATH.as_posix(),
        "prediction_sha256": sha256_file(prediction_path),
        "config_sha256": sha256_file(config_path),
        "timestamp_semantics": "timestamp is Phase 4.5 target_timestamp (feature_timestamp + 24h)",
        "rows": EXPECTED_ROWS,
        "days": EXPECTED_DAYS,
        "hours_per_day": EXPECTED_HOURS_PER_DAY,
        "forecast_horizon_hours": FORECAST_HORIZON_HOURS,
        "selection_protocol": protocol,
    }
    return normalized, lineage
