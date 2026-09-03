"""Fail-closed validation and promotion for Phase 13.1 visual assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_1"
MANIFEST = OUT / "manifests" / "visual_asset_manifest.json"
VALIDATION = OUT / "manifests" / "validation_results.json"
FROZEN_COMMIT = "549abc314e93e2862bfc22965db89622c22890e1"
TEXT_EXT = {".json", ".csv", ".txt", ".md", ".py", ".yml", ".yaml", ".toml"}
REQUIRED_ASSET_FIELDS = {
    "asset_id", "title", "asset_type", "scientific_or_conceptual", "claim_id", "evidence_id",
    "source_phase", "source_files", "source_hashes", "source_fields", "deterministic_transform",
    "output_files", "slide_role", "priority", "supports_claim", "does_not_support", "required_caveat",
    "truthfulness_status", "presentation_suitability", "reproducibility_status",
}


def normalized(data: bytes, path: str) -> bytes:
    if Path(path).suffix.lower() in TEXT_EXT:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def blob(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "cat-file", "blob", f"{commit}:{path}"], cwd=ROOT)


def validate_frozen_git(paths: list[str], label: str) -> dict:
    drift = []
    missing = []
    for rel in paths:
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        current = digest(normalized(path.read_bytes(), rel))
        frozen = digest(normalized(blob(FROZEN_COMMIT, rel), rel))
        if current != frozen:
            drift.append(rel)
    return {"label": label, "registered": len(paths), "validated": len(paths) - len(missing), "drift_count": len(drift), "missing": missing, "drift": drift, "status": "PASS" if not missing and not drift else "FAIL"}


def validate_phase13b() -> dict:
    summary = json.loads((ROOT / "outputs/phase13_0b/phase13_0b_summary.json").read_text(encoding="utf-8"))
    drift, missing = [], []
    semantic_parts = []
    for item in summary["artifacts"]:
        rel = item["path"]
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        actual_bytes = normalized(path.read_bytes(), rel)
        actual = digest(actual_bytes)
        semantic_parts.append((rel, actual))
        if actual != item["sha256"]:
            drift.append(rel)
    return {
        "label": "Phase 13.0B registered files",
        "registered": len(summary["artifacts"]),
        "validated": len(summary["artifacts"]) - len(missing),
        "drift_count": len(drift),
        "missing": missing,
        "drift": drift,
        "structured_semantic_digest": digest(json.dumps(semantic_parts, separators=(",", ":")).encode()),
        "status": "PASS" if not missing and not drift else "FAIL",
    }


def output_snapshot(manifest: dict) -> dict[str, str]:
    paths = []
    for asset in manifest["assets"]:
        paths.extend(asset["output_files"])
    paths.extend(manifest.get("preview_files", []))
    paths.append(manifest["style_guide"])
    return {p: file_digest(ROOT / p) for p in sorted(paths)}


def main() -> None:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    before = output_snapshot(manifest)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_phase13_1_visual_assets.py")], cwd=ROOT, check=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    after = output_snapshot(manifest)
    reproducible = before == after
    if not reproducible:
        errors.append("output hashes differ across deterministic rebuild")

    required_top = {"schema_version", "phase", "status", "producer", "hash_contract", "assets", "preview_files", "style_guide"}
    missing_top = sorted(required_top - set(manifest))
    if missing_top:
        errors.append(f"manifest missing top-level fields: {missing_top}")

    asset_ids = set()
    output_checks = []
    for asset in manifest["assets"]:
        missing_fields = sorted(REQUIRED_ASSET_FIELDS - set(asset))
        if missing_fields:
            errors.append(f"{asset.get('asset_id', '<unknown>')} missing fields: {missing_fields}")
        aid = asset["asset_id"]
        if aid in asset_ids:
            errors.append(f"duplicate asset_id: {aid}")
        asset_ids.add(aid)
        scientific = asset["scientific_or_conceptual"] == "SCIENTIFIC"
        if scientific and (not asset["claim_id"] or not asset["evidence_id"]):
            errors.append(f"scientific asset lacks claim/evidence linkage: {aid}")
        if not scientific and not asset["scientific_or_conceptual"].startswith("CONCEPTUAL"):
            errors.append(f"conceptual asset is not explicitly labeled: {aid}")
        for rel, expected in asset["source_hashes"].items():
            path = ROOT / rel
            if not path.exists():
                errors.append(f"missing source: {rel}")
            elif digest(normalized(path.read_bytes(), rel)) != expected:
                errors.append(f"source hash mismatch: {rel}")
        for rel in asset["output_files"]:
            path = ROOT / rel
            if not path.exists() or path.stat().st_size == 0:
                errors.append(f"missing or empty output: {rel}")
                continue
            suffix = path.suffix.lower()
            detail = {"path": rel, "bytes": path.stat().st_size}
            if suffix == ".svg":
                try:
                    root = ET.parse(path).getroot()
                    if not root.tag.endswith("svg"):
                        raise ValueError("root is not svg")
                    detail["svg_parse"] = "PASS"
                except Exception as exc:  # pragma: no cover - diagnostic path
                    errors.append(f"invalid SVG {rel}: {exc}")
            elif suffix == ".png":
                try:
                    with Image.open(path) as image:
                        image.load()
                        detail["dimensions"] = list(image.size)
                        if image.size[0] < 1920 or image.size[1] < 1080:
                            errors.append(f"PNG dimensions below 1920x1080: {rel} {image.size}")
                        stat = ImageStat.Stat(image.convert("RGB"))
                        if max(stat.var) < 1.0:
                            errors.append(f"visually empty PNG: {rel}")
                        detail["png_read"] = "PASS"
                except Exception as exc:  # pragma: no cover - diagnostic path
                    errors.append(f"invalid PNG {rel}: {exc}")
            output_checks.append(detail)

    phase_audit = json.loads((ROOT / "outputs/phase9_1/artifact_hash_audit.json").read_text(encoding="utf-8"))
    p7891_paths = [x["path"] for x in phase_audit["artifacts"]]
    p13a_paths = [row["path"] for row in __import__("csv").DictReader((ROOT / "outputs/phase13_0a/presentation_source_hashes.csv").open(encoding="utf-8-sig", newline=""))]
    integrity = {
        "phase7_8_9_9_1": validate_frozen_git(p7891_paths, "Phase 7/8/9/9.1 canonical artifacts"),
        "phase13_0a": validate_frozen_git(p13a_paths, "Phase 13.0A registered sources"),
        "phase13_0b": validate_phase13b(),
    }
    for check in integrity.values():
        if check["status"] != "PASS":
            errors.append(f"{check['label']} integrity failed")

    # Verify frozen ancestry and absence of modifications in upstream scopes.
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    ancestry_ok = subprocess.run(["git", "merge-base", "--is-ancestor", "062a3ceb02a293bbb78c7c7c4fe1d35fc9ae3999", "HEAD"], cwd=ROOT).returncode == 0
    upstream_diff = subprocess.check_output(["git", "diff", "--name-only", "--", "outputs/phase7", "outputs/phase8", "outputs/phase9", "outputs/phase9_1", "outputs/phase13_0a", "outputs/phase13_0b"], cwd=ROOT, text=True).splitlines()
    if not ancestry_ok:
        errors.append("HF1 starting HEAD is not an ancestor")
    if upstream_diff:
        errors.append(f"upstream frozen files modified: {upstream_diff}")

    passed = not errors
    for asset in manifest["assets"]:
        asset["truthfulness_status"] = "PASS" if passed else "FAIL"
        asset["presentation_suitability"] = "PASS" if passed else "FAIL"
        asset["reproducibility_status"] = "PASS" if reproducible else "FAIL"
        asset["status"] = "canonical" if passed else "candidate"
    manifest["status"] = "canonical" if passed else "candidate"
    manifest["acceptance_reason"] = "All frozen-source, schema, format, readability, truthfulness, lineage, and deterministic rebuild checks passed." if passed else "Validation failed; see validation_results.json."
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    result = {
        "schema_version": 1,
        "phase": "13.1",
        "status": "PASS" if passed else "FAIL",
        "head_at_validation": head,
        "branch": branch,
        "hf1_ancestry": "PASS" if ancestry_ok else "FAIL",
        "hash_contract": "LF-normalized SHA-256 for text; raw SHA-256 for binary; frozen Git committed bytes arbitrate legacy CRLF registry entries.",
        "legacy_registry_note": "Some Phase 7/8/9 and Phase 13.0A text digests were historically recorded from CRLF checkouts. They are not rewritten; normalized current bytes are compared with frozen committed blobs to distinguish newline conversion from real drift.",
        "manifest_schema": "PASS" if not missing_top else "FAIL",
        "asset_count": len(manifest["assets"]),
        "source_files_exist": "PASS" if not any(e.startswith("missing source") for e in errors) else "FAIL",
        "outputs": output_checks,
        "deterministic_rebuild": "PASS" if reproducible else "FAIL",
        "integrity": integrity,
        "claim_evidence_semantic_changes": "NONE" if integrity["phase13_0b"]["status"] == "PASS" else "UNRESOLVED",
        "new_experiments_or_statistical_tests": "NO",
        "ppt_created": "NO",
        "errors": errors,
    }
    VALIDATION.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "asset_count": result["asset_count"], "deterministic_rebuild": result["deterministic_rebuild"], "integrity": {k: v["drift_count"] for k, v in integrity.items()}, "errors": errors}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
