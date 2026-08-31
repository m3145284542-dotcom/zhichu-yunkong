import json
import hashlib
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.battery.model import BatteryConfig
from src.features.load_features import ALL_FEATURES, build_phase4_features
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import day_week_blend
from src.phase7.evaluation import normalized_forecast_metrics
from src.phase7.models import MODEL_CANDIDATES, RANDOM_SEED, fit_candidate, predict
from src.phase7.selection import MORPHOLOGY_FEATURES, select_representative_buildings


ROOT = Path(__file__).resolve().parents[1]


class Phase7UnitTests(unittest.TestCase):
    def test_train_only_deterministic_building_selection(self):
        names = ["Hog_office_Rolando", *[f"Office_{i}" for i in range(9)]]
        rows = []
        for i, name in enumerate(names):
            row = {"building": name, "quality_pass": True}
            row.update({feature: float(i + j / 10) for j, feature in enumerate(MORPHOLOGY_FEATURES)})
            rows.append(row)
        stats = pd.DataFrame(rows)
        _, first = select_representative_buildings(stats, 8)
        mutated = stats.copy()
        mutated["test_MAE"] = np.arange(len(mutated))[::-1] * 1e9
        _, second = select_representative_buildings(mutated, 8)
        self.assertEqual(first.building.tolist(), second.building.tolist())
        self.assertEqual(len(first), 8)
        self.assertEqual(first.building.iloc[0], "Hog_office_Rolando")

    def test_phase6_dayweek_is_reused_exactly(self):
        frame = pd.DataFrame({"yesterday_pred": [10.0, 20.0], "last_week_pred": [30.0, 40.0]})
        np.testing.assert_allclose(day_week_blend(frame, 0.5), [20.0, 30.0])

    def test_split_purge_and_feature_parity(self):
        frame = pd.DataFrame({"timestamp": pd.date_range("2016-01-01", "2017-12-31 23:00", freq="h")})
        frame["load"] = 100 + np.sin(np.arange(len(frame)) * 2 * np.pi / 24)
        supervised = build_phase4_features(frame)
        splits = split_by_feature_time(supervised)
        train = purge_unavailable_targets(splits["train"], "2017-11-01")
        validation = purge_unavailable_targets(splits["validation"], "2017-12-01")
        self.assertLess(train.target_timestamp.max(), pd.Timestamp("2017-11-01"))
        self.assertLess(validation.target_timestamp.max(), pd.Timestamp("2017-12-01"))
        self.assertEqual(len(validation), 696)
        self.assertNotIn("target", ALL_FEATURES)
        self.assertEqual(len(ALL_FEATURES), 31)

    def test_battery_scaling_is_relative(self):
        small = BatteryConfig.from_mean_train_load("a", 100.0, 0.10)
        large = BatteryConfig.from_mean_train_load("b", 250.0, 0.10)
        self.assertAlmostEqual(large.capacity / small.capacity, 2.5)
        self.assertAlmostEqual(small.max_charge_power, small.capacity / 4)
        self.assertEqual(small.soc_min_fraction, large.soc_min_fraction)

    def test_normalized_metric(self):
        ts = pd.date_range("2026-01-01", periods=24, freq="h")
        result = normalized_forecast_metrics(pd.Series(ts), np.full(24, 100.0), np.full(24, 110.0), 200.0)
        self.assertAlmostEqual(result["normalized_MAE"], 0.05)
        self.assertAlmostEqual(result["normalized_RMSE"], 0.05)

    def test_equal_model_search_budget_and_seed(self):
        self.assertEqual(RANDOM_SEED, 42)
        self.assertEqual({name: len(grid) for name, grid in MODEL_CANDIDATES.items()}, {"LightGBM": 2, "XGBoost": 2, "CatBoost": 2})

    def test_model_comparison_is_reproducible(self):
        rng = np.random.default_rng(42)
        frame = pd.DataFrame({"x1": rng.normal(size=480), "x2": rng.normal(size=480)})
        frame["target"] = 2 * frame.x1 - frame.x2 + rng.normal(scale=0.01, size=len(frame))
        train, validation = frame.iloc[:360], frame.iloc[360:]
        for family, grid in MODEL_CANDIDATES.items():
            outputs = []
            for _ in range(2):
                model, iteration = fit_candidate(family, train, validation, ["x1", "x2"], grid[0][1])
                outputs.append(predict(model, family, validation, ["x1", "x2"], iteration))
            np.testing.assert_allclose(outputs[0], outputs[1], atol=1e-12, rtol=0.0, err_msg=family)


class Phase7AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "outputs" / "phase7"
        if not (cls.out / "summary.json").is_file():
            raise AssertionError("Run `python scripts/run_phase7.py` before Phase 7 acceptance tests")
        cls.summary = json.loads((cls.out / "summary.json").read_text())

    def test_selected_count_and_freeze(self):
        selected = json.loads((self.out / "selected_buildings.json").read_text())
        self.assertEqual(len(selected["selected_buildings"]), 8)
        self.assertEqual(selected["status"], "frozen_before_model_training")
        self.assertFalse(selected["validation_or_test_model_performance_used"])

    def test_model_feature_split_and_test_freeze(self):
        config = json.loads((self.out / "model_selection_config.json").read_text())
        self.assertEqual(config["feature_list"], ALL_FEATURES)
        self.assertFalse(config["test_used_for_selection"])
        self.assertEqual(config["status"], "frozen_before_test")
        validation = pd.read_csv(self.out / "model_validation_results.csv")
        counts = validation.loc[validation.model_family.ne("DayWeek")].groupby(["building", "model_family"]).size()
        self.assertTrue(counts.eq(2).all())

    def test_phase6_compatibility(self):
        result = json.loads((self.out / "hog_phase6_compatibility.json").read_text())
        self.assertTrue(result["passed"])
        self.assertLessEqual(result["test_prediction_max_absolute_delta"], 1e-6)
        self.assertLessEqual(result["mean_daily_peak_absolute_delta_vs_phase6"], 1e-6)

    def test_battery_scaling_and_model_outputs(self):
        battery = pd.read_csv(self.out / "building_battery_configs.csv")
        np.testing.assert_allclose(battery.capacity, 24 * battery.mean_train_load * 0.10)
        np.testing.assert_allclose(battery.max_charge_power, battery.capacity / 4)
        forecast = pd.read_csv(self.out / "model_test_forecast_metrics.csv")
        decision = pd.read_csv(self.out / "model_test_decision_metrics.csv")
        self.assertEqual(len(forecast), 32)
        self.assertEqual(len(decision), 32)
        self.assertTrue(np.isfinite(forecast.select_dtypes("number")).all().all())

    def test_ensemble_grid_and_freeze(self):
        config = json.loads((self.out / "selected_ensemble_config.json").read_text())
        self.assertEqual(config["candidate_alphas"], [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertFalse(config["test_used_for_selection"])
        sweep = pd.read_csv(self.out / "ensemble_validation_sweep.csv")
        self.assertEqual(set(sweep.alpha), {0.0, 0.25, 0.5, 0.75, 1.0})

    def test_leakage_constraints_lineage_and_reproducibility(self):
        leakage = json.loads((self.out / "leakage_audit.json").read_text())
        constraint = json.loads((self.out / "constraint_audit.json").read_text())
        manifest = json.loads((self.out / "artifact_manifest.json").read_text())
        self.assertEqual(leakage["status"], "PASS")
        self.assertEqual(constraint["status"], "PASS")
        self.assertEqual(sum(constraint["totals"].values()), 0)
        self.assertEqual(manifest["status"], "canonical")
        for artifact in manifest["artifacts"]:
            digest = hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"], artifact["path"])
        self.assertTrue(self.summary["frozen_artifact_hashes_unchanged"])


if __name__ == "__main__":
    unittest.main()
