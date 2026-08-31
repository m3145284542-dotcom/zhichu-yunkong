"""Fail-closed resolver for the canonical Phase 9.1 reporting lineage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


FINAL_BUILDINGS = (
    "Hog_office_Rolando", "Hog_office_Lavon", "Hog_office_Joey",
    "Lamb_office_Caitlin", "Robin_office_Addie", "Lamb_office_Gerardo",
    "Hog_office_Alexis", "Hog_office_Byron",
)
REQUIRED_FROZEN_ARTIFACTS = {
    "outputs/phase7/selected_buildings.json",
    "outputs/phase7/model_selection_config.json",
    "outputs/phase7/building_battery_configs.csv",
    "outputs/phase8/selected_weights.csv",
    "outputs/phase9/forecast_metrics.csv",
    "outputs/phase9/decision_metrics.csv",
    "outputs/phase9/final_benchmark.csv",
    "outputs/phase9/competition_summary.json",
    "outputs/phase9/final_algorithm.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_final_algorithm(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load DOEF only after validating Phase 9.1 and all frozen parents.

    There is deliberately no fallback to Phase 9, Phase 8, or another
    historical stage when Phase 9.1 is absent or invalid.
    """
    root = Path(project_root).resolve()
    lineage_path = root / "outputs/phase9_1/data_lineage.json"
    if not lineage_path.is_file():
        raise FileNotFoundError(lineage_path)
    lineage = _read_json(lineage_path)
    if lineage.get("status") != "canonical" or lineage.get("schema_version") != 1:
        raise ValueError("Phase 9.1 lineage is not supported canonical metadata")
    if lineage.get("logical_role") != "canonical Phase 9.1 methodology, statistical, unit-semantic, and reporting correction":
        raise ValueError("Unexpected Phase 9.1 logical role")

    for parent in lineage.get("parents", {}).values():
        path = root / parent["path"]
        if not path.is_file() or _sha256(path) != parent["sha256"]:
            raise ValueError(f"Canonical parent artifact drift: {parent['path']}")
    artifacts = {item["path"]: item["sha256"] for item in lineage.get("artifacts", [])}
    for relative, expected in artifacts.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"Canonical Phase 9.1 artifact drift: {relative}")

    summary_relative = "outputs/phase9_1/final_reporting_summary.json"
    hash_relative = "outputs/phase9_1/artifact_hash_audit.json"
    if summary_relative not in artifacts or hash_relative not in artifacts:
        raise ValueError("Phase 9.1 final summary or frozen-artifact audit is not registered")
    summary = _read_json(root / summary_relative)
    if summary.get("status") != "canonical":
        raise ValueError("Phase 9.1 final reporting summary is not canonical")
    final = summary.get("final_algorithm", {})
    expected_fields = {
        "name": "Decision-Oriented Ensemble Forecasting",
        "acronym": "DOEF",
        "display_name_zh": "面向储能决策的集成负荷预测方法",
        "source_phase": 9,
        "canonical_reporting_phase": "9.1",
        "algorithm_version": "1.0",
        "freeze_status": "frozen",
        "algorithm_selection_source": "Validation",
        "test_role": "evaluation_only",
        "test_can_promote_algorithm": False,
        "weight_config_path": "outputs/phase8/selected_weights.csv",
        "weight_field": "w_decision",
    }
    for field, expected in expected_fields.items():
        if final.get(field) != expected:
            raise ValueError(f"Invalid final algorithm metadata: {field}")

    rows = summary.get("forecast_vs_decision_weights", {}).get("rows", [])
    if tuple(row.get("building") for row in rows) != FINAL_BUILDINGS:
        raise ValueError("Phase 9.1 fixed building list changed")
    prediction = summary.get("doef_prediction_invariance", {})
    if prediction.get("status") != "PASS" or prediction.get("max_absolute_delta", float("inf")) > 1e-12:
        raise ValueError("DOEF prediction invariance was not proven")

    audit = _read_json(root / hash_relative)
    if audit.get("status") != "PASS":
        raise ValueError("Frozen-artifact audit did not pass")
    audit_rows = {row["path"]: row for row in audit.get("artifacts", [])}
    if not REQUIRED_FROZEN_ARTIFACTS.issubset(audit_rows):
        raise ValueError("Frozen-artifact audit does not cover all required inputs")
    for relative, row in audit_rows.items():
        path = root / relative
        if not row.get("unchanged") or row.get("before_sha256") != row.get("after_sha256"):
            raise ValueError(f"Frozen-artifact audit recorded drift: {relative}")
        if not path.is_file() or _sha256(path) != row["after_sha256"]:
            raise ValueError(f"Frozen artifact changed after Phase 9.1 audit: {relative}")
    return final, lineage
