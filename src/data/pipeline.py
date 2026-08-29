"""BDG2 stage-two audit, education-site selection, and safe aggregation."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EXPECTED_WEATHER = [
    "airTemperature",
    "cloudCoverage",
    "dewTemperature",
    "precipDepth1HR",
    "seaLvlPressure",
    "windSpeed",
]


def parse_timestamps(series: pd.Series, label: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    if parsed.isna().any():
        raise ValueError(f"{label}: {int(parsed.isna().sum())} timestamps cannot be parsed")
    return parsed


def aggregate_complete_load(electricity: pd.DataFrame, building_ids: list[str]) -> pd.DataFrame:
    if not building_ids:
        raise ValueError("At least one building is required")
    missing = sorted(set(building_ids) - set(electricity.columns))
    if missing:
        raise ValueError(f"Unknown electricity columns: {missing}")
    load = electricity[building_ids].sum(axis=1, min_count=len(building_ids))
    return pd.DataFrame({"timestamp": electricity["timestamp"], "load": load})


def merge_load_weather(load: pd.DataFrame, weather: pd.DataFrame, site_id: str) -> pd.DataFrame:
    site_weather = weather.loc[weather["site_id"] == site_id].copy()
    if site_weather.empty:
        raise ValueError(f"No weather rows found for site {site_id}")
    site_weather = site_weather.drop(columns=["site_id"])
    if site_weather["timestamp"].duplicated().any():
        numeric = site_weather.select_dtypes(include="number").columns.tolist()
        site_weather = site_weather.groupby("timestamp", as_index=False)[numeric].mean()
    merged = load.merge(site_weather, on="timestamp", how="left", validate="one_to_one")
    return merged.sort_values("timestamp").reset_index(drop=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{100 * value:.2f}%"


def _markdown_table(frame: pd.DataFrame, columns: Iterable[str] | None = None) -> str:
    view = frame if columns is None else frame[list(columns)]
    headers = [str(column) for column in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in view.itertuples(index=False, name=None):
        values = []
        for value in row:
            if pd.isna(value):
                values.append("")
            elif isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _frequency_summary(timestamps: pd.Series) -> tuple[str, float]:
    unique = timestamps.drop_duplicates().sort_values()
    deltas = unique.diff().dropna()
    if deltas.empty:
        return "unknown", math.nan
    mode = deltas.mode().iloc[0]
    hourly_share = float((deltas == pd.Timedelta(hours=1)).mean())
    return str(mode), hourly_share


def _building_quality(electricity: pd.DataFrame) -> pd.DataFrame:
    value_columns = [column for column in electricity.columns if column != "timestamp"]
    values = electricity[value_columns]
    valid = values.notna()
    starts = {column: electricity.loc[valid[column], "timestamp"].min() for column in value_columns}
    ends = {column: electricity.loc[valid[column], "timestamp"].max() for column in value_columns}
    rows = []
    for column in value_columns:
        non_missing = values[column].dropna()
        rows.append(
            {
                "building_id": column,
                "valid_ratio": float(valid[column].mean()),
                "zero_ratio_valid": float((non_missing == 0).mean()) if len(non_missing) else math.nan,
                "negative_count": int((non_missing < 0).sum()),
                "start": starts[column],
                "end": ends[column],
            }
        )
    return pd.DataFrame(rows)


def _candidate_sites(
    metadata: pd.DataFrame, electricity: pd.DataFrame, weather: pd.DataFrame, building_quality: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    if "primaryspaceusage" not in metadata.columns:
        raise ValueError("metadata.csv has no primaryspaceusage column")
    education = metadata[metadata["primaryspaceusage"].fillna("").astype(str).str.contains("education", case=False)]
    available = set(electricity.columns) - {"timestamp"}
    education = education[education["building_id"].isin(available)].copy()
    if education.empty:
        raise ValueError("No Education buildings with electricity data were found")

    timestamp_count = electricity["timestamp"].nunique()
    site_buildings: dict[str, list[str]] = {}
    rows = []
    for site_id, group in education.groupby("site_id", dropna=False):
        site_id = str(site_id)
        buildings = sorted(group["building_id"].astype(str).tolist())
        site_buildings[site_id] = buildings
        subset = building_quality[building_quality["building_id"].isin(buildings)]
        common_ratio = float(electricity[buildings].notna().all(axis=1).mean())
        weather_ts = weather.loc[weather["site_id"].astype(str) == site_id, "timestamp"].drop_duplicates()
        weather_coverage = float(electricity["timestamp"].isin(weather_ts).sum() / timestamp_count)
        zero_ratio = float(subset["zero_ratio_valid"].fillna(1).mean())
        valid_mean = float(subset["valid_ratio"].mean())
        negative_count = int(subset["negative_count"].sum())
        score = (
            0.35 * valid_mean
            + 0.35 * common_ratio
            + 0.25 * weather_coverage
            + 0.05 * min(len(buildings), 10) / 10
            - 0.10 * min(zero_ratio, 1)
            - (0.25 if negative_count else 0)
        )
        rows.append(
            {
                "site_id": site_id,
                "education_buildings": len(buildings),
                "mean_valid_ratio": valid_mean,
                "common_valid_ratio": common_ratio,
                "weather_coverage": weather_coverage,
                "mean_zero_ratio": zero_ratio,
                "negative_count": negative_count,
                "score": score,
            }
        )
    candidates = pd.DataFrame(rows).sort_values(
        ["score", "education_buildings"], ascending=[False, False]
    ).reset_index(drop=True)
    return candidates, site_buildings


def _select_buildings(
    site_id: str, site_buildings: dict[str, list[str]], electricity: pd.DataFrame, quality: pd.DataFrame
) -> tuple[list[str], str]:
    candidates = quality[quality["building_id"].isin(site_buildings[site_id])].copy()
    candidates["quality"] = candidates["valid_ratio"] - candidates["zero_ratio_valid"].fillna(1)
    candidates = candidates.sort_values(["quality", "building_id"], ascending=[False, True])
    eligible = candidates[
        (candidates["valid_ratio"] >= 0.90)
        & (candidates["zero_ratio_valid"].fillna(1) <= 0.10)
        & (candidates["negative_count"] == 0)
    ]["building_id"].tolist()
    if not eligible:
        eligible = candidates.head(1)["building_id"].tolist()

    complete = candidates[
        np.isclose(candidates["valid_ratio"], 1.0)
        & (candidates["zero_ratio_valid"].fillna(1) <= 0.10)
        & (candidates["negative_count"] == 0)
    ]["building_id"].tolist()
    if len(complete) >= 2:
        return complete, (
            "Campus aggregation uses all qualifying Education buildings with complete coverage; "
            "every retained hour has every selected reading (no zero fill and no interpolation)."
        )

    selected = [eligible[0]]
    for building in eligible[1:]:
        proposed = selected + [building]
        if float(electricity[proposed].notna().all(axis=1).mean()) >= 0.99:
            selected = proposed
    if len(selected) >= 2:
        return selected, (
            "Fallback campus aggregation retains at least 99% simultaneous coverage; every retained hour has "
            "readings from every selected building (no zero fill and no interpolation)."
        )
    return selected, "Fallback to the best Education building because no multi-building set met the 99% common-coverage rule."


def _longest_hourly_segment(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    breaks = frame["timestamp"].diff().ne(pd.Timedelta(hours=1)).cumsum()
    group_id = breaks.value_counts().idxmax()
    return frame.loc[breaks == group_id]


def _plot_all(processed: pd.DataFrame, figures_dir: Path, unit: str) -> list[str]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    def save(name: str) -> None:
        plt.tight_layout()
        plt.savefig(figures_dir / name, dpi=150, bbox_inches="tight")
        plt.close()
        generated.append(name)

    plt.figure(figsize=(12, 4))
    plt.plot(processed["timestamp"], processed["load"], linewidth=0.35)
    plt.title("Campus Load — Full Available Range")
    plt.xlabel("Timestamp (local time)")
    plt.ylabel(f"Hourly electricity ({unit})")
    save("01_full_load_overview.png")

    continuous = _longest_hourly_segment(processed[["timestamp", "load"]])
    seven_days = continuous.head(24 * 7)
    plt.figure(figsize=(12, 4))
    plt.plot(seven_days["timestamp"], seven_days["load"], linewidth=1.0)
    plt.title("Campus Load — First Complete 7-Day Window")
    plt.xlabel("Timestamp (local time)")
    plt.ylabel(f"Hourly electricity ({unit})")
    save("02_seven_day_load.png")

    hourly = processed.assign(hour=processed["timestamp"].dt.hour).groupby("hour")["load"].mean()
    plt.figure(figsize=(8, 4))
    plt.plot(hourly.index, hourly.values, marker="o", linewidth=1.2)
    plt.xticks(range(0, 24, 2))
    plt.title("Mean 24-Hour Load Profile")
    plt.xlabel("Hour of day (local time)")
    plt.ylabel(f"Mean hourly electricity ({unit})")
    save("03_mean_24h_profile.png")

    weekday = processed.assign(weekday=processed["timestamp"].dt.dayofweek).groupby("weekday")["load"].mean()
    plt.figure(figsize=(8, 4))
    plt.bar(range(7), weekday.reindex(range(7)).values)
    plt.xticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    plt.title("Mean Load by Day of Week")
    plt.xlabel("Day of week")
    plt.ylabel(f"Mean hourly electricity ({unit})")
    save("04_weekday_mean_load.png")

    if "airTemperature" in processed.columns:
        scatter = processed[["airTemperature", "load"]].dropna()
        step = max(1, len(scatter) // 20000)
        scatter = scatter.iloc[::step]
        plt.figure(figsize=(7, 5))
        plt.scatter(scatter["airTemperature"], scatter["load"], s=5, alpha=0.25)
        plt.title("Air Temperature vs Campus Load")
        plt.xlabel("Air temperature (°C)")
        plt.ylabel(f"Hourly electricity ({unit})")
        save("05_temperature_vs_load.png")
    return generated


def run_pipeline(project_root: Path) -> dict[str, object]:
    raw = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"
    reports = project_root / "reports"
    figures = reports / "figures"
    required = [raw / "metadata.csv", raw / "weather.csv", raw / "electricity_cleaned.csv"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw files: {missing}. Run scripts/download_bdg2.py first.")

    metadata = pd.read_csv(required[0])
    weather = pd.read_csv(required[1], low_memory=False)
    electricity = pd.read_csv(required[2], low_memory=False)
    for frame, label in [(weather, "weather"), (electricity, "electricity")]:
        if "timestamp" not in frame.columns:
            raise ValueError(f"{label}.csv has no timestamp column")
        frame["timestamp"] = parse_timestamps(frame["timestamp"], label)
        frame.sort_values("timestamp", inplace=True)
        frame.reset_index(drop=True, inplace=True)
    if not {"building_id", "site_id"}.issubset(metadata.columns):
        raise ValueError("metadata.csv must contain building_id and site_id")
    weather["site_id"] = weather["site_id"].astype(str)
    metadata["site_id"] = metadata["site_id"].astype(str)

    quality = _building_quality(electricity)
    candidates, site_buildings = _candidate_sites(metadata, electricity, weather, quality)
    multi = candidates[candidates["education_buildings"] >= 2]
    chosen_row = (multi if not multi.empty else candidates).iloc[0]
    chosen_site = str(chosen_row["site_id"])
    selected, selection_policy = _select_buildings(chosen_site, site_buildings, electricity, quality)
    site_timezones = sorted(
        metadata.loc[metadata["site_id"] == chosen_site, "timezone"].dropna().astype(str).unique().tolist()
    ) if "timezone" in metadata.columns else []

    campus = aggregate_complete_load(electricity, selected)
    incomplete_load_rows = int(campus["load"].isna().sum())
    campus = campus.dropna(subset=["load"]).copy()
    processed = merge_load_weather(campus, weather, chosen_site)
    processed = processed.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / "campus_hourly.csv"
    processed.to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")

    frequency, hourly_share = _frequency_summary(electricity["timestamp"])
    weather_fields = [column for column in EXPECTED_WEATHER if column in weather.columns]
    other_weather = [column for column in weather.columns if column not in {"timestamp", "site_id", *EXPECTED_WEATHER}]
    audit_lines = [
        "# BDG2 data audit",
        "",
        "> Generated from the three files in `data/raw`; raw files were read only.",
        "",
        "## Electricity",
        "",
        f"- Shape: {len(electricity):,} rows × {len(electricity.columns):,} columns",
        f"- Timestamp range: {electricity['timestamp'].min()} to {electricity['timestamp'].max()} (local site time)",
        f"- Modal timestamp interval: {frequency}; one-hour delta share: {_pct(hourly_share)}",
        f"- Building columns: {len(electricity.columns) - 1:,}",
        f"- Overall value missing rate: {_pct(float(electricity.drop(columns='timestamp').isna().mean().mean()))}",
        f"- Duplicate timestamps: {int(electricity['timestamp'].duplicated().sum()):,}",
        f"- Negative readings: {int((electricity.drop(columns='timestamp') < 0).sum().sum()):,}",
        "- Unit: kWh summed over each hour (`kWh_sum` in the BDG2 documentation).",
        "",
        "### Per-building validity",
        "",
        _markdown_table(quality.assign(valid_ratio=quality["valid_ratio"] * 100, zero_ratio_valid=quality["zero_ratio_valid"] * 100).rename(columns={"valid_ratio": "valid_%", "zero_ratio_valid": "zero_%_of_valid"})),
        "",
        "## Metadata",
        "",
        f"- Shape: {len(metadata):,} rows × {len(metadata.columns):,} columns",
        f"- Columns actually present: {', '.join(metadata.columns)}",
        f"- Required review fields present: {', '.join(column for column in ['building_id', 'site_id', 'primaryspaceusage', 'sqft', 'sqm', 'timezone'] if column in metadata.columns)}",
        "",
        "### Metadata field completeness",
        "",
        _markdown_table(pd.DataFrame({"field": metadata.columns, "dtype": metadata.dtypes.astype(str).values, "non_missing_%": (metadata.notna().mean() * 100).round(4).values})),
        "",
        "## Weather",
        "",
        f"- Shape: {len(weather):,} rows × {len(weather.columns):,} columns",
        f"- Timestamp range: {weather['timestamp'].min()} to {weather['timestamp'].max()} (local site time)",
        f"- Sites: {weather['site_id'].nunique():,}",
        f"- Duplicate `(site_id, timestamp)` rows: {int(weather.duplicated(['site_id', 'timestamp']).sum()):,}",
        f"- Requested fields actually present: {', '.join(weather_fields) if weather_fields else 'none'}",
        f"- Other fields actually present: {', '.join(other_weather) if other_weather else 'none'}",
        "",
        "### Weather field missingness",
        "",
        _markdown_table(pd.DataFrame({"field": weather.columns, "missing_%": (weather.isna().mean() * 100).round(4).values})),
    ]
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "data_audit.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    selection_rows = []
    for row in candidates.itertuples(index=False):
        buildings = site_buildings[str(row.site_id)]
        details = quality[quality["building_id"].isin(buildings)]
        detail_text = "; ".join(
            f"{r.building_id} ({100*r.valid_ratio:.2f}%, {r.start}–{r.end})" for r in details.itertuples(index=False)
        )
        recommendation = "recommended" if str(row.site_id) == chosen_site else "not selected: lower measured quality score"
        selection_rows.append(
            {
                "site_id": row.site_id,
                "education_count": row.education_buildings,
                "mean_valid_%": 100 * row.mean_valid_ratio,
                "common_valid_%": 100 * row.common_valid_ratio,
                "weather_coverage_%": 100 * row.weather_coverage,
                "zero_%": 100 * row.mean_zero_ratio,
                "negative_count": row.negative_count,
                "score": row.score,
                "decision": recommendation,
                "buildings (valid %, range)": detail_text,
            }
        )
    chosen_quality = quality[quality["building_id"].isin(selected)]
    selection_lines = [
        "# Education site selection",
        "",
        "## Method",
        "",
        "Candidates are metadata rows whose actual `primaryspaceusage` contains `Education` and whose `building_id` exists in the electricity file. The deterministic score combines mean building validity (35%), simultaneous completeness (35%), weather coverage (25%), a small multi-building bonus (5%), and penalties for zeros or negative readings. A multi-building site is preferred when available.",
        "",
        "## Candidate ranking",
        "",
        _markdown_table(pd.DataFrame(selection_rows)),
        "",
        "## Automatic recommendation",
        "",
        f"- Site: `{chosen_site}`",
        f"- Metadata timezone: {', '.join(site_timezones) if site_timezones else 'not available'}",
        f"- Selected Education buildings ({len(selected)}): {', '.join(selected)}",
        f"- Selected-building individual validity: {', '.join(f'{r.building_id}={100*r.valid_ratio:.2f}%' for r in chosen_quality.itertuples(index=False))}",
        f"- Aggregation policy: {selection_policy}",
        f"- Hours excluded because at least one selected building was missing: {incomplete_load_rows:,}",
        "- No missing load value was replaced with zero; no interpolation was performed.",
    ]
    (reports / "site_selection.md").write_text("\n".join(selection_lines) + "\n", encoding="utf-8")

    unit = "kWh"
    figures_generated = _plot_all(processed, figures, unit)
    source_records = [
        {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in required
    ]
    manifest = {
        "dataset": "Building Data Genome Project 2",
        "official_repository": "https://github.com/buds-lab/building-data-genome-project-2",
        "raw_files": source_records,
        "selected_site_id": chosen_site,
        "site_timezones": site_timezones,
        "selected_building_ids": selected,
        "load_unit": unit,
        "aggregation": selection_policy,
        "excluded_incomplete_load_rows": incomplete_load_rows,
        "weather_merge": "left join on exact local timestamp after filtering by metadata site_id",
        "output": str(output_path.relative_to(project_root)),
        "output_rows": len(processed),
        "output_columns": processed.columns.tolist(),
    }
    (processed_dir / "campus_hourly_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "site_id": chosen_site,
        "buildings": selected,
        "processed_rows": len(processed),
        "processed_columns": processed.columns.tolist(),
        "start": str(processed["timestamp"].min()),
        "end": str(processed["timestamp"].max()),
        "missing_rates": processed.isna().mean().to_dict(),
        "figures": figures_generated,
        "source_files": source_records,
    }
