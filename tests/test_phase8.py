import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.phase8 import (
    WEIGHT_GRID,
    ensemble_prediction,
    select_decision_weight,
    select_forecast_weight,
    select_global_weights,
)
from src.battery.model import BatteryConfig
from src.phase7.evaluation import evaluate_method


ROOT = Path(__file__).resolve().parents[1]
BUILDINGS = {
    "Hog_office_Rolando", "Hog_office_Lavon", "Hog_office_Joey",
    "Lamb_office_Caitlin", "Robin_office_Addie", "Lamb_office_Gerardo",
    "Hog_office_Alexis", "Hog_office_Byron",
}


class Phase8UnitTests(unittest.TestCase):
    def test_ensemble_formula_and_endpoints(self):
        dayweek = np.array([1.0, 3.0, 5.0])
        ml = np.array([5.0, 7.0, 9.0])
        np.testing.assert_array_equal(ensemble_prediction(dayweek, ml, 0.0), dayweek)
        np.testing.assert_array_equal(ensemble_prediction(dayweek, ml, 1.0), ml)
        np.testing.assert_allclose(ensemble_prediction(dayweek, ml, 0.25), [2.0, 4.0, 6.0])

    def test_candidate_grid_is_frozen(self):
        self.assertEqual(WEIGHT_GRID, tuple(np.round(np.arange(0.0, 1.01, 0.1), 1)))

    def test_selection_rejects_non_validation_rows(self):
        frame = pd.DataFrame({
            "split": ["validation", "test"], "weight": [0.0, 1.0],
            "MAE": [2.0, 0.0], "RMSE": [2.0, 0.0],
            "mean_regret_vs_oracle": [2.0, 0.0], "p90_regret": [2.0, 0.0],
        })
        with self.assertRaises(ValueError):
            select_forecast_weight(frame)
        with self.assertRaises(ValueError):
            select_decision_weight(frame)

    def test_selection_objectives_and_deterministic_ties(self):
        frame = pd.DataFrame({
            "split": ["validation"] * 4,
            "weight": [0.0, 0.2, 0.8, 1.0],
            "MAE": [2.0, 1.0, 1.0, 3.0],
            "RMSE": [2.0, 1.5, 1.5, 3.0],
            "mean_regret_vs_oracle": [3.0, 2.0, 1.0, 4.0],
            "p90_regret": [3.0, 2.0, 1.5, 4.0],
        })
        self.assertEqual(select_forecast_weight(frame), 0.2)
        self.assertEqual(select_decision_weight(frame), 0.8)
        endpoint_tie = frame.iloc[[0, 3]].assign(MAE=1.0, RMSE=1.0)
        self.assertEqual(select_forecast_weight(endpoint_tie), 0.0)

    def test_global_selection_uses_train_scale_normalization(self):
        rows = []
        for building, scale in (("small", 10.0), ("large", 1000.0)):
            for weight in (0.0, 1.0):
                rows.append({
                    "building": building, "split": "validation", "weight": weight,
                    "train_mean_load": scale,
                    "MAE": (1.0 if (building, weight) == ("small", 0.0) else
                            3.0 if building == "small" else 200.0 if weight == 0.0 else 100.0),
                    "RMSE": 1.0, "mean_regret_vs_oracle": 1.0,
                    "p90_regret": 1.0,
                })
        selected, aggregate = select_global_weights(pd.DataFrame(rows))
        self.assertEqual(selected["forecast"], 0.0)
        self.assertTrue(aggregate["normalization_source"].eq("Phase 7 Train mean load").all())

    def test_same_forecast_and_battery_config_are_reproducible(self):
        timestamps = pd.Series(pd.date_range("2026-01-01", periods=24, freq="h"))
        actual = 100.0 + 20.0 * np.sin(np.arange(24) * 2 * np.pi / 24)
        prediction = actual + np.linspace(-2.0, 2.0, 24)
        battery = BatteryConfig.from_mean_train_load("synthetic", 100.0, 0.10)
        first = evaluate_method("synthetic", "validation", "same", timestamps, actual, prediction, battery)[0]
        second = evaluate_method("synthetic", "validation", "same", timestamps, actual, prediction, battery)[0]
        for metric in ("mean_daily_peak", "worst_10pct_daily_peak", "battery_throughput", "equivalent_full_cycles"):
            self.assertAlmostEqual(first[metric], second[metric], places=12)


class Phase8AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "outputs" / "phase8"
        if not (cls.out / "aggregate_summary.json").is_file():
            raise unittest.SkipTest("Run `python scripts/run_phase8.py` for Phase 8 acceptance checks")

    def test_required_artifacts_and_building_coverage(self):
        required = {
            "run_config.json", "lineage.json", "validation_weight_search.csv",
            "selected_weights.csv", "test_forecast_metrics.csv",
            "test_decision_metrics.csv", "building_summary.csv",
            "aggregate_summary.json", "leakage_audit.txt", "constraint_audit.txt",
            "global_weight_search.csv", "global_selected_weights.json",
            "global_test_summary.csv", "bootstrap_summary.json",
        }
        self.assertTrue(required.issubset({p.name for p in self.out.iterdir()}))
        selected = pd.read_csv(self.out / "selected_weights.csv")
        self.assertEqual(set(selected.building), BUILDINGS)
        self.assertEqual(len(selected), 8)

    def test_validation_only_freeze_and_global_normalization(self):
        config = json.loads((self.out / "run_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["status"], "frozen_before_test")
        self.assertFalse(config["test_used_for_selection"])
        self.assertEqual(config["candidate_weights"], list(WEIGHT_GRID))
        search = pd.read_csv(self.out / "validation_weight_search.csv")
        self.assertTrue(search.split.eq("validation").all())
        self.assertEqual(search.groupby("building").size().to_dict(), {b: 11 for b in BUILDINGS})
        global_search = pd.read_csv(self.out / "global_weight_search.csv")
        self.assertTrue(global_search.normalization_source.eq("Phase 7 Train mean load").all())

    def test_constraints_leakage_reproducibility_and_frozen_artifacts(self):
        summary = json.loads((self.out / "aggregate_summary.json").read_text(encoding="utf-8"))
        lineage = json.loads((self.out / "lineage.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(lineage["status"], "canonical")
        self.assertTrue(summary["frozen_phase3_7_artifacts_unchanged"])
        self.assertTrue(summary["endpoint_reproduction_passed"])
        self.assertEqual(summary["constraint_audit"]["status"], "PASS")
        self.assertEqual(summary["leakage_audit"]["status"], "PASS")
        for artifact in lineage["artifacts"]:
            digest = hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"], artifact["path"])

    def test_all_six_deployable_schemes_plus_oracle_are_evaluated(self):
        forecast = pd.read_csv(self.out / "test_forecast_metrics.csv")
        decision = pd.read_csv(self.out / "test_decision_metrics.csv")
        deployable = {
            "DayWeek", "LightGBM", "ForecastSelectedPerBuilding",
            "DecisionSelectedPerBuilding", "ForecastSelectedGlobal", "DecisionSelectedGlobal",
        }
        self.assertEqual(set(forecast.method), deployable)
        self.assertEqual(set(decision.method), deployable | {"Oracle"})
        self.assertTrue(forecast.groupby("method").building.nunique().eq(8).all())
        self.assertTrue(decision.groupby("method").building.nunique().eq(8).all())


if __name__ == "__main__":
    unittest.main()
