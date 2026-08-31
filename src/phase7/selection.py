"""Train-only office morphology profiling and deterministic representative sampling."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


ANCHOR_BUILDING = "Hog_office_Rolando"
TRAIN_END = pd.Timestamp("2017-11-01")
VALIDATION_END = pd.Timestamp("2017-12-01")
MORPHOLOGY_FEATURES = [
    "log_mean_load", "coefficient_of_variation", "peak_to_average_ratio",
    "normalized_peak_valley_range", "lag24_autocorrelation", "lag168_autocorrelation",
    "weekday_weekend_difference_normalized", "daily_profile_variability_normalized",
    "robust_outlier_fraction",
]


@dataclass(frozen=True)
class QualityRules:
    train_missing_fraction_max: float = 0.01
    validation_missing_fraction_max: float = 0.0
    test_missing_fraction_max: float = 0.0
    zero_fraction_max: float = 0.20
    minimum_train_valid_samples: int = 24 * 365
    required_validation_samples: int = 24 * 30
    required_test_samples: int = 24 * 31

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _daily_profile_variability(series: pd.Series) -> float:
    frame = pd.DataFrame({"load": series, "date": series.index.normalize(), "hour": series.index.hour})
    profiles = frame.pivot(index="date", columns="hour", values="load").dropna()
    return float(profiles.std(axis=0, ddof=0).mean()) if not profiles.empty else float("nan")


def profile_office_buildings(
    electricity: pd.DataFrame, office_buildings: list[str], rules: QualityRules = QualityRules()
) -> pd.DataFrame:
    """Compute morphology on Train only; Validation/Test are read only for quality coverage."""
    timestamps = pd.to_datetime(electricity["timestamp"], errors="raise")
    expected = pd.date_range(timestamps.iloc[0], timestamps.iloc[-1], freq="h")
    if timestamps.duplicated().any() or not timestamps.reset_index(drop=True).equals(pd.Series(expected, name="timestamp")):
        raise ValueError("Raw timestamps must be unique, sorted, and hourly-continuous")
    train_mask = timestamps < TRAIN_END
    validation_mask = (timestamps >= TRAIN_END) & (timestamps < VALIDATION_END)
    test_mask = timestamps >= VALIDATION_END
    rows = []
    for building in sorted(set(office_buildings).intersection(electricity.columns)):
        raw = pd.to_numeric(electricity[building], errors="coerce")
        train = pd.Series(raw.loc[train_mask].to_numpy(float), index=timestamps.loc[train_mask])
        validation, test = raw.loc[validation_mask], raw.loc[test_mask]
        valid = train.dropna()
        mean, std = float(valid.mean()), float(valid.std(ddof=0))
        minimum, maximum, p95 = float(valid.min()), float(valid.max()), float(valid.quantile(0.95))
        q1, q3 = valid.quantile([0.25, 0.75]); iqr = float(q3 - q1)
        outlier_fraction = float(((valid < q1 - 3 * iqr) | (valid > q3 + 3 * iqr)).mean()) if iqr > 0 else 0.0
        weekday = float(valid.loc[valid.index.dayofweek < 5].mean())
        weekend = float(valid.loc[valid.index.dayofweek >= 5].mean())
        daily_variability = _daily_profile_variability(train)
        train_missing = float(train.isna().mean())
        validation_missing, test_missing = float(validation.isna().mean()), float(test.isna().mean())
        zero_fraction, negative_count = float((valid == 0).mean()), int((valid < 0).sum())
        finite = bool(np.isfinite([mean, std, minimum, maximum, p95, daily_variability]).all())
        checks = {
            "train_missing": train_missing <= rules.train_missing_fraction_max,
            "validation_missing": validation_missing <= rules.validation_missing_fraction_max,
            "test_missing": test_missing <= rules.test_missing_fraction_max,
            "zero_fraction": zero_fraction <= rules.zero_fraction_max,
            "no_negative_load": negative_count == 0,
            "sufficient_train": len(valid) >= rules.minimum_train_valid_samples,
            "valid_scale": finite and mean > 0 and std > 1e-9,
            "validation_coverage": int(validation.notna().sum()) >= rules.required_validation_samples,
            "test_coverage": int(test.notna().sum()) >= rules.required_test_samples,
        }
        peak_valley = maximum - minimum
        rows.append({
            "building": building, "primaryspaceusage": "Office", "quality_pass": all(checks.values()),
            "quality_failure_reasons": ";".join(key for key, passed in checks.items() if not passed),
            "train_valid_samples": int(len(valid)), "validation_valid_samples": int(validation.notna().sum()),
            "test_valid_samples": int(test.notna().sum()), "mean_load": mean, "std": std,
            "coefficient_of_variation": std / mean, "min": minimum, "max": maximum, "p95": p95,
            "peak_to_average_ratio": maximum / mean, "peak_valley_range": peak_valley,
            "normalized_peak_valley_range": peak_valley / mean,
            "lag24_autocorrelation": float(train.corr(train.shift(24))),
            "lag168_autocorrelation": float(train.corr(train.shift(168))),
            "weekday_weekend_difference": weekday - weekend,
            "weekday_weekend_difference_normalized": (weekday - weekend) / mean,
            "daily_profile_variability": daily_variability,
            "daily_profile_variability_normalized": daily_variability / mean,
            "robust_outlier_fraction": outlier_fraction, "zero_fraction": zero_fraction,
            "missing_fraction": train_missing, "validation_missing_fraction": validation_missing,
            "test_missing_fraction": test_missing, "negative_count": negative_count,
            "log_mean_load": float(np.log1p(mean)),
            "morphology_data_scope": "Train raw load only",
            "quality_coverage_scope": "Train/Validation/Test raw availability only; no model or decision metrics",
        })
    return pd.DataFrame(rows).sort_values("building").reset_index(drop=True)


def robust_standardize(frame: pd.DataFrame) -> pd.DataFrame:
    values = frame[MORPHOLOGY_FEATURES].astype(float)
    median = values.median()
    scale = (values.quantile(0.75) - values.quantile(0.25)).replace(0, np.nan)
    scale = scale.fillna(values.std(ddof=0)).replace(0, 1).fillna(1)
    return ((values - median) / scale).clip(-5, 5)


def select_representative_buildings(
    statistics: pd.DataFrame, count: int = 8, anchor: str = ANCHOR_BUILDING
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = statistics.loc[statistics["quality_pass"]].sort_values("building").reset_index(drop=True)
    if len(eligible) < count or anchor not in set(eligible["building"]):
        raise ValueError("Insufficient eligible offices or canonical anchor failed quality")
    z = robust_standardize(eligible)
    if not np.isfinite(z.to_numpy()).all():
        raise ValueError("Non-finite eligible morphology")
    names, matrix = eligible["building"].tolist(), z.to_numpy(float)
    chosen = [names.index(anchor)]
    distance = np.linalg.norm(matrix - matrix[chosen[0]], axis=1)
    selected_distance = [0.0]
    while len(chosen) < count:
        distance[chosen] = -np.inf
        maximum = float(distance.max())
        ties = np.flatnonzero(np.isclose(distance, maximum, atol=1e-12, rtol=0))
        index = min((int(i) for i in ties), key=lambda i: names[i])
        chosen.append(index); selected_distance.append(maximum)
        distance = np.minimum(distance, np.linalg.norm(matrix - matrix[index], axis=1))
    selected = eligible.iloc[chosen].copy().reset_index(drop=True)
    selected["selection_order"] = np.arange(count)
    selected["distance_at_selection"] = selected_distance
    reasons = []
    for order, source_index in enumerate(chosen):
        if order == 0:
            reasons.append("Phase 3–6 canonical anchor; passed the same frozen quality rules")
            continue
        row = z.iloc[source_index]
        strongest = row.abs().sort_values(ascending=False).head(3).index
        labels = [f"{'high' if row[key] >= 0 else 'low'} {key}" for key in strongest]
        reasons.append("deterministic morphology coverage: " + ", ".join(labels))
    selected["selection_reason"] = reasons
    selected["selection_method"] = "anchor + deterministic farthest-point sampling on robust-scaled Train-only morphology"
    annotated = statistics.copy()
    annotated["selected"] = annotated["building"].isin(selected["building"])
    annotated["selection_order"] = annotated["building"].map(dict(zip(selected["building"], selected["selection_order"])))
    return annotated.sort_values(["selected", "building"], ascending=[False, True]), selected
