"""Fail-closed resolver for the single canonical post-Phase-9 result source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


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
    if lineage.get("logical_role") != "canonical final algorithm evidence and sole downstream result source":
        raise ValueError("Unexpected Phase 9 logical role")
    artifacts = {item["path"]: item["sha256"] for item in lineage.get("artifacts", [])}
    relative = "outputs/phase9/final_algorithm.json"
    if relative not in artifacts:
        raise ValueError("Canonical lineage does not register final_algorithm.json")
    final_path = root / relative
    if not final_path.is_file() or _sha256(final_path) != artifacts[relative]:
        raise ValueError("Canonical final algorithm artifact is missing or has changed")
    final = json.loads(final_path.read_text(encoding="utf-8"))
    if final.get("status") != "canonical" or not final.get("algorithm_development_frozen"):
        raise ValueError("Final algorithm is not frozen canonical state")
    if final.get("test_used_to_choose_peak_configuration") is not False:
        raise ValueError("Invalid final selection protocol")
    return final, lineage
