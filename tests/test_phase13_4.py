import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_4"


def rows(name):
    with (OUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Phase134EvidenceTest(unittest.TestCase):
    REQUIRED = {
        "claim_registry.csv": {"claim_id", "claim_category", "claim_text", "claim_scope", "status", "allowed_wording", "prohibited_wording", "primary_evidence", "source_file", "source_field_or_section"},
        "numeric_evidence_registry.csv": {"metric_id", "metric_name", "value", "unit", "scope", "split", "method", "source_phase", "source_file", "source_field", "canonical_status", "ppt_slide"},
        "figure_registry.csv": {"figure_id", "title", "purpose", "generation_source", "data_source", "upstream_canonical_artifact", "svg_path", "png_path", "ppt_slide", "integrity_status"},
        "presentation_evidence_map.csv": {"slide_number", "slide_title", "element_type", "claim_text", "claim_id", "numeric_metric_ids", "figure_ids", "evidence_source", "traceability_status", "wording_status"},
        "negative_result_registry.csv": {"result_id", "phase", "experiment", "actual_result", "status", "allowed_wording", "prohibited_wording", "source_file"},
        "discrepancy_registry.csv": {"issue_id", "severity", "artifact", "location", "observed", "canonical", "impact", "recommended_phase14_action", "status"},
    }

    def test_required_columns_and_nonempty(self):
        for name, required in self.REQUIRED.items():
            data = rows(name)
            self.assertTrue(data, name)
            self.assertTrue(required.issubset(data[0]), f"{name}: {required - set(data[0])}")

    def test_unique_ids(self):
        for name, field in [("claim_registry.csv", "claim_id"), ("numeric_evidence_registry.csv", "metric_id"), ("figure_registry.csv", "figure_id"), ("negative_result_registry.csv", "result_id"), ("discrepancy_registry.csv", "issue_id")]:
            values = [row[field] for row in rows(name)]
            self.assertEqual(len(values), len(set(values)), name)

    def test_source_paths_exist(self):
        for name, fields in [
            ("claim_registry.csv", ["source_file", "primary_evidence"]),
            ("numeric_evidence_registry.csv", ["source_file"]),
            ("negative_result_registry.csv", ["source_file"]),
            ("presentation_evidence_map.csv", ["evidence_source"]),
        ]:
            for row in rows(name):
                for field in fields:
                    for value in filter(None, row[field].split(";")):
                        if value.startswith("outputs/") or value.startswith("reports/") or value.startswith("scripts/"):
                            self.assertTrue((ROOT / value).exists(), f"{name}: broken {field}={value}")

    def test_figures_and_upstream_paths_exist(self):
        for row in rows("figure_registry.csv"):
            for field in ["generation_source", "data_source", "upstream_canonical_artifact", "svg_path", "png_path"]:
                for value in filter(None, row[field].split(";")):
                    self.assertTrue((ROOT / value).exists(), f"{row['figure_id']}: broken {field}={value}")
            self.assertEqual(row["integrity_status"], "PASS")

    def test_references_resolve(self):
        claim_ids = {r["claim_id"] for r in rows("claim_registry.csv")}
        metric_ids = {r["metric_id"] for r in rows("numeric_evidence_registry.csv")}
        figure_ids = {r["figure_id"] for r in rows("figure_registry.csv")}
        for row in rows("presentation_evidence_map.csv"):
            slide = int(row["slide_number"])
            self.assertIn(slide, range(1, 24))
            self.assertTrue(set(filter(None, row["claim_id"].split(";"))).issubset(claim_ids))
            self.assertTrue(set(filter(None, row["numeric_metric_ids"].split(";"))).issubset(metric_ids))
            self.assertTrue(set(filter(None, row["figure_ids"].split(";"))).issubset(figure_ids))

    def test_claim_status_vocabulary(self):
        allowed = {"SUPPORTED", "SUPPORTED_WITH_QUALIFICATION", "NEGATIVE_RESULT", "UNSUPPORTED", "REJECTED", "NOT_APPLICABLE"}
        self.assertTrue({r["status"] for r in rows("claim_registry.csv")}.issubset(allowed))

    def test_manifest_schema_and_counts(self):
        manifest = json.loads((OUT / "master_evidence_manifest.json").read_text(encoding="utf-8"))
        required = {"phase", "generated_at", "repository_head", "frozen_baseline", "algorithm_name", "algorithm_version", "algorithm_status", "canonical_artifacts", "claims", "numbers", "figures", "presentation", "negative_results", "terminology", "integrity_summary", "phase14_gate"}
        self.assertTrue(required.issubset(manifest))
        self.assertEqual(manifest["phase"], "13.4")
        self.assertEqual(manifest["claims"]["count"], len(rows("claim_registry.csv")))
        self.assertEqual(manifest["numbers"]["count"], len(rows("numeric_evidence_registry.csv")))
        self.assertEqual(manifest["figures"]["count"], len(rows("figure_registry.csv")))
        self.assertEqual(manifest["presentation"]["slides"], 23)
        self.assertEqual(manifest["operations"]["new_experiments"], 0)
        self.assertEqual(manifest["operations"]["ppt_modifications"], 0)
        for result in manifest["integrity_summary"].values():
            self.assertEqual(result["status"], "PASS")

    def test_required_reports_exist(self):
        for name in ["master_project_record.md", "competition_artifact_index.md", "terminology_and_naming_standard.md", "competition_claim_language_guide.md"]:
            self.assertTrue((ROOT / "reports/phase13_4" / name).is_file())


if __name__ == "__main__":
    unittest.main()
