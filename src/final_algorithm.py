"""Fail-closed resolver for the single canonical post-Phase-9 result source."""

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
EXPECTED_REQUIRED_ARTIFACTS = {
    "outputs/phase7/selected_buildings.json",
    "outputs/phase7/model_selection_config.json",
    "outputs/phase7/building_battery_configs.csv",
    "outputs/phase8/selected_weights.csv",
    "outputs/phase9/run_config.json",
    "outputs/phase9/aggregate_metrics.csv",
    "outputs/phase9/final_benchmark.csv",
    "outputs/phase9/competition_summary.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_final_algorithm(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load Phase 9 final_algorithm.json after validating canonical lineage.

    There is deliberately no fallback to Phase 8 or another historical stage.
    """
    root = Path(project_root).resolve()
    lineage_path = root / "outputs" / "phase9" / "data_lineage.json"
    if not lineage_path.is_file():
        raise FileNotFoundError(lineage_path)
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    if lineage.get("status") != "canonical":
        raise ValueError("Phase 9 lineage is not canonical")
    if lineage.get("schema_version") != 2:
        raise ValueError("Unsupported Phase 9 lineage schema")
    if lineage.get("logical_role") != "canonical final algorithm evidence and sole downstream result source":
        raise ValueError("Unexpected Phase 9 logical role")
    artifacts = {item["path"]: item["sha256"] for item in lineage.get("artifacts", [])}
    parents = {item["path"]: item["sha256"] for item in lineage.get("parents", {}).values()}
    relative = "outputs/phase9/final_algorithm.json"
    if relative not in artifacts:
        raise ValueError("Canonical lineage does not register final_algorithm.json")
    final_path = root / relative
    if not final_path.is_file() or _sha256(final_path) != artifacts[relative]:
        raise ValueError("Canonical final algorithm artifact is missing or has changed")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    expected_fields = {
        "schema_version": 1,
        "name": "Decision-Oriented Ensemble Forecasting",
        "acronym": "DOEF",
        "display_name_zh": "面向储能决策的集成负荷预测方法",
        "source_phase": 9,
        "algorithm_version": "1.0",
        "freeze_status": "frozen",
        "status": "canonical",
        "algorithm_development_status": "ENDED / FROZEN",
    }
    for field, expected in expected_fields.items():
        if final.get(field) != expected:
            raise ValueError(f"Invalid final algorithm metadata: {field}")
    if not final.get("algorithm_development_frozen"):
        raise ValueError("Final algorithm is not frozen canonical state")
    if final.get("test_used_to_choose_peak_configuration") is not False:
        raise ValueError("Invalid final selection protocol")
    if tuple(final.get("fixed_buildings", ())) != FINAL_BUILDINGS:
        raise ValueError("Phase 9 fixed building list changed")
    components = final.get("model_components")
    ensemble = final.get("ensemble")
    if not isinstance(components, list) or {item.get("name") for item in components} != {"DayWeek", "LightGBM"}:
        raise ValueError("Required DOEF model component metadata is missing")
    if not isinstance(ensemble, dict) or ensemble.get("weight_config_path") != "outputs/phase8/selected_weights.csv" or ensemble.get("weight_field") != "w_decision":
        raise ValueError("Required DOEF ensemble metadata is missing")
    required = set(final.get("required_artifacts", []))
    if required != EXPECTED_REQUIRED_ARTIFACTS:
        raise ValueError("Final algorithm required-artifact registry changed")
    registered = set(artifacts) | set(parents)
    for required_path in sorted(required):
        path = root / required_path
        if required_path not in registered:
            raise ValueError(f"Required artifact is not registered by canonical lineage: {required_path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_hash = artifacts.get(required_path, parents.get(required_path))
        if _sha256(path) != expected_hash:
            raise ValueError(f"Required artifact hash mismatch: {required_path}")
    return final, lineage
