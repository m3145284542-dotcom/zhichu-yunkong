import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.final_algorithm import load_final_algorithm
from src.phase8 import BUILDINGS
from src.phase9_1 import building_level_paired_bootstrap, choose_canonical_algorithm


ROOT = Path(__file__).resolve().parents[1]


class Phase91UnitTests(unittest.TestCase):
    def test_test_cannot_promote_algorithm(self):
        hostile_test_result = {"winner": "PeakAwareLightGBM", "ci95_upper": -999.0}
        final = choose_canonical_algorithm(hostile_test_result)
        self.assertEqual(final["acronym"], "DOEF")
        self.assertEqual(final["algorithm_selection_source"], "Validation")
        self.assertEqual(final["test_role"], "evaluation_only")
        self.assertFalse(final["test_can_promote_algorithm"])

    def test_building_bootstrap_is_deterministic_and_uses_eight_buildings(self):
        values = np.linspace(-0.008, -0.001, 8)
        first = building_level_paired_bootstrap(values)
        second = building_level_paired_bootstrap(values)
        self.assertEqual(first, second)
        self.assertEqual(first["resampling_unit"], "building")
        self.assertEqual(first["number_of_units"], 8)
        self.assertEqual(first["resamples"], 10_000)
        self.assertEqual(first["seed"], 42)


class Phase91AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "outputs/phase9_1"
        if not (cls.out / "data_lineage.json").is_file():
            raise unittest.SkipTest("Run `python scripts/run_phase9_1.py` first")

    def test_required_outputs_and_canonical_lineage(self):
        required = {
            "methodology_audit.json", "building_level_bootstrap.csv",
            "building_level_bootstrap_summary.json", "metric_semantics.json",
            "unit_semantics.json", "claim_audit.csv", "artifact_hash_audit.json",
            "final_reporting_summary.json", "doef_prediction_invariance.json", "data_lineage.json",
        }
        self.assertTrue(required.issubset({path.name for path in self.out.iterdir()}))
        lineage = json.loads((self.out / "data_lineage.json").read_text(encoding="utf-8"))
        self.assertEqual(lineage["status"], "canonical")
        for item in lineage["artifacts"]:
            self.assertEqual(hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest(), item["sha256"])

    def test_doef_predictions_unchanged(self):
        audit = json.loads((self.out / "doef_prediction_invariance.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "PASS")
        self.assertLessEqual(audit["max_absolute_delta"], 1e-12)
        self.assertEqual(audit["reference_sha256"], audit["audited_sha256"])
        self.assertEqual(audit["samples"], 8 * 720)

    def test_frozen_artifact_hashes_and_building_order(self):
        audit = json.loads((self.out / "artifact_hash_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "PASS")
        rows = {row["path"]: row for row in audit["artifacts"]}
        for relative in (
            "outputs/phase7/selected_buildings.json",
            "outputs/phase7/model_selection_config.json",
            "outputs/phase7/building_battery_configs.csv",
            "outputs/phase8/selected_weights.csv",
        ):
            self.assertTrue(rows[relative]["unchanged"])
            self.assertEqual(rows[relative]["before_sha256"], rows[relative]["after_sha256"])
        selected = json.loads((ROOT / "outputs/phase7/selected_buildings.json").read_text(encoding="utf-8"))
        self.assertEqual(tuple(row["building"] for row in selected["selected_buildings"]), BUILDINGS)

    def test_formal_bootstrap_matches_saved_building_differences(self):
        differences = pd.read_csv(self.out / "building_level_bootstrap.csv")
        saved = json.loads((self.out / "building_level_bootstrap_summary.json").read_text(encoding="utf-8"))
        recomputed = building_level_paired_bootstrap(differences.normalized_difference.to_numpy(float))
        for field in (
            "point_estimate", "median_bootstrap_estimate", "ci95_lower", "ci95_upper",
            "probability_mean_less_than_zero",
        ):
            self.assertAlmostEqual(saved[field], recomputed[field], places=15)
        for field in ("resampling_unit", "number_of_buildings", "number_of_units", "resamples", "seed"):
            self.assertEqual(saved[field], recomputed[field])
        self.assertEqual(saved["resampling_unit"], "building")
        self.assertEqual(saved["number_of_buildings"], 8)

    def test_unit_and_metric_semantics(self):
        unit = json.loads((self.out / "unit_semantics.json").read_text(encoding="utf-8"))
        self.assertEqual(unit["raw_meter_unit"], "kWh per hourly interval")
        self.assertEqual(unit["dispatch_power_interpretation"], "interval-average kW")
        self.assertEqual(unit["time_step_hours"], 1.0)
        self.assertEqual(unit["conversion"], "P_t = E_t / delta_t")
        self.assertTrue(unit["numeric_values_unchanged_due_to_one_hour_interval"])
        metric = json.loads((self.out / "metric_semantics.json").read_text(encoding="utf-8"))
        self.assertTrue(metric["peak_reduction_percentage"]["not_equivalent_to_decision_regret"])

    def test_weight_mismatch_is_complete_not_cherry_picked(self):
        summary = json.loads((self.out / "final_reporting_summary.json").read_text(encoding="utf-8"))
        weights = summary["forecast_vs_decision_weights"]
        self.assertEqual(weights["total"], 8)
        self.assertEqual(weights["different"], 6)
        self.assertEqual(len(weights["rows"]), 8)

    def test_claim_audit_passes_for_final_canonical_documents(self):
        claims = pd.read_csv(self.out / "claim_audit.csv")
        self.assertFalse(claims.empty)
        self.assertTrue(claims.status.eq("PASS").all())
        self.assertTrue(claims.occurrences.eq(0).all())

    def test_loader_is_phase91_fail_closed(self):
        final, lineage = load_final_algorithm(ROOT)
        self.assertEqual(final["acronym"], "DOEF")
        self.assertEqual(final["test_role"], "evaluation_only")
        self.assertEqual(lineage["status"], "canonical")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            historical = root / "outputs/phase9"
            historical.mkdir(parents=True)
            shutil.copy2(ROOT / "outputs/phase9/final_algorithm.json", historical / "final_algorithm.json")
            with self.assertRaises(FileNotFoundError):
                load_final_algorithm(root)


if __name__ == "__main__":
    unittest.main()
