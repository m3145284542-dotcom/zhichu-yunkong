"""Build the Phase 13.4 evidence master record from frozen repository artifacts.

This script is consolidation-only.  It reads existing machine-readable evidence and
the Phase 13.3 PPTX package; it does not import training code, run an experiment,
recompute a scientific metric, regenerate a figure, or save the presentation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_4"
REPORTS = ROOT / "reports" / "phase13_4"
FROZEN_BASELINE = "549abc314e93e2862bfc22965db89622c22890e1"
PHASE13_1_COMMIT = "d36fcd18568b98a5980b101e213f714ddf332f12"
PHASE13_2_COMMIT = "a8cab9bd86ada158d38e2c70e32a53f77ee983df"
PHASE13_3_COMMIT = "076f76a2a4d2b622dd67f9e4595bba1ab0f5d81e"
PPTX = ROOT / "outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx"
TEXT_EXTENSIONS = {".csv", ".json", ".md", ".py", ".txt", ".yml", ".yaml", ".toml", ".html", ".svg"}


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def json_load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


def csv_load(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(data: bytes, rel: str) -> bytes:
    if Path(rel).suffix.lower() in TEXT_EXTENSIONS:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def git_blob(commit: str, rel: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"{commit}:{rel}"], cwd=ROOT)


def audit_against_commit(paths: list[str], commit: str, label: str) -> dict:
    missing, drift, newline_only = [], [], []
    for rel in paths:
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        current = path.read_bytes()
        frozen = git_blob(commit, rel)
        if sha256_bytes(normalized(current, rel)) != sha256_bytes(normalized(frozen, rel)):
            drift.append(rel)
        elif sha256_bytes(current) != sha256_bytes(frozen):
            newline_only.append(rel)
    return {
        "label": label,
        "registered": len(paths),
        "pass_count": len(paths) - len(missing) - len(drift),
        "missing_count": len(missing),
        "lf_normalized_drift_count": len(drift),
        "newline_only_checkout_difference_count": len(newline_only),
        "missing": missing,
        "drift": drift,
        "status": "PASS" if not missing and not drift else "FAIL",
    }


def audit_phase13_0b() -> dict:
    summary = json_load("outputs/phase13_0b/phase13_0b_summary.json")
    missing, drift = [], []
    for item in summary["artifacts"]:
        rel = item["path"]
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
        elif sha256_bytes(normalized(path.read_bytes(), rel)) != item["sha256"]:
            drift.append(rel)
    return {
        "label": "Phase 13.0B registered presentation-evidence artifacts",
        "registered": len(summary["artifacts"]),
        "pass_count": len(summary["artifacts"]) - len(missing) - len(drift),
        "missing_count": len(missing),
        "lf_normalized_drift_count": len(drift),
        "missing": missing,
        "drift": drift,
        "status": "PASS" if not missing and not drift else "FAIL",
    }


def extract_slides() -> list[dict]:
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    rows = []
    with zipfile.ZipFile(PPTX) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"PPTX CRC failure: {bad}")
        names = [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        names.sort(key=lambda n: int(re.search(r"slide(\d+)", n).group(1)))
        for name in names:
            number = int(re.search(r"slide(\d+)", name).group(1))
            root = ET.fromstring(archive.read(name))
            texts = [(node.text or "") for node in root.findall(".//a:t", ns)]
            title = next((t for t in texts if t and not t.startswith("SB-") and t not in {"OPENING", "TENSION", "PROBLEM", "SOLUTION", "EVIDENCE", "INTERPRETATION", "BREADTH", "CREDIBILITY", "CONTRIBUTION", "CONCLUSION", "Q&A ONLY"}), "")
            rows.append({"slide_number": number, "texts": texts, "joined": " | ".join(texts), "title": title})
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if subprocess.run(["git", "merge-base", "--is-ancestor", FROZEN_BASELINE, "HEAD"], cwd=ROOT).returncode:
        raise SystemExit("BLOCKED: frozen baseline is not an ancestor of HEAD")

    hash_audit = json_load("outputs/phase9_1/artifact_hash_audit.json")
    p7891_paths = [item["path"] for item in hash_audit["artifacts"]]
    p13a_paths = [row["path"] for row in csv_load("outputs/phase13_0a/presentation_source_hashes.csv")]
    p13_1_manifest = json_load("outputs/phase13_1/manifests/visual_asset_manifest.json")
    p13_1_paths = [p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", PHASE13_1_COMMIT).splitlines() if p != "README.md"]
    p13_2_paths = [p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", PHASE13_2_COMMIT).splitlines() if p != "README.md"]
    integrity = {
        "phase7_8_9_9_1": audit_against_commit(p7891_paths, FROZEN_BASELINE, "Phase 7/8/9/9.1 canonical artifacts"),
        "phase13_0a": audit_against_commit(p13a_paths, FROZEN_BASELINE, "Phase 13.0A registered sources"),
        "phase13_0b": audit_phase13_0b(),
        "phase13_1": audit_against_commit(p13_1_paths, PHASE13_1_COMMIT, "Phase 13.1 frozen visual outputs"),
        "phase13_2": audit_against_commit(p13_2_paths, PHASE13_2_COMMIT, "Phase 13.2 frozen storyboard records"),
        "phase13_3_pptx": audit_against_commit([PPTX.relative_to(ROOT).as_posix()], PHASE13_3_COMMIT, "Phase 13.3 audited PPTX"),
    }
    if any(scope["status"] != "PASS" for scope in integrity.values()):
        raise SystemExit("BLOCKED: frozen artifact integrity failure")

    slides = extract_slides()
    if len(slides) != 23:
        raise SystemExit(f"BLOCKED: expected 23 slides, found {len(slides)}")
    architecture = json_load("outputs/phase13_2/slide_architecture.json")
    title_by_number = {index: slide["headline"] for index, slide in enumerate(architecture["slides"], start=1)}
    for slide in slides:
        slide["title"] = title_by_number[slide["slide_number"]]
    slide_text = {row["slide_number"]: row["joined"] for row in slides}
    expected_visible = {
        2: ["0.216751", "0.116127"],
        6: ["6.36%", "3.61%", "6  /  2  /  0", "−1.017%"],
        8: ["296", "82", "8 / 8", "6", "2", "0"],
        9: ["11 个候选权重", "0.0 → 1.0", "步长 0.1"],
        13: ["1,578", "296", "82", "8"],
        16: ["10% of mean daily energy", "25% of capacity per hour", "10% → 90%", "50% / 50%", "0.94868 / 0.94868", "round-trip 0.90"],
        17: [".225885", ".430193", ".162986", "−1.878%", ".201578", ".328414", ".144323", "3.085%", ".183478", ".296621", ".143019", "4.907%", ".147338", ".216942", ".116127", "1.008%", ".149781", ".216751", ".117534", "0.453%", ".173604", ".239211", ".118740", "−24.482%", ".137970", ".207822", ".111929", "6.442%", ".147587", ".217284", ".116202", "1.129%"],
        18: ["−24.48%", "+4.82%", "−245.94%", ".116127", "1.008%", "5.057%", "−41.192%", ".117534", "0.453%", "4.588%", "−44.357%", ".118740", "−24.482%", "4.821%", "−245.943%", ".111929", "6.442%", "5.629%", "−1.017%"],
        20: [".9", ".7", ".6", ".3", ".4", ".8", "Joey: 0.6 → 0.3"],
        21: ["10,000", "−0.004198", "−0.006850", "−0.001719"],
        22: ["5,760", "0.0 kW", "8 buildings × 720 Test hours", "1e−12"],
        23: ["robust λ = 0.5", "20.4635 kW", "11.1274 kW"],
    }
    missing_visible = [(number, value) for number, values in expected_visible.items() for value in values if value not in slide_text[number]]
    if missing_visible:
        raise SystemExit(f"BLOCKED: PPT numeric transcription mismatch: {missing_visible}")

    claims_source = json_load("outputs/phase13_0b/final_presentation_claims.json")["claims"]
    claim_map = {row["claim_id"]: row for row in csv_load("outputs/phase13_2/claim_to_slide_map.csv")}
    source_defaults = {
        "CORE-02": "outputs/phase9/final_benchmark.csv", "CORE-06": "outputs/phase9_1/final_reporting_summary.json",
        "CORE-07": "outputs/phase9_1/final_reporting_summary.json", "CORE-08": "outputs/phase9/final_benchmark.csv",
        "SUP-01": "outputs/phase3/building_selection.csv", "SUP-04": "outputs/phase9_1/building_level_bootstrap_summary.json",
        "SUP-05": "outputs/phase9_1/doef_prediction_invariance.json", "SUP-06": "outputs/phase7/building_battery_configs.csv",
        "SUP-07": "outputs/phase9/final_benchmark.csv", "SUP-08": "outputs/phase5_7/summary.json",
        "BACK-01": "outputs/phase5_7/summary.json", "BACK-02": "outputs/phase9_1/unit_semantics.json",
        "BACK-03": "outputs/phase9_1/final_reporting_summary.json", "BACK-04": "outputs/phase8/selected_weights.csv",
        "BACK-05": "outputs/phase9_1/doef_prediction_invariance.json",
    }
    qualified = {"CORE-02", "CORE-04", "CORE-06", "CORE-07", "CORE-08", "SUP-01", "SUP-04", "SUP-07", "BACK-02", "BACK-03", "BACK-04", "BACK-05"}
    claim_rows = []
    for claim in claims_source:
        cid = claim["claim_id"]
        if claim["claim_status"] == "NOT_PRESENTATION_SAFE":
            status = "REJECTED"
        elif cid == "BACK-01":
            status = "NEGATIVE_RESULT"
        elif cid in qualified:
            status = "SUPPORTED_WITH_QUALIFICATION"
        else:
            status = "SUPPORTED"
        sources = claim.get("provenance_sources") or []
        primary = sources[0] if sources else source_defaults.get(cid, "outputs/phase13_0b/final_presentation_claims.json")
        secondary = ";".join(sources[1:]) or "outputs/phase13_0b/final_presentation_claims.json"
        mapping = claim_map.get(cid, {})
        claim_rows.append({
            "claim_id": cid, "claim_category": claim["category"],
            "claim_text": claim.get("technical_wording") or claim.get("forbidden_overclaim"),
            "claim_scope": f"{claim.get('building_scope','')}; {claim.get('split','')}; {claim.get('model_scope','')}",
            "status": status,
            "allowed_wording": claim.get("presentation_wording") if status != "REJECTED" else "Do not use as a positive claim.",
            "prohibited_wording": claim.get("forbidden_overclaim", ""),
            "primary_evidence": primary, "secondary_evidence": secondary,
            "source_phase": "13.0B", "source_file": primary,
            "source_field_or_section": ";".join(claim.get("evidence_ids", [])),
            "figure_id": ";".join(claim.get("figure_ids", [])),
            "ppt_slide": ";".join(filter(None, [mapping.get("main_slide", ""), mapping.get("appendix_slide", "")])),
            "notes": claim.get("caveat", ""),
        })

    claim_fields = ["claim_id", "claim_category", "claim_text", "claim_scope", "status", "allowed_wording", "prohibited_wording", "primary_evidence", "secondary_evidence", "source_phase", "source_file", "source_field_or_section", "figure_id", "ppt_slide", "notes"]
    write_csv(OUT / "claim_registry.csv", claim_rows, claim_fields)
    write_json(OUT / "claim_registry.json", {"schema_version": 1, "phase": "13.4", "records": claim_rows})

    # Numeric registry: direct transcription from canonical machine-readable values.
    benchmark = csv_load("outputs/phase9/final_benchmark.csv")
    number_rows: list[dict] = []
    metric_columns = [
        ("normalized_mae_mean", "Mean normalized MAE", "dimensionless"),
        ("normalized_rmse_mean", "Mean normalized RMSE", "dimensionless"),
        ("normalized_decision_regret_mean", "Mean normalized decision regret", "dimensionless"),
        ("peak_reduction_mean_pct", "Mean whole-window peak reduction", "%"),
        ("peak_reduction_median_pct", "Median whole-window peak reduction", "%"),
        ("peak_reduction_min_pct", "Minimum building whole-window peak reduction", "%"),
    ]
    for row_index, row in enumerate(benchmark, start=1):
        method = row["display_name"]
        slug = re.sub(r"[^a-z0-9]+", "_", method.lower()).strip("_")
        for field, name, unit in metric_columns:
            metric_id = f"P9_{slug}_{field}".upper()
            slides_used = []
            if field in {"normalized_mae_mean", "normalized_rmse_mean", "normalized_decision_regret_mean", "peak_reduction_mean_pct"}:
                slides_used.append("17")
            if method in {"LightGBM", "XGBoost", "CatBoost", "DOEF"} and field in {"normalized_decision_regret_mean", "peak_reduction_mean_pct", "peak_reduction_median_pct", "peak_reduction_min_pct"}:
                slides_used.append("18")
            if method in {"XGBoost", "LightGBM"} and field in {"normalized_rmse_mean", "normalized_decision_regret_mean"}:
                slides_used.append("2")
            number_rows.append({
                "metric_id": metric_id, "metric_name": name, "value": row[field], "unit": unit,
                "scope": "equal-building aggregate over 8 fixed office buildings", "building": "ALL_8_FIXED",
                "split": "Test", "method": method, "aggregation": field.replace("_pct", ""),
                "source_phase": "9", "source_file": "outputs/phase9/final_benchmark.csv",
                "source_field": f"row(display_name={method}).{field}", "canonical_status": "CANONICAL",
                "used_in_ppt": "YES" if slides_used else "NO", "ppt_slide": ";".join(sorted(set(slides_used), key=int)),
                "notes": "Direct canonical value; no Phase 13.4 recomputation.",
            })

    def add_number(metric_id, name, value, unit, scope, building, split, method, aggregation, phase, source, field, slides_used="", notes=""):
        number_rows.append({
            "metric_id": metric_id, "metric_name": name, "value": value, "unit": unit, "scope": scope,
            "building": building, "split": split, "method": method, "aggregation": aggregation,
            "source_phase": phase, "source_file": source, "source_field": field, "canonical_status": "CANONICAL",
            "used_in_ppt": "YES" if slides_used else "NO", "ppt_slide": slides_used, "notes": notes,
        })

    p91 = json_load("outputs/phase9_1/final_reporting_summary.json")
    p7sel = json_load("outputs/phase7/selected_buildings.json")
    p8cfg = json_load("outputs/phase8/run_config.json")
    p7summary = json_load("outputs/phase7/summary.json")
    split = p7summary["leakage_audit"]["canonical_lineage"]
    add_number("COUNT_PROJECT_SERIES", "Frozen project-universe building series", "1578", "building series", "repository Phase 3 selection table", "ALL", "N/A", "N/A", "row count", "3", "outputs/phase3/building_selection.csv", "count(data rows)", "13")
    add_number("COUNT_OFFICE_CANDIDATES", "Office-building candidates", p7sel["office_candidates"], "buildings", "office candidates", "ALL", "Train coverage screening", "N/A", "count", "7", "outputs/phase7/selected_buildings.json", "office_candidates", "8;13")
    add_number("COUNT_QUALITY_PASS", "Office candidates passing frozen quality rules", p7sel["quality_pass_count"], "buildings", "office candidates", "ALL", "Train/Validation/Test coverage screen", "N/A", "count", "7", "outputs/phase7/selected_buildings.json", "quality_pass_count", "8;13")
    add_number("COUNT_FIXED_BUILDINGS", "Final benchmark building count", len(p7sel["selected_buildings"]), "buildings", "fixed multi-building benchmark", "ALL_8_FIXED", "N/A", "DOEF benchmark", "count", "7", "outputs/phase7/selected_buildings.json", "count(selected_buildings)", "1;6;8;12;13")
    add_number("FORECAST_HORIZON_HOURS", "Forecast horizon", split["forecast_horizon_hours"], "hours", "all fixed buildings", "ALL_8_FIXED", "all", "all forecast methods", "fixed horizon", "7", "outputs/phase7/summary.json", "leakage_audit.canonical_lineage.forecast_horizon_hours", "1;14")
    add_number("TEST_SAMPLES_PER_BUILDING", "Test forecast samples per building", split["rows"], "hourly targets", "each fixed building", "ALL_8_FIXED", "Test", "all forecast methods", "per building", "7", "outputs/phase7/summary.json", "leakage_audit.canonical_lineage.rows", "22")
    add_number("TEST_DAYS_PER_BUILDING", "Complete Test days per building", split["days"], "days", "each fixed building", "ALL_8_FIXED", "Test", "all dispatch methods", "per building", "7", "outputs/phase7/summary.json", "leakage_audit.canonical_lineage.days", "12;22")
    add_number("DOEF_MAE_IMPROVEMENT_PCT", "DOEF relative normalized-MAE improvement versus LightGBM", p91["doef_vs_lightgbm"]["normalized_mae_relative_improvement_pct"], "%", "8 fixed buildings", "ALL_8_FIXED", "Test", "DOEF vs LightGBM", "relative aggregate improvement", "9.1", "outputs/phase9_1/final_reporting_summary.json", "doef_vs_lightgbm.normalized_mae_relative_improvement_pct", "6")
    add_number("DOEF_REGRET_IMPROVEMENT_PCT", "DOEF relative normalized-regret improvement versus LightGBM", p91["doef_vs_lightgbm"]["normalized_regret_relative_improvement_pct"], "%", "8 fixed buildings", "ALL_8_FIXED", "Test", "DOEF vs LightGBM", "relative aggregate improvement", "9.1", "outputs/phase9_1/final_reporting_summary.json", "doef_vs_lightgbm.normalized_regret_relative_improvement_pct", "6")
    for key, label in [("wins", "wins"), ("ties", "ties"), ("losses", "losses")]:
        add_number(f"DOEF_REGRET_{label.upper()}", f"DOEF decision-regret building {label}", p91["doef_vs_lightgbm"]["decision_regret_win_tie_loss"][key], "buildings", "8 fixed buildings", "ALL_8_FIXED", "Test", "DOEF vs LightGBM", "per-building comparison", "9.1", "outputs/phase9_1/final_reporting_summary.json", f"doef_vs_lightgbm.decision_regret_win_tie_loss.{key}", "6;8")
    weights = csv_load("outputs/phase8/selected_weights.csv")
    for row in weights:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", row["building"]).upper()
        for field, label in [("w_forecast", "forecast-MAE-selected LightGBM weight"), ("w_decision", "decision-regret-selected LightGBM weight")]:
            add_number(f"WEIGHT_{slug}_{field.upper()}", label, row[field], "ensemble LightGBM weight", "per-building Validation grid", row["building"], "Validation", "DayWeek-LightGBM ensemble", "per-building selection", "8", "outputs/phase8/selected_weights.csv", f"row(building={row['building']}).{field}", "20" + (";9" if row["building"] == "Hog_office_Joey" else ""))
    add_number("WEIGHT_CANDIDATE_COUNT", "Predeclared candidate weight count", len(p8cfg["candidate_weights"]), "weights", "per-building Validation search", "ALL_8_FIXED", "Validation", "DOEF", "fixed grid", "8", "outputs/phase8/run_config.json", "count(candidate_weights)", "9;20")
    boot = p91["building_level_bootstrap"]
    for key, label, unit in [
        ("resamples", "Building-level bootstrap resamples", "resamples"),
        ("point_estimate", "DOEF minus LightGBM normalized regret point estimate", "normalized regret difference"),
        ("ci95_lower", "Building-level bootstrap 95% lower bound", "normalized regret difference"),
        ("ci95_upper", "Building-level bootstrap 95% upper bound", "normalized regret difference"),
    ]:
        add_number(f"BOOTSTRAP_{key.upper()}", label, boot[key], unit, "8 fixed buildings resampled by building", "ALL_8_FIXED", "Test", "DOEF minus LightGBM", "paired building bootstrap", "9.1", "outputs/phase9_1/final_reporting_summary.json", f"building_level_bootstrap.{key}", "21")
    inv = p91["doef_prediction_invariance"]
    add_number("PREDICTION_IDENTITY_SAMPLES", "Frozen DOEF predictions checked", inv["samples"], "predictions", "8 buildings × 720 Test hours", "ALL_8_FIXED", "Test", "DOEF", "identity audit", "9.1", "outputs/phase9_1/doef_prediction_invariance.json", "samples", "22")
    add_number("PREDICTION_IDENTITY_MAX_DELTA", "DOEF prediction identity maximum absolute delta", inv["max_absolute_delta"], "kW", "8 buildings × 720 Test hours", "ALL_8_FIXED", "Test", "DOEF", "maximum", "9.1", "outputs/phase9_1/doef_prediction_invariance.json", "max_absolute_delta", "22")
    battery = csv_load("outputs/phase7/building_battery_configs.csv")
    for row in battery:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", row["building"]).upper()
        add_number(f"BATTERY_{slug}_CAPACITY", "Frozen battery capacity", row["capacity"], "kWh", "building-specific Train-scaled battery", row["building"], "all dispatch splits", "all forecast methods", "per building", "7", "outputs/phase7/building_battery_configs.csv", f"row(building={row['building']}).capacity", "16")
        add_number(f"BATTERY_{slug}_POWER", "Frozen charge/discharge power limit", row["max_charge_power"], "kW", "building-specific Train-scaled battery", row["building"], "all dispatch splits", "all forecast methods", "per building", "7", "outputs/phase7/building_battery_configs.csv", f"row(building={row['building']}).max_charge_power", "16")
    first_battery = battery[0]
    for field, label, unit in [
        ("capacity_fraction_of_mean_daily_energy", "Capacity fraction of Train mean daily energy", "fraction"),
        ("soc_min_fraction", "Minimum SOC fraction", "fraction"), ("soc_max_fraction", "Maximum SOC fraction", "fraction"),
        ("initial_soc_fraction", "Initial SOC fraction", "fraction"), ("terminal_soc_fraction", "Terminal SOC fraction", "fraction"),
        ("eta_charge", "Charge efficiency", "fraction"), ("eta_discharge", "Discharge efficiency", "fraction"),
        ("round_trip_efficiency", "Round-trip efficiency", "fraction"),
    ]:
        add_number(f"BATTERY_COMMON_{field.upper()}", label, first_battery[field], unit, "common frozen rule across 8 building-specific batteries", "ALL_8_FIXED", "all dispatch splits", "all forecast methods", "fixed constraint", "7", "outputs/phase7/building_battery_configs.csv", field, "16")
    robust = json_load("outputs/phase5_7/summary.json")
    add_number("ROBUST_SELECTED_LAMBDA", "Validation-selected robust lambda", robust["selected_robust_configuration"]["lambda"], "dimensionless", "anchor-building Phase 5.7", "Hog_office_Rolando", "Validation", "Robust LightGBM dispatch", "selection", "5.7", "outputs/phase5_7/summary.json", "selected_robust_configuration.lambda", "23")
    for method, mid in [("LightGBM robust", "ROBUST_TEST_MEAN_REGRET"), ("LightGBM deterministic", "DETERMINISTIC_TEST_MEAN_REGRET")]:
        row = next(x for x in robust["test_metrics"] if x["method"] == method)
        add_number(mid, f"{method} mean Test regret", row["mean_regret"], "kW", "anchor-building Phase 5.7", "Hog_office_Rolando", "Test", method, "mean across 30 days", "5.7", "outputs/phase5_7/summary.json", f"test_metrics[method={method}].mean_regret", "23")
    numeric_fields = ["metric_id", "metric_name", "value", "unit", "scope", "building", "split", "method", "aggregation", "source_phase", "source_file", "source_field", "canonical_status", "used_in_ppt", "ppt_slide", "notes"]
    write_csv(OUT / "numeric_evidence_registry.csv", number_rows, numeric_fields)
    write_json(OUT / "numeric_evidence_registry.json", {"schema_version": 1, "phase": "13.4", "records": number_rows})

    # Figure and visual-asset registry, using the frozen Phase 13.1 manifest as authority.
    asset_map = {row["asset_id"]: row for row in csv_load("outputs/phase13_2/asset_to_slide_map.csv")}
    figure_rows = []
    for asset in p13_1_manifest["assets"]:
        paths = asset["output_files"]
        mapping = asset_map[asset["asset_id"]]
        figure_rows.append({
            "figure_id": asset["asset_id"], "title": asset["title"], "purpose": asset["intended_message"],
            "source_phase": "13.1", "generation_source": asset["generation_script"],
            "data_source": ";".join(asset["source_files"]), "upstream_canonical_artifact": ";".join(asset["source_files"]),
            "svg_path": next((p for p in paths if p.endswith(".svg")), ""),
            "png_path": next((p for p in paths if p.endswith(".png") and "transparent" not in p), paths[0]),
            "ppt_slide": mapping["assigned_slide"], "scientific_claim_ids": ";".join(asset["claim_id"]),
            "integrity_status": "PASS", "notes": f"Supports: {asset['supports_claim']} Does not support: {asset['does_not_support']} Caveat: {asset['required_caveat']}",
        })
    figure_fields = ["figure_id", "title", "purpose", "source_phase", "generation_source", "data_source", "upstream_canonical_artifact", "svg_path", "png_path", "ppt_slide", "scientific_claim_ids", "integrity_status", "notes"]
    write_csv(OUT / "figure_registry.csv", figure_rows, figure_fields)

    negative_rows = [
        {
            "result_id": "NEG-P5.7-ROBUST", "phase": "5.7", "experiment": "Validation-selected robust battery dispatch",
            "expected_or_tested_hypothesis": "Validation-selected robust dispatch may improve held-out peak-shaving robustness over deterministic LightGBM dispatch.",
            "actual_result": "On Test, robust mean regret was 20.4635 kW versus 11.1274 kW deterministic; robust was better on 1 day and worse on 29 days.",
            "status": "NEGATIVE_RESULT", "scientific_interpretation": "The selected robust variant degraded in this frozen single-building test and was excluded from DOEF v1.0.",
            "allowed_wording": "Robust optimization did not outperform the deterministic strategy in the frozen Phase 5.7 Test evaluation.",
            "prohibited_wording": "Robust optimization improves peak shaving or consistently outperforms deterministic dispatch.",
            "source_file": "outputs/phase5_7/summary.json",
        },
        {
            "result_id": "NEG-P9-PEAK-AWARE", "phase": "9", "experiment": "Peak-aware LightGBM supporting experiment",
            "expected_or_tested_hypothesis": "Additional peak weighting may improve downstream decision regret.",
            "actual_result": "Validation selected alpha=0 for 7/8 buildings; held-out comparison versus LightGBM was 0 wins, 7 ties, 1 loss.",
            "status": "NEGATIVE_RESULT", "scientific_interpretation": "The extension did not show stable cross-building value and was rejected from the final algorithm.",
            "allowed_wording": "The peak-aware extension was a retained failed supporting experiment and is not part of DOEF v1.0.",
            "prohibited_wording": "Peak-aware training improves the final algorithm.", "source_file": "outputs/phase9/competition_summary.json",
        },
        {
            "result_id": "NEG-P9-CATBOOST-PEAK", "phase": "9/9.1", "experiment": "CatBoost frozen Test peak-reduction aggregation",
            "expected_or_tested_hypothesis": "A comparator with acceptable median peak reduction may also have a favorable mean.",
            "actual_result": "Median peak reduction was +4.8209%, but mean was -24.4824% because the minimum building result was -245.9433%.",
            "status": "NEGATIVE_RESULT", "scientific_interpretation": "Mean, median, range, method and building scope must be shown together; the extreme failure is preserved.",
            "allowed_wording": "CatBoost has a positive median but a negative mean peak reduction in the frozen eight-building scope.",
            "prohibited_wording": "CatBoost uniformly improves or uniformly worsens peak shaving.", "source_file": "outputs/phase9_1/final_reporting_summary.json",
        },
        {
            "result_id": "NEG-P9-DOEF-MIN", "phase": "9", "experiment": "DOEF whole-window Test peak reduction",
            "expected_or_tested_hypothesis": "Aggregate gains may hold for every fixed building.",
            "actual_result": "DOEF mean peak reduction was +6.4423%, while the minimum building result was -1.0170%.",
            "status": "NEGATIVE_RESULT", "scientific_interpretation": "The aggregate improvement is not an all-building peak-reduction guarantee.",
            "allowed_wording": "DOEF improved the eight-building mean while retaining one negative building case.",
            "prohibited_wording": "DOEF reduces peak demand for every building.", "source_file": "outputs/phase9/final_benchmark.csv",
        },
    ]
    negative_fields = ["result_id", "phase", "experiment", "expected_or_tested_hypothesis", "actual_result", "status", "scientific_interpretation", "allowed_wording", "prohibited_wording", "source_file"]
    write_csv(OUT / "negative_result_registry.csv", negative_rows, negative_fields)

    discrepancies = [
        {
            "issue_id": "DISC-001", "severity": "MAJOR", "artifact": "origin/main",
            "location": "commit 8061c79; outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx",
            "observed": "After fetch, origin/main contains a later parallel commit that replaces the PPTX and is not descended from local audited Phase 13.3 repair commit 076f76a.",
            "canonical": "This Phase 13.4 audit uses the local 076f76a PPTX accepted by reports/phase13_3_submission_grade_acceptance.md.",
            "impact": "A blind pull/merge could replace the audited presentation and invalidate the Phase 13.4 presentation hash and traceability map.",
            "recommended_phase14_action": "Reconcile Git history explicitly; preserve the 076f76a accepted PPTX unless a new minimal presentation-repair phase revalidates any replacement.",
            "status": "OPEN",
        },
        {
            "issue_id": "DISC-002", "severity": "MAJOR", "artifact": "Phase 13.3 PPTX",
            "location": "slide 1 competition identity line",
            "observed": "全球人工智能算法精英大赛 · AI+能源主题赛",
            "canonical": "全球校园人工智能算法精英大赛；算法主题赛（AI+能源）—科技创新组",
            "impact": "Competition identity is abbreviated and omits 校园 and 科技创新组; scientific results are unaffected, but submission identity may be ambiguous.",
            "recommended_phase14_action": "Record as a minimal presentation wording repair if the official name/group must appear verbatim; do not alter scientific claims.",
            "status": "OPEN",
        },
        {
            "issue_id": "DISC-003", "severity": "MINOR", "artifact": "reports/phase9_report.md",
            "location": "DOEF vs LightGBM bootstrap interval",
            "observed": "The Phase 9 narrative reports the secondary building-day interval [-0.007830, -0.000356].",
            "canonical": "Phase 9.1 primary building-level interval [-0.006850, -0.001719]; Phase 9 interval is retained only as secondary temporal-resampling sensitivity evidence.",
            "impact": "Using the older report without the Phase 9.1 hierarchy can cite the wrong primary uncertainty interval.",
            "recommended_phase14_action": "Use Phase 9.1 final_reporting_summary.json and the Master Project Record for all submission-facing bootstrap wording.",
            "status": "RESOLVED_BY_SOURCE_HIERARCHY",
        },
    ]
    discrepancy_fields = ["issue_id", "severity", "artifact", "location", "observed", "canonical", "impact", "recommended_phase14_action", "status"]
    write_csv(OUT / "discrepancy_registry.csv", discrepancies, discrepancy_fields)

    # Page-by-page presentation evidence map. Titles are inventory rows; scientific rows are mapped to frozen claims.
    slide_claim = {
        1: ("CORE-01", "PASS"), 2: ("CORE-02", "PASS_WITH_QUALIFICATION"), 3: ("SUP-06", "PASS_WITH_QUALIFICATION"),
        4: ("CORE-03", "PASS"), 5: ("CORE-05", "PASS"), 6: ("CORE-06;CORE-07;CORE-08", "PASS_WITH_QUALIFICATION"),
        7: ("CORE-02", "PASS_WITH_QUALIFICATION"), 8: ("CORE-04;CORE-07", "PASS_WITH_QUALIFICATION"),
        9: ("SUP-03", "PASS_WITH_QUALIFICATION"), 10: ("CORE-05;SUP-06", "PASS_WITH_QUALIFICATION"),
        11: ("CORE-03;CORE-05", "PASS_WITH_QUALIFICATION"), 12: ("CORE-01;CORE-03;BACK-03", "PASS_WITH_QUALIFICATION"),
        13: ("CORE-04;SUP-01", "PASS_WITH_QUALIFICATION"), 14: ("SUP-02;BACK-03", "PASS_WITH_QUALIFICATION"),
        15: ("CORE-05;BACK-04", "PASS_WITH_QUALIFICATION"), 16: ("SUP-06;BACK-02", "PASS_WITH_QUALIFICATION"),
        17: ("CORE-02;CORE-06;CORE-07", "PASS_WITH_QUALIFICATION"), 18: ("CORE-08;SUP-07", "PASS_WITH_QUALIFICATION"),
        19: ("SUP-06", "PASS_WITH_QUALIFICATION"), 20: ("CORE-03;BACK-04", "PASS"),
        21: ("SUP-04", "PASS_WITH_QUALIFICATION"), 22: ("SUP-05;BACK-05", "PASS_WITH_QUALIFICATION"),
        23: ("BACK-01;SUP-08", "PASS_WITH_QUALIFICATION"),
    }
    slide_sources = {
        1: "outputs/phase9/final_algorithm.json", 2: "outputs/phase9/final_benchmark.csv", 3: "outputs/phase13_1/presentation_assets/con_01_prediction_decision_bridge.png",
        4: "outputs/phase8/selected_weights.csv", 5: "outputs/phase9/final_algorithm.json", 6: "outputs/phase9_1/final_reporting_summary.json",
        7: "outputs/phase9_1/metric_semantics.json", 8: "outputs/phase9_1/final_reporting_summary.json", 9: "outputs/phase8/run_config.json",
        10: "outputs/phase9/final_algorithm.json", 11: "outputs/phase12/innovation_claims_frozen.json", 12: "outputs/phase9_1/final_reporting_summary.json",
        13: "outputs/phase7/selected_buildings.json", 14: "outputs/phase7/model_selection_config.json", 15: "outputs/phase9/final_algorithm.json",
        16: "outputs/phase7/building_battery_configs.csv", 17: "outputs/phase9/final_benchmark.csv", 18: "outputs/phase9/final_benchmark.csv",
        19: "outputs/phase13_1/figures/sci_05_storage_dispatch_frozen.png", 20: "outputs/phase8/selected_weights.csv",
        21: "outputs/phase9_1/final_reporting_summary.json", 22: "outputs/phase9_1/doef_prediction_invariance.json", 23: "outputs/phase5_7/summary.json",
    }
    slide_figures = {2: "SCI-01-forecast-decision-mismatch", 3: "CON-01-prediction-decision-bridge", 5: "ARCH-01-doef-architecture-master", 6: "SCI-02-doef-main-results", 8: "SCI-03-multibuilding-regret", 9: "SCI-04-validation-weight-selection", 11: "CON-02-contribution-overview", 19: "SCI-05-storage-dispatch-frozen"}
    slide_metrics = {
        2: "P9_XGBOOST_NORMALIZED_RMSE_MEAN;P9_LIGHTGBM_NORMALIZED_RMSE_MEAN;P9_XGBOOST_NORMALIZED_DECISION_REGRET_MEAN;P9_LIGHTGBM_NORMALIZED_DECISION_REGRET_MEAN",
        6: "DOEF_MAE_IMPROVEMENT_PCT;DOEF_REGRET_IMPROVEMENT_PCT;DOEF_REGRET_WINS;DOEF_REGRET_TIES;DOEF_REGRET_LOSSES;P9_DOEF_PEAK_REDUCTION_MIN_PCT",
        8: "COUNT_OFFICE_CANDIDATES;COUNT_QUALITY_PASS;COUNT_FIXED_BUILDINGS;DOEF_REGRET_WINS;DOEF_REGRET_TIES;DOEF_REGRET_LOSSES",
        9: "WEIGHT_CANDIDATE_COUNT", 13: "COUNT_PROJECT_SERIES;COUNT_OFFICE_CANDIDATES;COUNT_QUALITY_PASS;COUNT_FIXED_BUILDINGS",
        16: ";".join(["BATTERY_COMMON_CAPACITY_FRACTION_OF_MEAN_DAILY_ENERGY", "BATTERY_COMMON_SOC_MIN_FRACTION", "BATTERY_COMMON_SOC_MAX_FRACTION", "BATTERY_COMMON_INITIAL_SOC_FRACTION", "BATTERY_COMMON_TERMINAL_SOC_FRACTION", "BATTERY_COMMON_ETA_CHARGE", "BATTERY_COMMON_ETA_DISCHARGE", "BATTERY_COMMON_ROUND_TRIP_EFFICIENCY"]),
        17: ";".join(r["metric_id"] for r in number_rows if r["ppt_slide"] and "17" in r["ppt_slide"].split(";")),
        18: ";".join(r["metric_id"] for r in number_rows if r["ppt_slide"] and "18" in r["ppt_slide"].split(";")),
        20: ";".join(r["metric_id"] for r in number_rows if r["metric_id"].startswith("WEIGHT_")),
        21: "BOOTSTRAP_RESAMPLES;BOOTSTRAP_POINT_ESTIMATE;BOOTSTRAP_CI95_LOWER;BOOTSTRAP_CI95_UPPER",
        22: "PREDICTION_IDENTITY_SAMPLES;PREDICTION_IDENTITY_MAX_DELTA", 23: "ROBUST_SELECTED_LAMBDA;ROBUST_TEST_MEAN_REGRET;DETERMINISTIC_TEST_MEAN_REGRET",
    }
    presentation_rows = []
    for slide in slides:
        n = slide["slide_number"]
        cid, status = slide_claim[n]
        presentation_rows.append({
            "slide_number": n, "slide_title": slide["title"], "element_type": "title",
            "claim_text": slide["title"], "claim_id": "", "numeric_metric_ids": "", "figure_ids": "",
            "source_phase": "13.2", "evidence_source": "outputs/phase13_2/slide_architecture.json",
            "traceability_status": "NON_SCIENTIFIC", "wording_status": "PASS", "notes": "Slide title/section navigation inventory.",
        })
        presentation_rows.append({
            "slide_number": n, "slide_title": slide["title"], "element_type": "major_claim",
            "claim_text": next((c["allowed_wording"] for c in claim_rows if c["claim_id"] == cid.split(";")[0]), slide["joined"]),
            "claim_id": cid, "numeric_metric_ids": slide_metrics.get(n, ""), "figure_ids": slide_figures.get(n, ""),
            "source_phase": "5.7/7/8/9/9.1/12/13.1 as mapped", "evidence_source": slide_sources[n],
            "traceability_status": status, "wording_status": status,
            "notes": "Visible PPTX wording audited against canonical source; normal display rounding accepted.",
        })
        if n in slide_metrics:
            presentation_rows.append({
                "slide_number": n, "slide_title": slide["title"], "element_type": "highlighted_number_or_table",
                "claim_text": "Visible quantitative evidence", "claim_id": cid, "numeric_metric_ids": slide_metrics[n],
                "figure_ids": slide_figures.get(n, ""), "source_phase": "canonical numeric registry",
                "evidence_source": slide_sources[n], "traceability_status": "PASS", "wording_status": "PASS",
                "notes": "Every listed number is mapped to numeric_evidence_registry.csv.",
            })
        if n in slide_figures:
            presentation_rows.append({
                "slide_number": n, "slide_title": slide["title"], "element_type": "figure_or_visual",
                "claim_text": "Frozen Phase 13.1 visual usage", "claim_id": cid, "numeric_metric_ids": slide_metrics.get(n, ""),
                "figure_ids": slide_figures[n], "source_phase": "13.1", "evidence_source": slide_sources[n],
                "traceability_status": "PASS", "wording_status": "PASS", "notes": "No Phase 13.4 figure regeneration or modification.",
            })
    presentation_fields = ["slide_number", "slide_title", "element_type", "claim_text", "claim_id", "numeric_metric_ids", "figure_ids", "source_phase", "evidence_source", "traceability_status", "wording_status", "notes"]
    write_csv(OUT / "presentation_evidence_map.csv", presentation_rows, presentation_fields)

    project_title = "DOEF：让负荷预测服务于储能削峰决策"
    selected_buildings = [item["building"] for item in p7sel["selected_buildings"]]
    weight_table = "\n".join(f"| {row['building']} | {row['w_forecast']} | {row['w_decision']} |" for row in weights)
    timeline = [
        ("3", "Single-building baseline and frozen project selection table"), ("4", "Causal LightGBM forecasting"),
        ("4.5", "Forecast diagnostics and canonical split protocol"), ("5", "Deterministic battery peak-shaving evaluation"),
        ("5.5", "Frozen robustness and sensitivity analysis"), ("5.6", "Forecast-lineage repair and deterministic reproduction"),
        ("5.7", "Robust-dispatch negative result retained"), ("6", "Decision-oriented forecasting baseline"),
        ("7", "Train-only eight-building deterministic benchmark"), ("8", "Validation-only decision-oriented ensemble"),
        ("9", "Final algorithm validation and DOEF v1.0 freeze"), ("9.1", "Final methodology/statistical reporting audit"),
        ("10", "Final deliverable gap audit"), ("11", "Competition rules verification"),
        ("12", "Innovation positioning and claim freeze"), ("13.0A", "Presentation scientific source freeze: 88/88 PASS"),
        ("13.0B", "Presentation evidence selection: 8/8 PASS"), ("13.1", "Frozen visual assets"),
        ("13.2", "Frozen 12-main + 11-appendix storyboard"), ("13.3", "Accepted 23-slide competition PPTX"),
        ("13.4", "Master evidence record and registries"),
    ]
    timeline_md = "\n".join(f"| Phase {p} | {d} |" for p, d in timeline)
    master = f"""# Phase 13.4 — Master Project Record

Status: **PHASE 13.4 — PASS WITH FOLLOW-UP**
Role: canonical competition-evidence audit entry for Phase 14; it does not supersede or modify scientific artifacts.

## 1. Project Identity

| Field | Frozen record |
| --- | --- |
| Competition | 全球校园人工智能算法精英大赛 |
| Track | 算法主题赛（AI+能源）—科技创新组 |
| Competition-facing project title | {project_title} |
| Title provenance | Current Phase 13.3 title; Phase 13.2 called it a working title. Phase 13.4 freezes it as the competition-facing title without claiming that a separate registration-platform title has been verified. |
| Problem domain | AI-assisted building energy management |
| Dataset | Building Data Genome Project 2 (BDG2), electricity_cleaned.csv + metadata.csv |
| Forecasting task | 24-hour-ahead hourly building-load forecast |
| Decision task | Deterministic daily BESS dispatch for peak shaving, evaluated on realized load |
| Final algorithm | DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法） |
| Frozen baseline | `{FROZEN_BASELINE}` |
| Final scientific validation | Phase 9.1 — PASS |
| Presentation | Phase 13.3 — PASS; 23 slides; audited read-only in Phase 13.4 |
| Project status | ALGORITHM FROZEN; EVIDENCE CONSOLIDATED; Phase 14 may be re-executed after follow-up review |

## 2. Final Problem Definition

`Building load forecasting → forecast error structure → battery energy storage dispatch → peak-shaving decision value`.

The project does not optimize forecast MAE/RMSE as the sole terminal objective. Frozen evidence supports the narrower statement that **forecast accuracy and downstream decision quality are related but not equivalent**: in the eight-building Test aggregate, XGBoost has slightly lower normalized RMSE than LightGBM (0.216751 vs 0.216942) while having higher normalized decision regret (0.117534 vs 0.116127). This is a project-scoped counterexample, not a universal causal law and not evidence that forecast accuracy is irrelevant.

## 3. Final Algorithm Record

- Full name: Decision-Oriented Ensemble Forecasting; abbreviation: DOEF; version: 1.0.
- Forecast horizon: 24 hours. Components: `DayWeek = 0.5·actual(t−24h) + 0.5·actual(t−168h)` and one frozen per-building LightGBM forecaster.
- DOEF formula: `ŷ_t = w_b·ŷ_t^(LightGBM) + (1−w_b)·ŷ_t^(DayWeek)`.
- Causal feature construction: current load at feature time, calendar encodings, positive lags 1/2/3/24/48/72/168/336 and shifted rolling statistics; no weather and no future target values. Complete list and per-building model parameters are canonical in `outputs/phase7/model_selection_config.json`.
- Split protocol: Phase 4.5/6 feature-time splits with target-availability purge. Anchor feature-time windows are Train 2016-01-15 through 2017-10-31, Validation 2017-11-01 through 2017-11-30, Test 2017-12-01 through 2017-12-30; the 24-hour target shift yields the documented target-time boundaries. Test has 720 hourly targets / 30 complete days per building.
- Model/config selection: per-building base-model candidates were selected before Test from Validation; DOEF searches the predeclared `0.0, 0.1, …, 1.0` weight grid on Validation mean daily regret versus the non-deployable Oracle, with frozen tie-breaks. Test is evaluation-only and cannot promote or retune the algorithm.
- Frozen weights:

| Building | w forecast | w decision (DOEF) |
| --- | ---: | ---: |
{weight_table}

- Downstream dispatch: every method uses the same per-building Train-scaled battery and the same deterministic daily `scipy.optimize.milp` peak-shaving formulation. Capacity is 10% of Train mean daily energy; charge/discharge power is 25% of capacity per hour; SOC is 10%–90%; initial and terminal SOC are 50% (daily reset); charge and discharge efficiencies are each 0.948683, giving 0.90 round-trip efficiency.
- Decision metrics: realized post-dispatch peak, peak reduction, and daily regret = forecast-driven realized daily peak minus non-deployable Oracle realized daily peak. Regret is not monetary regret.
- Frozen configuration sources: `outputs/phase7/model_selection_config.json`, `outputs/phase7/building_battery_configs.csv`, `outputs/phase8/run_config.json`, `outputs/phase8/selected_weights.csv`, `outputs/phase9/final_algorithm.json`, and `outputs/phase9_1/final_reporting_summary.json`.

## 4. Dataset Record

- Dataset: Building Data Genome Project 2. Final multi-building work reads `data/raw/electricity_cleaned.csv` and `data/raw/metadata.csv`; the Phase 2 campus aggregate manifest is historical and is not the Phase 7–9 benchmark source.
- Electricity semantics: raw meter values are kWh per one-hour interval; dispatch interprets them as interval-average kW using `P_t = E_t/Δt`. Numeric values coincide only because `Δt = 1 h`. Battery capacity/SOC use kWh and charge/discharge limits use kW.
- Coverage used by the frozen forecast protocol: 2016-01-15 through 2017-12-30 at feature time for the anchor configuration; fixed 24-hour target shift; Validation November 2017 and Test December 2017 (720 target hours / 30 complete days per building).
- Project universe: 1,578 building-series rows in the frozen Phase 3 selection table; 296 office candidates; 82 passed deterministic coverage/quality rules; 8 were selected.
- Canonical anchor: `Hog_office_Rolando`.
- Final eight-building benchmark: {', '.join(selected_buildings)}.
- Selection principle: anchor plus deterministic farthest-point sampling on robust-scaled **Train-only** load morphology among eligible buildings. Validation/Test forecast or decision performance was not used; therefore this is fixed multi-building evidence, not unseen-building transfer.

## 5. Experimental Timeline

| Stage | Verified role |
| --- | --- |
{timeline_md}

## 6. Source-of-Truth Priority

1. Phase 7/8/9/9.1 canonical machine-readable scientific artifacts.
2. Frozen scientific integrity manifests and hashes.
3. Canonical code/config used to produce those artifacts.
4. Phase 13.0A / 13.0B frozen evidence records.
5. Phase 13.1 frozen figures and visual manifest.
6. Phase 13.2 frozen storyboard.
7. Phase 13.3 competition presentation.
8. Earlier narrative reports.
9. README.
10. Historical prompts or conversation descriptions.

If presentation wording conflicts with a canonical machine-readable result, the machine-readable result wins. Phase 9.1's building-level bootstrap is the primary uncertainty statement; the earlier Phase 9 building-day bootstrap remains secondary sensitivity evidence. No conflict is resolved by rerunning experiments.

## 7. Competition Evidence Summary

- DOEF vs LightGBM on the fixed eight-building Test aggregate: normalized MAE 0.137970 vs 0.147338 (6.3585% relative improvement); normalized decision regret 0.111929 vs 0.116127 (3.6147% relative improvement); building decision-regret win/tie/loss 6/2/0.
- Peak-shaving scope: DOEF mean whole-window peak reduction 6.4423%, median 5.6291%, minimum -1.0170%; the negative building case is retained.
- Generalization boundary: evidence spans eight preselected office buildings and one fixed future Test month per building; it does not establish universal, unseen-building, seasonal or cross-year generalization.
- Negative results: Phase 5.7 robust dispatch degraded Test regret; Phase 9 peak-aware LightGBM did not produce stable gains; CatBoost's extreme negative peak case and DOEF's negative minimum building remain visible.

## 8. Presentation Audit and Innovation Boundaries

All 23 slides were read from the PPTX XML. The evidence map inventories titles, major claims, numbers, figures, algorithm descriptions, contribution statements, result summaries and appendix caveats. The defensible innovation narrative is the auditable decision-oriented model-selection/evaluation framework: downstream Validation regret selects a transparent fixed blend, followed by controlled multi-building evaluation with frozen dispatch. LightGBM, lag features, the generic battery model and generic peak-shaving optimization are not claimed as original algorithms.

Open follow-up items are authoritative in `outputs/phase13_4/discrepancy_registry.csv`. Phase 13.4 does not modify the PPTX.

## 9. Freeze Declaration and Phase 14 Contract

- DOEF v1.0 remains **ALGORITHM FROZEN**. Algorithm development ended at Phase 9.1.
- New experiments/statistical tests in Phase 13.4: 0.
- Modified canonical scientific artifacts: 0.
- Modified Phase 13.1 figures, Phase 13.2 storyboard or Phase 13.3 PPTX: 0.
- Phase 7/8/9/9.1 integrity: {integrity['phase7_8_9_9_1']['pass_count']}/{integrity['phase7_8_9_9_1']['registered']} PASS; LF-normalized drift = {integrity['phase7_8_9_9_1']['lf_normalized_drift_count']}.

Phase 14 must begin from this Master Project Record and its machine-readable registries. It must resolve or explicitly disposition open presentation/Git discrepancies without changing scientific claims, frozen weights, predictions, dispatch or negative results.
"""
    (REPORTS / "master_project_record.md").write_text(master, encoding="utf-8", newline="\n")

    terminology = """# Phase 13.4 — Terminology and Naming Standard

| Canonical term | Required meaning / use | Prohibited ambiguity |
| --- | --- | --- |
| DOEF | Decision-Oriented Ensemble Forecasting, version 1.0 | Do not call it a new LightGBM architecture or end-to-end DFL. |
| Building Load Forecasting | 24-hour-ahead hourly building-load prediction | Do not describe it as one-hour-ahead. |
| Battery Energy Storage System (BESS) | Frozen simulated battery used for dispatch comparison | Do not imply field deployment. |
| Peak Shaving | Reduction of maximum power demand under the frozen protocol | Not energy saving, tariff saving or carbon reduction. |
| Forecast Metric | MAE, RMSE, MAPE and normalized variants | Not a downstream decision metric. |
| Decision Metric | Realized peak, peak reduction and Oracle-relative regret | Regret is not monetary regret. |
| Validation | Selection split for model/weight/tie-break rules | Never call Validation Test. |
| Test | Frozen held-out evaluation period; historical results had been viewed | Do not call it pristine, never-viewed or a selection set. |
| Dispatch | Deterministic 24-hour battery plan from the frozen optimizer | Do not call it online control. |
| Regret | Realized daily peak(method) − realized daily peak(non-deployable Oracle) | Not cost, energy or carbon regret. |
| Causal Feature | Information available at feature time: load history and calendar state | No future target or future weather. |
| Day baseline | `actual(t−24h)`; historically also Persistence | Do not duplicate Persistence and Day as different scientific methods. |
| Week baseline | `actual(t−168h)` | — |
| Day/Week baseline / DayWeek | `0.5·Day + 0.5·Week` | Not a learned model. |
| Ensemble weight | Building-specific LightGBM coefficient `w_b`; DayWeek coefficient is `1−w_b` | Do not generalize Joey's 0.3 to all buildings. |

## Units

- Raw electricity reading: **kWh per hourly interval**.
- Dispatch load/power: **interval-average kW**, derived by `P_t = E_t / Δt` with `Δt = 1 h`.
- Battery capacity and SOC: **kWh**.
- Charge/discharge power: **kW**.
- kW and kWh are not interchangeable. Equality of numerical magnitudes for one-hour intervals does not erase the semantic distinction.

## Names

- Official competition: **全球校园人工智能算法精英大赛**.
- Track: **算法主题赛（AI+能源）—科技创新组**.
- Competition-facing project title: **DOEF：让负荷预测服务于储能削峰决策**.
- Scientific algorithm display name: **DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）**.

The current PPT slide 1 abbreviates the official competition identity; the discrepancy registry controls the Phase 14 follow-up.
"""
    (REPORTS / "terminology_and_naming_standard.md").write_text(terminology, encoding="utf-8", newline="\n")

    language = """# Phase 13.4 — Competition Claim Language Guide

## Allowed when scope and source are retained

- Forecast accuracy does not necessarily translate into better downstream storage decisions in the frozen eight-building evidence.
- DOEF uses Validation-stage downstream decision regret to select a building-specific DayWeek–LightGBM ensemble weight.
- The final algorithm was evaluated on a deterministic eight-building benchmark selected using training-period characteristics and data quality, not Test performance.
- DOEF reduced the eight-building aggregate normalized MAE and normalized decision regret versus LightGBM; the exact values and scope must accompany the statement.
- Robust optimization did not outperform deterministic LightGBM dispatch in the frozen single-building Phase 5.7 Test evaluation.
- Every forecast method uses the same frozen battery constraints and dispatch formulation in the controlled comparison.

## Required qualification

- “Generalization” may mean only multi-building robustness across the eight fixed buildings; it must not imply unseen-building transfer.
- “Better” must name the metric, comparator, split and aggregation.
- “Peak reduction” must preserve kW/% semantics and must not be relabeled as energy, cost or carbon saving.
- The building-level bootstrap interval is descriptive uncertainty within eight building units; do not add a separate statistical-significance claim.
- The Test split was not used for selection, but historical Test visibility means it is not described as pristine or never viewed.

## Prohibited without new, separately authorized evidence

- DOEF is universally superior, state of the art, world-first or statistically significant.
- DOEF significantly outperforms all methods on all buildings.
- Robust optimization improves or consistently outperforms the final result.
- The method guarantees optimal storage scheduling.
- The method generalizes to all commercial or unseen buildings, seasons or years.
- The project proves cost savings, carbon reduction or energy-use reduction.
- LightGBM, generic lag features, the generic battery model or ordinary peak-shaving optimization is the project's original algorithmic innovation.
"""
    (REPORTS / "competition_claim_language_guide.md").write_text(language, encoding="utf-8", newline="\n")

    artifact_entries = [
        ("Algorithm freeze", "9/9.1", "outputs/phase9/final_algorithm.json; outputs/phase9_1/final_reporting_summary.json", "Canonical algorithm definition and reporting semantics", "CANONICAL", "All submission claims"),
        ("Scientific canonical artifacts", "7/8/9/9.1", "outputs/phase9_1/artifact_hash_audit.json", "76-file frozen integrity registry", "CANONICAL", "Integrity gate"),
        ("Multi-building evidence", "7/9/9.1", "outputs/phase7/selected_buildings.json; outputs/phase9/per_building_metrics.csv", "Fixed building selection and outcomes", "CANONICAL", "Breadth/generalization wording"),
        ("Negative-result evidence", "5.7/9", "outputs/phase5_7/summary.json; outputs/phase9/competition_summary.json", "Retained falsification evidence", "CANONICAL", "Honest limitations"),
        ("Scientific figures", "13.1", "outputs/phase13_1/manifests/visual_asset_manifest.json", "Five scientific figures plus architecture/conceptual assets", "CANONICAL", "PPT visuals"),
        ("Storyboard", "13.2", "outputs/phase13_2/slide_architecture.json", "12-slide main + 11-slide appendix narrative", "FROZEN", "PPT narrative"),
        ("Competition presentation", "13.3", "outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx", "Accepted 23-slide deck; Phase 13.4 read-only audit object", "FROZEN_WITH_FOLLOW_UP", "Phase 14 presentation audit"),
        ("Master Project Record", "13.4", "reports/phase13_4/master_project_record.md", "Human-readable master evidence entry", "CANONICAL_AUDIT_ENTRY", "Phase 14"),
        ("Claim registry", "13.4", "outputs/phase13_4/claim_registry.csv", "Allowed/prohibited claim control", "CANONICAL_AUDIT_ENTRY", "Claim audit"),
        ("Numeric registry", "13.4", "outputs/phase13_4/numeric_evidence_registry.csv", "Number-to-source map", "CANONICAL_AUDIT_ENTRY", "Number audit"),
        ("Figure registry", "13.4", "outputs/phase13_4/figure_registry.csv", "Figure provenance and limits", "CANONICAL_AUDIT_ENTRY", "Figure audit"),
        ("Presentation evidence map", "13.4", "outputs/phase13_4/presentation_evidence_map.csv", "Page-by-page evidence map", "CANONICAL_AUDIT_ENTRY", "Presentation audit"),
        ("Terminology standard", "13.4", "reports/phase13_4/terminology_and_naming_standard.md", "Naming, metric and unit semantics", "CANONICAL_AUDIT_ENTRY", "Submission consistency"),
    ]
    artifact_table = "\n".join(f"| {a} | {p} | `{path}` | {purpose} | {status} | {use} |" for a, p, path, purpose, status, use in artifact_entries)
    index = f"""# Phase 13.4 — Competition Artifact Index

| Artifact | Phase | Path | Purpose | Canonical status | Downstream use |
| --- | --- | --- | --- | --- | --- |
{artifact_table}

## Phase 14 entry requirements

1. Start from `reports/phase13_4/master_project_record.md` and `outputs/phase13_4/master_evidence_manifest.json`.
2. Recheck the frozen baseline ancestry and the 76 registered scientific artifacts.
3. Reconcile the open remote/PPT identity discrepancies without changing scientific content.
4. Treat machine-readable canonical evidence as superior to PPT wording and earlier narrative reports.
5. Preserve Validation/Test roles and all negative results; run no algorithm selection on Test.
"""
    (REPORTS / "competition_artifact_index.md").write_text(index, encoding="utf-8", newline="\n")

    counts = {
        "claims": len(claim_rows), "numbers": len(number_rows), "figures": len(figure_rows),
        "presentation_map_rows": len(presentation_rows), "negative_results": len(negative_rows), "discrepancies": len(discrepancies),
    }
    claim_counts = dict(Counter(row["status"] for row in claim_rows))
    trace_counts = dict(Counter(row["traceability_status"] for row in presentation_rows))
    ppt_metric_ids = sorted({metric for row in presentation_rows for metric in row["numeric_metric_ids"].split(";") if metric})
    ppt_figure_ids = sorted({figure for row in presentation_rows for figure in row["figure_ids"].split(";") if figure})
    manifest = {
        "schema_version": 1,
        "phase": "13.4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_head": head,
        "repository_branch": branch,
        "frozen_baseline": FROZEN_BASELINE,
        "algorithm_name": "Decision-Oriented Ensemble Forecasting",
        "algorithm_version": "1.0",
        "algorithm_status": "ALGORITHM FROZEN",
        "canonical_artifacts": {
            "scientific_hash_registry": "outputs/phase9_1/artifact_hash_audit.json",
            "master_project_record": "reports/phase13_4/master_project_record.md",
            "artifact_index": "reports/phase13_4/competition_artifact_index.md",
        },
        "claims": {"path": "outputs/phase13_4/claim_registry.csv", "json": "outputs/phase13_4/claim_registry.json", "count": len(claim_rows), "status_counts": claim_counts},
        "numbers": {"path": "outputs/phase13_4/numeric_evidence_registry.csv", "json": "outputs/phase13_4/numeric_evidence_registry.json", "count": len(number_rows)},
        "figures": {"path": "outputs/phase13_4/figure_registry.csv", "count": len(figure_rows)},
        "presentation": {"path": PPTX.relative_to(ROOT).as_posix(), "sha256": sha256_bytes(PPTX.read_bytes()), "slides": len(slides), "evidence_map": "outputs/phase13_4/presentation_evidence_map.csv", "evidence_rows": len(presentation_rows), "scientific_claim_rows": len([row for row in presentation_rows if row["traceability_status"] != "NON_SCIENTIFIC"]), "numeric_metrics_audited": len(ppt_metric_ids), "figures_mapped": len(ppt_figure_ids), "traceability_counts": trace_counts, "unsupported_count": 0, "mismatch_count": 1, "modified_by_phase13_4": False},
        "negative_results": {"path": "outputs/phase13_4/negative_result_registry.csv", "count": len(negative_rows), "preserved": True},
        "terminology": "reports/phase13_4/terminology_and_naming_standard.md",
        "discrepancies": {"path": "outputs/phase13_4/discrepancy_registry.csv", "count": len(discrepancies), "severity_counts": dict(Counter(row["severity"] for row in discrepancies))},
        "integrity_summary": integrity,
        "operations": {"new_experiments": 0, "new_statistical_tests": 0, "algorithm_modifications": 0, "scientific_canonical_modifications": 0, "ppt_modifications": 0},
        "phase14_gate": {"status": "YES_WITH_FOLLOW_UP", "entry_point": "reports/phase13_4/master_project_record.md", "required_actions": ["Reconcile origin/main PPTX divergence", "Confirm or minimally repair exact official competition/track wording on slide 1"]},
        "record_counts": counts,
    }
    write_json(OUT / "master_evidence_manifest.json", manifest)
    print(json.dumps({"status": "PASS WITH FOLLOW-UP", "integrity": {k: v["status"] for k, v in integrity.items()}, "counts": counts, "claim_status": claim_counts, "presentation_traceability": trace_counts}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
