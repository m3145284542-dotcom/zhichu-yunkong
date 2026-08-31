import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.battery.model import BatteryConfig
from src.final_algorithm import load_final_algorithm
from src.phase8 import BUILDINGS
from src.phase9 import (
    BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, DECISION_EQUIVALENCE_BAND,
    PEAK_ALPHAS, PEAK_QUANTILES, choose_final_algorithm, paired_bootstrap,
    peak_sample_weights, select_peak_candidate, train_peak_threshold,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase9UnitTests(unittest.TestCase):
    def test_threshold_depends_only_on_supplied_train_labels(self):
        train = np.arange(10, dtype=float)
        threshold = train_peak_threshold(train, 0.8)
        _mutated_validation_and_test = np.full(100, 1e12)
        self.assertEqual(threshold, train_peak_threshold(train, 0.8))
        self.assertNotEqual(threshold, np.quantile(np.r_[train, _mutated_validation_and_test], 0.8))

    def test_sample_weights_and_alpha_zero(self):
        target = np.array([1.0, 2.0, 3.0, 4.0])
        np.testing.assert_array_equal(peak_sample_weights(target, 3.0, 1.0), [1.0, 1.0, 2.0, 2.0])
        np.testing.assert_array_equal(peak_sample_weights(target, 3.0, 0.0), np.ones(4))

    def test_selection_rejects_test_and_prefers_simple_equivalent_candidate(self):
        table = pd.DataFrame({
            "split": ["validation", "validation"], "q": [0.8, 0.9], "alpha": [0.0, 2.0],
            "normalized_mean_regret": [0.1009, 0.1000], "normalized_p90_regret": [0.2, 0.1],
            "normalized_MAE": [0.2, 0.1],
        })
        self.assertEqual(select_peak_candidate(table)["alpha"], 0.0)
        self.assertEqual(DECISION_EQUIVALENCE_BAND, 0.001)
        with self.assertRaises(ValueError):
            select_peak_candidate(table.assign(split=["validation", "test"]))

    def test_bootstrap_is_reproducible(self):
        values = np.linspace(-1, 1, 40)
        self.assertEqual(paired_bootstrap(values, "x"), paired_bootstrap(values, "x"))
        self.assertEqual(BOOTSTRAP_SEED, 42)
        self.assertEqual(BOOTSTRAP_RESAMPLES, 10_000)

    def test_test_comparison_cannot_promote_algorithm(self):
        comparisons = {
            "PeakAwareLightGBM_vs_LightGBM": {"wins": 5, "mean_normalized_delta": -0.1},
            "PeakAwareLightGBM_vs_Phase8_DOEF": {"wins": 5, "mean_normalized_delta": -0.1},
        }
        bootstrap = {"PeakAwareLightGBM_minus_Phase8_DOEF": {"ci95_upper": -0.01}}
        final = choose_final_algorithm(comparisons, bootstrap)
        self.assertEqual(final["final_algorithm"], "DOEF v1.0 — Decision-Oriented Ensemble Forecasting")
        self.assertEqual(final["algorithm_selection_source"], "Validation")
        self.assertEqual(final["test_role"], "evaluation_only")
        self.assertFalse(final["test_used_to_promote_algorithm"])
        self.assertFalse(final["test_used_to_choose_peak_configuration"])

    def test_frozen_grids_buildings_and_battery(self):
        self.assertEqual(PEAK_QUANTILES, (0.80, 0.90))
        self.assertEqual(PEAK_ALPHAS, (0.0, 0.5, 1.0, 2.0))
        phase7 = json.loads((ROOT / "outputs/phase7/selected_buildings.json").read_text(encoding="utf-8"))
        self.assertEqual(tuple(row["building"] for row in phase7["selected_buildings"]), BUILDINGS)
        battery = pd.read_csv(ROOT / "outputs/phase7/building_battery_configs.csv")
        for row in battery.itertuples():
            expected = BatteryConfig.from_mean_train_load(row.building, row.mean_train_load, 0.10)
            self.assertAlmostEqual(row.capacity, expected.capacity, places=10)
            self.assertAlmostEqual(row.eta_charge, expected.eta_charge, places=12)


class Phase9AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "outputs/phase9"
        if not (cls.out / "summary.json").is_file():
            raise unittest.SkipTest("Run `python scripts/run_phase9.py` for Phase 9 acceptance checks")

    def test_machine_readable_outputs_and_schemas(self):
        required = {
            "run_config.json", "data_lineage.json", "validation_search.csv", "selected_peak_configs.csv",
            "per_building_metrics.csv", "aggregate_metrics.csv", "forecast_metrics.csv", "decision_metrics.csv",
            "efficiency_metrics.csv", "bootstrap_results.csv", "final_algorithm.json", "summary.json",
            "leakage_audit.json", "constraint_summary.json",
            "final_benchmark.csv", "competition_summary.json",
        }
        self.assertTrue(required.issubset({path.name for path in self.out.iterdir()}))
        forecast = pd.read_csv(self.out / "forecast_metrics.csv")
        decision = pd.read_csv(self.out / "decision_metrics.csv")
        self.assertEqual(set(forecast.method), {
            "Persistence", "Day", "Week", "DayWeek", "LightGBM", "XGBoost", "CatBoost", "Phase8_DOEF", "PeakAwareLightGBM",
        })
        self.assertTrue(forecast.groupby("method").building.nunique().eq(8).all())
        self.assertTrue(decision.loc[decision.method.ne("Oracle")].groupby("method").building.nunique().eq(8).all())
        self.assertTrue(np.isfinite(forecast.select_dtypes("number")).all().all())

    def test_validation_freeze_leakage_and_alpha_zero_reproduction(self):
        config = json.loads((self.out / "run_config.json").read_text(encoding="utf-8"))
        leakage = json.loads((self.out / "leakage_audit.json").read_text(encoding="utf-8"))
        search = pd.read_csv(self.out / "validation_search.csv")
        self.assertEqual(config["status"], "frozen_before_test")
        self.assertFalse(config["test_used_for_peak_configuration"])
        self.assertTrue(search.split.eq("validation").all())
        self.assertEqual(search.groupby("building").size().to_dict(), {building: 8 for building in BUILDINGS})
        for _, part in search.loc[search.alpha.eq(0.0)].groupby("building"):
            self.assertLessEqual(float(part.MAE.max() - part.MAE.min()), 1e-10)
        self.assertEqual(leakage["status"], "PASS")
        self.assertLessEqual(leakage["maximum_reproduction_delta"], 1e-8)

    def test_efficiency_bootstrap_constraints_final_and_lineage(self):
        efficiency = pd.read_csv(self.out / "efficiency_metrics.csv")
        self.assertEqual(set(efficiency.method), {"LightGBM", "XGBoost", "CatBoost", "Phase8_DOEF", "PeakAwareLightGBM"})
        self.assertTrue((efficiency.training_time_seconds >= 0).all())
        self.assertTrue((efficiency.inference_time_seconds >= 0).all())
        self.assertTrue((efficiency.artifact_size_bytes > 0).all())
        self.assertTrue(efficiency.test_samples.eq(720).all())
        bootstrap = pd.read_csv(self.out / "bootstrap_results.csv")
        self.assertTrue(bootstrap.seed.eq(42).all())
        self.assertTrue(bootstrap.resamples.eq(10_000).all())
        constraint = json.loads((self.out / "constraint_summary.json").read_text(encoding="utf-8"))
        final = json.loads((self.out / "final_algorithm.json").read_text(encoding="utf-8"))
        lineage = json.loads((self.out / "data_lineage.json").read_text(encoding="utf-8"))
        self.assertEqual(constraint["status"], "PASS")
        self.assertTrue(final["algorithm_development_frozen"])
        self.assertEqual(lineage["status"], "canonical")
        for artifact in lineage["artifacts"]:
            self.assertEqual(hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest(), artifact["sha256"])
        loaded, loaded_lineage = load_final_algorithm(ROOT)
        self.assertEqual(loaded["name"], final["name"])
        self.assertEqual(loaded_lineage["status"], "canonical")

    def test_aggregate_schema_is_one_finite_row_per_method(self):
        aggregate = pd.read_csv(self.out / "aggregate_metrics.csv")
        self.assertEqual(len(aggregate), 9)
        self.assertEqual(aggregate.method.nunique(), 9)
        self.assertTrue(np.isfinite(aggregate.select_dtypes("number")).all().all())

    def test_day_persistence_alias_and_display_merge(self):
        per_building = pd.read_csv(self.out / "per_building_metrics.csv")
        persistence = per_building.loc[per_building.method.eq("Persistence")].sort_values("building").reset_index(drop=True)
        day = per_building.loc[per_building.method.eq("Day")].sort_values("building").reset_index(drop=True)
        self.assertEqual(persistence.building.tolist(), day.building.tolist())
        numeric = persistence.select_dtypes("number").columns
        np.testing.assert_allclose(persistence[numeric], day[numeric], atol=1e-12, rtol=0.0)
        benchmark = pd.read_csv(self.out / "final_benchmark.csv")
        self.assertEqual(int(benchmark.display_name.eq("Day Persistence").sum()), 1)
        self.assertFalse(benchmark.display_name.isin(["Persistence", "Day"]).any())
        alias = benchmark.loc[benchmark.display_name.eq("Day Persistence")].iloc[0]
        self.assertTrue(alias.equivalent_alias)
        self.assertEqual(alias.raw_identifiers, "Persistence|Day")

    def test_relative_improvements_are_derived_from_canonical_aggregate(self):
        aggregate = pd.read_csv(self.out / "aggregate_metrics.csv").set_index("method")
        competition = json.loads((self.out / "competition_summary.json").read_text(encoding="utf-8"))
        derived = competition["doef_vs_lightgbm"]
        expected_mae = 100 * (aggregate.loc["LightGBM", "mean_normalized_MAE"] - aggregate.loc["Phase8_DOEF", "mean_normalized_MAE"]) / aggregate.loc["LightGBM", "mean_normalized_MAE"]
        expected_regret = 100 * (aggregate.loc["LightGBM", "mean_normalized_regret"] - aggregate.loc["Phase8_DOEF", "mean_normalized_regret"]) / aggregate.loc["LightGBM", "mean_normalized_regret"]
        self.assertAlmostEqual(derived["normalized_mae_relative_improvement_pct"], expected_mae, places=12)
        self.assertAlmostEqual(derived["normalized_regret_relative_improvement_pct"], expected_regret, places=12)

    def test_catboost_robust_statistics_come_from_per_building_values(self):
        per_building = pd.read_csv(self.out / "per_building_metrics.csv")
        values = per_building.loc[per_building.method.eq("CatBoost"), "peak_reduction_percentage"].to_numpy(float)
        competition = json.loads((self.out / "competition_summary.json").read_text(encoding="utf-8"))
        catboost = competition["catboost_peak_reduction_pct"]
        self.assertAlmostEqual(catboost["mean"], float(np.mean(values)), places=12)
        self.assertAlmostEqual(catboost["median"], float(np.median(values)), places=12)
        self.assertAlmostEqual(catboost["min"], float(np.min(values)), places=12)
        self.assertAlmostEqual(catboost["max"], float(np.max(values)), places=12)
        self.assertEqual(len(catboost["per_building"]), 8)

    def test_final_algorithm_v1_metadata_and_metric_semantics(self):
        final, _ = load_final_algorithm(ROOT)
        self.assertEqual(final["name"], "Decision-Oriented Ensemble Forecasting")
        self.assertEqual(final["acronym"], "DOEF")
        self.assertEqual(final["source_phase"], 9)
        self.assertEqual(final["algorithm_version"], "1.0")
        self.assertEqual(final["freeze_status"], "frozen")
        competition = json.loads((self.out / "competition_summary.json").read_text(encoding="utf-8"))
        semantics = competition["metric_semantics"]
        self.assertFalse(semantics["peak_reduction_is_energy_saving"])
        self.assertFalse(semantics["energy_saving_metric_present"])

    def test_loader_fails_closed_without_phase9_and_never_uses_phase8(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            phase8 = root / "outputs/phase8"
            phase8.mkdir(parents=True)
            (phase8 / "final_algorithm.json").write_text('{"name":"fallback"}', encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                load_final_algorithm(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            phase9 = root / "outputs/phase9"
            phase9.mkdir(parents=True)
            shutil.copy2(self.out / "data_lineage.json", phase9 / "data_lineage.json")
            with self.assertRaises(FileNotFoundError):
                load_final_algorithm(root)

    def test_test_protocol_documentation_uses_honest_terminology(self):
        documents = [ROOT / "README.md", *sorted((ROOT / "reports").glob("*.md"))]
        banned = ("pristine blind", "completely unseen", "untouched test", "never-seen test", "never seen test", "blind holdout")
        for path in documents:
            text = path.read_text(encoding="utf-8").casefold()
            for phrase in banned:
                self.assertNotIn(phrase, text, f"{phrase!r} in {path}")

    def test_phase7_phase8_canonical_hashes_match_cleanup_audit(self):
        competition = json.loads((self.out / "competition_summary.json").read_text(encoding="utf-8"))
        audit = competition["historical_artifact_audit"]
        for path_key, hash_key in (("phase7_manifest_path", "phase7_manifest_sha256"), ("phase8_lineage_path", "phase8_lineage_sha256")):
            path = ROOT / audit[path_key]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), audit[hash_key])
        self.assertFalse(audit["frozen_artifacts_modified_by_cleanup"])


if __name__ == "__main__":
    unittest.main()
