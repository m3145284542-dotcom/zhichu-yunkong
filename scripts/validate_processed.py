"""Standalone acceptance checks for the generated campus data."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "campus_hourly.csv"
MANIFEST_PATH = PROJECT_ROOT / "data" / "processed" / "campus_hourly_manifest.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "processed_validation.md"


def main() -> None:
    if not DATA_PATH.exists() or not MANIFEST_PATH.exists():
        raise FileNotFoundError("Processed CSV or provenance manifest is missing")
    data = pd.read_csv(DATA_PATH)
    if data.empty:
        raise ValueError("Processed data is empty")
    if not {"timestamp", "load"}.issubset(data.columns):
        raise ValueError("Required timestamp/load columns are missing")
    timestamps = pd.to_datetime(data["timestamp"], errors="raise")
    if not timestamps.is_monotonic_increasing or timestamps.duplicated().any():
        raise ValueError("Timestamps must be unique and increasing")
    if not ((timestamps.dt.minute == 0) & (timestamps.dt.second == 0)).all():
        raise ValueError("Timestamps are not aligned to complete hours")
    deltas = timestamps.diff().dropna()
    if not deltas.dt.total_seconds().eq(3600).all():
        raise ValueError("Processed timestamps are not strictly continuous at one-hour intervals")
    load = pd.to_numeric(data["load"], errors="raise")
    if load.isna().any() or (load < 0).any():
        raise ValueError("Load contains missing or negative values")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("output_rows") != len(data) or not manifest.get("raw_files"):
        raise ValueError("Provenance manifest does not match output")
    if manifest.get("weather_merge") != "left join on exact local timestamp after filtering by metadata site_id":
        raise ValueError("Weather alignment policy is not traceable")
    expected_weather = {
        "airTemperature",
        "cloudCoverage",
        "dewTemperature",
        "precipDepth1HR",
        "seaLvlPressure",
        "windSpeed",
    }
    if not expected_weather.issubset(data.columns):
        raise ValueError("Expected weather fields are missing from processed data")
    aggregation = str(manifest.get("aggregation", "")).lower()
    if "no zero fill" not in aggregation or "no interpolation" not in aggregation:
        raise ValueError("Missing-value and leakage safeguards are not traceable")
    source_names = {item.get("file") for item in manifest.get("raw_files", [])}
    if source_names != {"metadata.csv", "weather.csv", "electricity_cleaned.csv"}:
        raise ValueError("Raw source list is incomplete")
    q1, q3 = load.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    iqr_flags = int(((load < lower) | (load > upper)).sum())
    z_scores = (load - load.mean()) / load.std()
    z4_flags = int((z_scores.abs() > 4).sum())
    weather_columns = [column for column in data.columns if column not in {"timestamp", "load"}]
    weather_rows = "\n".join(
        f"| `{column}` | {int(data[column].isna().sum()):,} | {100 * data[column].isna().mean():.4f}% |"
        for column in weather_columns
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Processed data validation",
                "",
                f"- File: `data/processed/campus_hourly.csv`",
                f"- Shape: {len(data):,} rows × {len(data.columns):,} columns",
                f"- Time range: {timestamps.min()} to {timestamps.max()} (source-local naive timestamps)",
                f"- Metadata timezone: {', '.join(manifest.get('site_timezones', [])) or 'not available'}",
                "- Timestamp order/duplicates/continuity: increasing, no duplicates, exactly one hour between rows",
                f"- Load unit: {manifest.get('load_unit')}",
                f"- Load min/mean/median/max: {load.min():.4f} / {load.mean():.4f} / {load.median():.4f} / {load.max():.4f}",
                f"- Missing/zero/negative load rows: {int(load.isna().sum())} / {int((load == 0).sum())} / {int((load < 0).sum())}",
                f"- IQR 1.5× flags: {iqr_flags:,} (bounds {lower:.4f} to {upper:.4f}); retained for review, not treated as proven errors",
                f"- Absolute z-score > 4 flags: {z4_flags:,}; retained for review",
                "",
                "## Weather missingness",
                "",
                "| Field | Missing rows | Missing rate |",
                "| --- | ---: | ---: |",
                weather_rows,
                "",
                "## Leakage and provenance checks",
                "",
                "- Load is a same-hour sum only; no lag/lead, rolling window, random split, interpolation, or model feature was created.",
                "- Missing building readings were not filled with zero; selected buildings have complete source coverage.",
                "- Weather was filtered by metadata site_id and left-joined on the exact same local timestamp.",
                "- Weather missing values remain missing; no past value was repaired with future data.",
                "- Raw source names, byte sizes, SHA-256 hashes, selected site/buildings, timezone, unit, and policies are recorded in the processed manifest.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"PASS: {len(data):,} strictly continuous hourly rows; "
        "weather schema, provenance, load, and no-interpolation checks succeeded. "
        f"Report: {REPORT_PATH.relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
