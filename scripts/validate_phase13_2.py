"""Read-only scientific-integrity and traceability validation for Phase 13.2.

The only file written is outputs/phase13_2/validation_report.json. No model,
forecast, optimizer, experiment, or frozen presentation asset is executed or
modified.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_2"
ARCHITECTURE = OUT / "slide_architecture.json"
CLAIM_MAP = OUT / "claim_to_slide_map.csv"
ASSET_MAP = OUT / "asset_to_slide_map.csv"
TRACEABILITY = OUT / "evidence_traceability.csv"
REPORT = OUT / "validation_report.json"

STARTING_HEAD = "d36fcd18568b98a5980b101e213f714ddf332f12"
FROZEN_ALGORITHM_COMMIT = "549abc314e93e2862bfc22965db89622c22890e1"
PHASE13_1_COMMIT = "d36fcd18568b98a5980b101e213f714ddf332f12"
TEXT_EXTENSIONS = {".json", ".csv", ".txt", ".md", ".py", ".yml", ".yaml", ".toml", ".html", ".svg"}

REQUIRED_SLIDE_FIELDS = {
    "slide_id", "section", "slide_role", "core_question", "single_takeaway",
    "headline", "supporting_copy", "claim_ids", "evidence_ids", "visual_asset_ids",
    "visual_asset_paths", "primary_metric_or_fact", "speaker_intent", "transition_from",
    "transition_to", "main_or_appendix", "must_not_claim", "design_notes_for_next_phase",
}


def run_git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def normalized_bytes(data: bytes, rel: str) -> bytes:
    if Path(rel).suffix.lower() in TEXT_EXTENSIONS:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(commit: str, rel: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"{commit}:{rel}"], cwd=ROOT)


def audit_paths_against_commit(paths: list[str], commit: str, label: str) -> dict[str, Any]:
    missing: list[str] = []
    drift: list[str] = []
    newline_only: list[str] = []
    for rel in paths:
        current_path = ROOT / rel
        if not current_path.is_file():
            missing.append(rel)
            continue
        current_raw = current_path.read_bytes()
        frozen_raw = git_blob(commit, rel)
        if sha256(normalized_bytes(current_raw, rel)) != sha256(normalized_bytes(frozen_raw, rel)):
            drift.append(rel)
        elif sha256(current_raw) != sha256(frozen_raw):
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


def audit_phase13_0b() -> dict[str, Any]:
    summary = json.loads((ROOT / "outputs/phase13_0b/phase13_0b_summary.json").read_text(encoding="utf-8"))
    missing: list[str] = []
    drift: list[str] = []
    for item in summary["artifacts"]:
        rel = item["path"]
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        actual = sha256(normalized_bytes(path.read_bytes(), rel))
        if actual != item["sha256"]:
            drift.append(rel)
    count = len(summary["artifacts"])
    return {
        "label": "Phase 13.0B registered presentation-evidence artifacts",
        "registered": count,
        "pass_count": count - len(missing) - len(drift),
        "missing_count": len(missing),
        "lf_normalized_drift_count": len(drift),
        "newline_only_checkout_difference_count": 0,
        "missing": missing,
        "drift": drift,
        "status": "PASS" if not missing and not drift else "FAIL",
    }


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def readme_phase13_1_section(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"(?ms)^## Phase 13\.1\b.*?(?=^## |\Z)", normalized)
    return match.group(0).rstrip() if match else ""


def numeric_value(value: str) -> float:
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?", value)
    if not match:
        raise ValueError(f"no numeric value in {value!r}")
    return float(match.group(0).replace(",", ""))


def main() -> None:
    errors: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    architecture = json.loads(ARCHITECTURE.read_text(encoding="utf-8"))
    claim_rows = rows(CLAIM_MAP)
    asset_rows = rows(ASSET_MAP)
    trace_rows = rows(TRACEABILITY)
    claim_registry = json.loads((ROOT / "outputs/phase13_0b/final_presentation_claims.json").read_text(encoding="utf-8"))
    asset_manifest = json.loads((ROOT / "outputs/phase13_1/manifests/visual_asset_manifest.json").read_text(encoding="utf-8"))
    metric_rows = rows(ROOT / "outputs/phase13_0b/presentation_metric_shortlist.csv")

    approved_claims = {
        item["claim_id"]: item
        for item in claim_registry["claims"]
        if item.get("presentation_safe") is True
    }
    rejected_claims = {
        item["claim_id"] for item in claim_registry["claims"]
        if item.get("presentation_safe") is not True
    }
    asset_registry = {item["asset_id"]: item for item in asset_manifest["assets"]}
    metric_registry = {item["metric_shortlist_id"]: item for item in metric_rows}

    slides = architecture["slides"]
    slide_by_id = {slide["slide_id"]: slide for slide in slides}
    slide_ids = [slide["slide_id"] for slide in slides]
    main_slides = [slide for slide in slides if slide["main_or_appendix"] == "MAIN"]
    appendix_slides = [slide for slide in slides if slide["main_or_appendix"] == "APPENDIX"]

    schema_errors: list[str] = []
    for slide in slides:
        missing = sorted(REQUIRED_SLIDE_FIELDS - set(slide))
        if missing:
            schema_errors.append(f"{slide.get('slide_id', '<unknown>')}: missing {missing}")
    if architecture.get("status") != "canonical":
        schema_errors.append("slide_architecture status is not canonical")
    checks["slide_schema"] = {"status": "PASS" if not schema_errors else "FAIL", "errors": schema_errors}
    errors.extend(schema_errors)

    duplicate_ids = sorted({sid for sid in slide_ids if slide_ids.count(sid) > 1})
    checks["slide_ids_unique"] = {
        "status": "PASS" if not duplicate_ids else "FAIL",
        "slide_count": len(slides), "duplicates": duplicate_ids,
    }
    if duplicate_ids:
        errors.append(f"duplicate slide IDs: {duplicate_ids}")

    main_order = [slide["slide_id"] for slide in main_slides]
    appendix_order = [slide["slide_id"] for slide in appendix_slides]
    deterministic = main_order == architecture["main_deck_order"] and appendix_order == architecture["appendix_order"]
    checks["main_deck_order_deterministic"] = {
        "status": "PASS" if deterministic else "FAIL",
        "main_count": len(main_order), "appendix_count": len(appendix_order),
        "main_order": main_order, "appendix_order": appendix_order,
    }
    if not deterministic:
        errors.append("slide arrays do not match declared deterministic order")

    takeaway_errors = [
        slide["slide_id"] for slide in main_slides
        if not isinstance(slide.get("single_takeaway"), str) or not slide["single_takeaway"].strip()
    ]
    checks["one_slide_one_takeaway"] = {
        "status": "PASS" if not takeaway_errors else "FAIL",
        "main_slides_checked": len(main_slides), "failures": takeaway_errors,
    }
    if takeaway_errors:
        errors.append(f"main slides without exactly one string takeaway: {takeaway_errors}")

    unsupported: list[dict[str, str]] = []
    rejected_used: list[dict[str, str]] = []
    for slide in main_slides:
        for claim_id in slide["claim_ids"]:
            if claim_id in rejected_claims:
                rejected_used.append({"slide_id": slide["slide_id"], "claim_id": claim_id})
            elif claim_id not in approved_claims:
                unsupported.append({"slide_id": slide["slide_id"], "claim_id": claim_id})
    checks["approved_main_claims_only"] = {
        "status": "PASS" if not unsupported and not rejected_used else "FAIL",
        "unsupported_main_deck_claim_count": len(unsupported),
        "rejected_claims_used_count": len(rejected_used),
        "unsupported": unsupported, "rejected_used": rejected_used,
    }
    if unsupported or rejected_used:
        errors.append("main deck contains unsupported or rejected claim IDs")

    main_caveat_errors = [slide["slide_id"] for slide in main_slides if not slide.get("must_not_claim")]
    checks["must_not_claim_populated"] = {
        "status": "PASS" if not main_caveat_errors else "FAIL",
        "main_slides_checked": len(main_slides), "failures": main_caveat_errors,
    }
    if main_caveat_errors:
        errors.append(f"main slides without must_not_claim: {main_caveat_errors}")

    referenced_paths = sorted({path for slide in slides for path in slide["visual_asset_paths"]})
    missing_paths = [path for path in referenced_paths if not (ROOT / path).is_file()]
    unknown_asset_ids = sorted({aid for slide in slides for aid in slide["visual_asset_ids"] if aid not in asset_registry})
    checks["referenced_assets_exist"] = {
        "status": "PASS" if not missing_paths and not unknown_asset_ids else "FAIL",
        "referenced_path_count": len(referenced_paths), "missing_paths": missing_paths,
        "unknown_phase13_1_asset_ids": unknown_asset_ids,
    }
    if missing_paths or unknown_asset_ids:
        errors.append("one or more referenced visual assets are missing or unknown")

    mapped_asset_ids = [item["asset_id"] for item in asset_rows]
    missing_allocations = sorted(set(asset_registry) - set(mapped_asset_ids))
    duplicate_allocations = sorted({aid for aid in mapped_asset_ids if mapped_asset_ids.count(aid) > 1})
    map_missing_paths = [item["asset_path"] for item in asset_rows if not (ROOT / item["asset_path"]).is_file()]
    bad_modification_rules = [item["asset_id"] for item in asset_rows if item["modification_allowed"] != "NO"]
    checks["phase13_1_asset_allocation"] = {
        "status": "PASS" if not missing_allocations and not duplicate_allocations and not map_missing_paths and not bad_modification_rules else "FAIL",
        "manifest_asset_count": len(asset_registry), "mapped_asset_count": len(mapped_asset_ids),
        "missing_allocations": missing_allocations, "duplicate_allocations": duplicate_allocations,
        "missing_paths": map_missing_paths, "modification_rule_failures": bad_modification_rules,
    }
    if any((missing_allocations, duplicate_allocations, map_missing_paths, bad_modification_rules)):
        errors.append("Phase 13.1 asset allocation is incomplete or unsafe")

    mapped_claim_ids = [item["claim_id"] for item in claim_rows]
    claim_map_missing = sorted(set(approved_claims) - set(mapped_claim_ids))
    claim_map_extra = sorted(set(mapped_claim_ids) - set(approved_claims))
    claim_map_duplicates = sorted({cid for cid in mapped_claim_ids if mapped_claim_ids.count(cid) > 1})
    checks["claim_map_coverage"] = {
        "status": "PASS" if not claim_map_missing and not claim_map_extra and not claim_map_duplicates else "FAIL",
        "approved_claim_count": len(approved_claims), "mapped_claim_count": len(mapped_claim_ids),
        "missing": claim_map_missing, "extra": claim_map_extra, "duplicates": claim_map_duplicates,
    }
    if any((claim_map_missing, claim_map_extra, claim_map_duplicates)):
        errors.append("claim-to-slide map does not exactly cover approved claims")

    trace_keys = [item["traceability_key"] for item in trace_rows]
    duplicate_trace_keys = sorted({key for key in trace_keys if trace_keys.count(key) > 1})
    fact_pairs = {
        (slide["slide_id"], fact["traceability_key"])
        for slide in slides for fact in slide["primary_metric_or_fact"]
    }
    trace_pairs = {(item["slide_id"], item["traceability_key"]) for item in trace_rows}
    missing_trace = sorted(fact_pairs - trace_pairs)
    extra_trace = sorted(trace_pairs - fact_pairs)
    trace_errors: list[str] = []
    for item in trace_rows:
        slide = slide_by_id.get(item["slide_id"])
        if slide is None:
            trace_errors.append(f"unknown slide: {item['slide_id']}")
            continue
        if item["claim_id"] not in slide["claim_ids"]:
            trace_errors.append(f"{item['traceability_key']}: claim not attached to slide")
        if item["verification_status"] != "VERIFIED":
            trace_errors.append(f"{item['traceability_key']}: not VERIFIED")
        source = ROOT / item["source_file"]
        if not source.is_file():
            trace_errors.append(f"{item['traceability_key']}: source missing")
        if not item["source_location"].strip():
            trace_errors.append(f"{item['traceability_key']}: source location empty")
        metric_id = item["metric_id"].strip()
        if metric_id:
            metric = metric_registry.get(metric_id)
            if metric is None:
                trace_errors.append(f"{item['traceability_key']}: unknown metric {metric_id}")
                continue
            if metric["source_path"] != item["source_file"] or metric["source_field"] != item["source_location"]:
                trace_errors.append(f"{item['traceability_key']}: metric source binding differs from Phase 13.0B")
            source_bytes = source.read_bytes()
            accepted_hashes = {
                sha256(source_bytes),
                sha256(normalized_bytes(source_bytes, item["source_file"])),
            }
            if metric["source_sha256"] not in accepted_hashes:
                trace_errors.append(f"{item['traceability_key']}: metric source hash drift")
            try:
                if abs(numeric_value(item["exact_number_used"]) - float(metric["value"])) > 1e-12 * max(1.0, abs(float(metric["value"]))):
                    trace_errors.append(f"{item['traceability_key']}: exact number differs from metric registry")
            except (ValueError, TypeError):
                trace_errors.append(f"{item['traceability_key']}: exact number is not verifiable")
    checks["evidence_traceability"] = {
        "status": "PASS" if not duplicate_trace_keys and not missing_trace and not extra_trace and not trace_errors else "FAIL",
        "fact_count": len(fact_pairs), "traceability_row_count": len(trace_rows),
        "duplicate_keys": duplicate_trace_keys, "missing_fact_rows": missing_trace,
        "orphan_trace_rows": extra_trace, "errors": trace_errors,
        "untraceable_main_deck_numbers": 0 if not trace_errors and not missing_trace else None,
    }
    if duplicate_trace_keys or missing_trace or extra_trace or trace_errors:
        errors.append("evidence traceability validation failed")

    phase9_audit = json.loads((ROOT / "outputs/phase9_1/artifact_hash_audit.json").read_text(encoding="utf-8"))
    p7891_paths = [item["path"] for item in phase9_audit["artifacts"]]
    p13a_paths = [item["path"] for item in rows(ROOT / "outputs/phase13_0a/presentation_source_hashes.csv")]
    p13_1_paths = [
        path for path in run_git("diff-tree", "--no-commit-id", "--name-only", "-r", PHASE13_1_COMMIT).splitlines()
        if path and path != "README.md"
    ]
    integrity = {
        "phase7_8_9_9_1": audit_paths_against_commit(
            p7891_paths, FROZEN_ALGORITHM_COMMIT, "Phase 7/8/9/9.1 canonical artifacts"
        ),
        "phase13_0a": audit_paths_against_commit(
            p13a_paths, FROZEN_ALGORITHM_COMMIT, "Phase 13.0A registered source artifacts"
        ),
        "phase13_0b": audit_phase13_0b(),
        "phase13_1": audit_paths_against_commit(
            p13_1_paths, PHASE13_1_COMMIT, "Phase 13.1 frozen files excluding README progress"
        ),
    }
    checks["frozen_artifact_integrity"] = {
        "status": "PASS" if all(item["status"] == "PASS" for item in integrity.values()) else "FAIL",
        "scopes": integrity,
    }
    if any(item["status"] != "PASS" for item in integrity.values()):
        errors.append("one or more frozen artifact scopes drifted")

    scientific_outputs = sorted({
        rel for asset in asset_manifest["assets"]
        if asset["scientific_or_conceptual"] == "SCIENTIFIC"
        for rel in asset["output_files"]
    })
    all_asset_outputs = sorted({rel for asset in asset_manifest["assets"] for rel in asset["output_files"]})
    scientific_integrity = audit_paths_against_commit(
        scientific_outputs, PHASE13_1_COMMIT, "Phase 13.1 scientific visual outputs"
    )
    all_asset_integrity = audit_paths_against_commit(
        all_asset_outputs, PHASE13_1_COMMIT, "Phase 13.1 all canonical asset outputs"
    )
    checks["phase13_1_visual_output_integrity"] = {
        "status": "PASS" if scientific_integrity["status"] == "PASS" and all_asset_integrity["status"] == "PASS" else "FAIL",
        "scientific": scientific_integrity, "all_assets": all_asset_integrity,
    }
    if checks["phase13_1_visual_output_integrity"]["status"] != "PASS":
        errors.append("Phase 13.1 visual output drift detected")

    lineage_drift: list[str] = []
    lineage_missing: list[str] = []
    lineage_sources: dict[str, str] = {}
    for asset in asset_manifest["assets"]:
        for rel, expected_hash in asset["source_hashes"].items():
            lineage_sources.setdefault(rel, expected_hash)
            if lineage_sources[rel] != expected_hash:
                lineage_drift.append(f"conflicting registered hashes: {rel}")
    for rel, expected_hash in sorted(lineage_sources.items()):
        path = ROOT / rel
        if not path.is_file():
            lineage_missing.append(rel)
        elif sha256(normalized_bytes(path.read_bytes(), rel)) != expected_hash:
            lineage_drift.append(rel)
    checks["phase13_1_source_lineage"] = {
        "status": "PASS" if not lineage_missing and not lineage_drift else "FAIL",
        "registered_unique_sources": len(lineage_sources),
        "missing": lineage_missing, "drift": lineage_drift,
    }
    if lineage_missing or lineage_drift:
        errors.append("Phase 13.1 figure source lineage failed")

    ancestry_ok = subprocess.run(
        ["git", "merge-base", "--is-ancestor", FROZEN_ALGORITHM_COMMIT, "HEAD"], cwd=ROOT
    ).returncode == 0
    start_ancestor_ok = subprocess.run(
        ["git", "merge-base", "--is-ancestor", STARTING_HEAD, "HEAD"], cwd=ROOT
    ).returncode == 0
    checks["frozen_algorithm_ancestry"] = {
        "status": "PASS" if ancestry_ok and start_ancestor_ok else "FAIL",
        "frozen_algorithm_commit": FROZEN_ALGORITHM_COMMIT,
        "phase13_2_starting_head": STARTING_HEAD,
        "frozen_algorithm_is_ancestor": ancestry_ok,
        "starting_head_is_ancestor_or_head": start_ancestor_ok,
    }
    if not ancestry_ok or not start_ancestor_ok:
        errors.append("Git ancestry check failed")

    upstream_prefixes = (
        "outputs/phase7/", "outputs/phase8/", "outputs/phase9/", "outputs/phase9_1/",
        "outputs/phase13_0a/", "outputs/phase13_0b/", "outputs/phase13_1/",
        "reports/phase7_report.md", "reports/phase8_report.md", "reports/phase9_report.md",
        "reports/phase9_1_final_audit.md", "reports/phase13/", "reports/phase13_1_visual_assets.md",
    )
    changed_since_start = set(run_git("diff", "--name-only", STARTING_HEAD, "--").splitlines())
    worktree_changes = set(run_git("diff", "--name-only", "--").splitlines())
    staged_changes = set(run_git("diff", "--cached", "--name-only", "--").splitlines())
    changed_upstream = sorted(
        path for path in changed_since_start | worktree_changes | staged_changes
        if any(path == prefix or path.startswith(prefix) for prefix in upstream_prefixes)
    )
    checks["no_experiment_or_frozen_output_modified"] = {
        "status": "PASS" if not changed_upstream else "FAIL",
        "changed_upstream_paths": changed_upstream,
    }
    if changed_upstream:
        errors.append(f"upstream or experiment outputs modified: {changed_upstream}")

    current_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    frozen_readme = git_blob(PHASE13_1_COMMIT, "README.md").decode("utf-8")
    section_preserved = readme_phase13_1_section(current_readme) == readme_phase13_1_section(frozen_readme)
    checks["phase13_1_readme_section_preserved"] = {
        "status": "PASS" if section_preserved else "FAIL"
    }
    if not section_preserved:
        errors.append("Phase 13.1 README section changed")

    tracked_pptx = run_git("ls-files", "*.pptx").splitlines()
    untracked_pptx = run_git("ls-files", "--others", "--exclude-standard", "*.pptx").splitlines()
    pptx_paths = sorted(set(tracked_pptx + untracked_pptx))
    checks["no_pptx_created"] = {"status": "PASS" if not pptx_paths else "FAIL", "pptx_paths": pptx_paths}
    if pptx_paths:
        errors.append(f"PPTX files present: {pptx_paths}")

    no_test_selection = architecture["selection_protocol"].get("test_based_selection_introduced") is False
    no_new_science = architecture["selection_protocol"].get("new_experiment_or_statistic_introduced") is False
    checks["no_test_based_selection_introduced"] = {"status": "PASS" if no_test_selection else "FAIL"}
    checks["no_new_experiment_or_statistic"] = {"status": "PASS" if no_new_science else "FAIL"}
    if not no_test_selection:
        errors.append("architecture declares Test-based selection")
    if not no_new_science:
        errors.append("architecture declares a new experiment or statistic")

    main_claims = sorted({cid for slide in main_slides for cid in slide["claim_ids"]})
    appendix_claims = sorted({cid for slide in appendix_slides for cid in slide["claim_ids"]})
    used_claims = set(main_claims) | set(appendix_claims)
    checks["claim_coverage_summary"] = {
        "status": "PASS",
        "approved_claims_available": len(approved_claims),
        "approved_claims_used_total": len(used_claims),
        "main_deck_unique_claims": len(main_claims),
        "appendix_unique_claims": len(appendix_claims),
        "unused_approved_claims": sorted(set(approved_claims) - used_claims),
        "unsupported_main_deck_claims": len(unsupported),
    }

    status = "PASS" if not errors else "FAIL"
    result = {
        "schema_version": 1,
        "phase": "13.2",
        "status": status,
        "validation_scope": "metadata, evidence traceability, Git ancestry, and immutable artifact hashes only",
        "evaluated_starting_head": STARTING_HEAD,
        "frozen_algorithm_commit": FROZEN_ALGORITHM_COMMIT,
        "hash_contract": "LF-normalized SHA-256 for text; raw SHA-256 for binary; committed Git blobs arbitrate frozen scopes.",
        "scientific_operations": {
            "model_training": "NOT_RUN",
            "experiment_rerun": "NOT_RUN",
            "new_statistical_test": "NOT_RUN",
            "figure_regeneration": "NOT_RUN",
            "ppt_creation": "NOT_RUN",
        },
        "checks": checks,
        "errors": errors,
    }
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": status,
        "main_slides": len(main_slides),
        "appendix_slides": len(appendix_slides),
        "unsupported_main_claims": len(unsupported),
        "untraceable_main_numbers": checks["evidence_traceability"]["untraceable_main_deck_numbers"],
        "integrity": {key: value["lf_normalized_drift_count"] for key, value in integrity.items()},
        "errors": errors,
    }, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
