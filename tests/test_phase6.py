import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.phase6 import (
    PEAK_SAMPLE_MULTIPLIERS,
    WEEKLY_BLEND_WEIGHTS,
    daily_peak_timing_metrics,
    day_week_blend,
    peak_sample_weights,
    select_validation_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase6HelperTests(unittest.TestCase):
    def test_day_week_blend_endpoints_and_midpoint(self) -> None:
        frame = pd.DataFrame(
            {
                "yesterday_pred": [10.0, 20.0, 30.0],
                "last_week_pred": [30.0, 40.0, 50.0],
            }
        )
        np.testing.assert_allclose(day_week_blend(frame, 0.0), [10.0, 20.0, 30.0])
        np.testing.assert_allclose(day_week_blend(frame, 1.0), [30.0, 40.0, 50.0])
        np.testing.assert_allclose(day_week_blend(frame, 0.5), [20.0, 30.0, 40.0])
        with self.assertRaises(ValueError):
            day_week_blend(frame, 1.1)

    def test_peak_sample_weights_only_upweight_high_region(self) -> None:
        target = np.array([1.0, 2.0, 3.0, 4.0])
        weights = peak_sample_weights(target, threshold=3.0, multiplier=2.5)
        np.testing.assert_allclose(weights, [1.0, 1.0, 2.5, 2.5])
        with self.assertRaises(ValueError):
            peak_sample_weights(target, threshold=3.0, multiplier=0.9)

    def test_validation_selection_prioritizes_decision_metric(self) -> None:
        table = pd.DataFrame(
            {
                "peak_multiplier": [1.0, 2.0, 3.0],
                "validation_mean_daily_peak": [100.0, 99.0, 99.0],
                "validation_worst_10pct_daily_peak": [120.0, 119.0, 118.0],
                "validation_MAE": [5.0, 8.0, 9.0],
            }
        )
        selected = select_validation_candidate(table, "peak_multiplier")
        self.assertEqual(float(selected["peak_multiplier"]), 3.0)

    def test_daily_peak_timing_metrics(self) -> None:
        ts = pd.date_range("2026-01-01", periods=24, freq="h")
        actual = np.arange(24, dtype=float)
        predicted = actual.copy()
        predicted[22] = 30.0
        predicted[23] = 22.0
        metrics = daily_peak_timing_metrics(ts, actual, predicted)
        self.assertEqual(metrics["daily_peak_hour_MAE"], 1.0)
        self.assertEqual(metrics["daily_peak_hour_exact_rate"], 0.0)
        self.assertGreaterEqual(metrics["daily_top3_overlap"], 2.0 / 3.0)


class Phase6AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output = ROOT / "outputs" / "phase6"
        if not (cls.output / "summary.json").exists():
            raise AssertionError("Run `python scripts/run_phase6.py` before Phase 6 acceptance tests")
        cls.summary = json.loads((cls.output / "summary.json").read_text(encoding="utf-8"))
        cls.selected = json.loads((cls.output / "selected_config.json").read_text(encoding="utf-8"))

    def test_selection_is_validation_only_and_frozen_before_test_loader(self) -> None:
        protocol = self.selected["selection_protocol"]
        self.assertFalse(protocol["test_used_for_selection"])
        self.assertTrue(protocol["selected_before_canonical_test_loader"])
        self.assertEqual(protocol["validation_rows"], 696)
        self.assertEqual(protocol["validation_complete_days"], 29)
        self.assertFalse(self.selected["test_accessed_during_selection"])
        self.assertTrue(self.summary["zero_test_leakage"])

    def test_candidate_grids_are_complete_and_one_candidate_is_selected(self) -> None:
        blend = pd.read_csv(self.output / "validation_day_week_candidates.csv")
        peak = pd.read_csv(self.output / "validation_peak_weight_candidates.csv")
        self.assertEqual(set(blend["weekly_weight"].astype(float)), set(WEEKLY_BLEND_WEIGHTS))
        self.assertEqual(set(peak["peak_multiplier"].astype(float)), set(PEAK_SAMPLE_MULTIPLIERS))
        self.assertEqual(int(blend["selected"].sum()), 1)
        self.assertEqual(int(peak["selected"].sum()), 1)

    def test_canonical_reproduction_is_tight(self) -> None:
        reproduction = json.loads((self.output / "canonical_reproduction.json").read_text(encoding="utf-8"))
        self.assertEqual(reproduction["rows"], 720)
        self.assertLessEqual(float(reproduction["canonical_test_prediction_max_abs_delta"]), 1e-6)

    def test_test_methods_cover_fixed_references_and_phase6_methods(self) -> None:
        decision = pd.read_csv(self.output / "test_decision_metrics.csv")
        methods = set(decision["method"])
        self.assertIn("No Battery", methods)
        self.assertIn("Persistence", methods)
        self.assertIn("Last-week", methods)
        self.assertIn("Canonical LightGBM", methods)
        self.assertIn("Oracle", methods)
        self.assertIn(self.selected["test_method_names"]["peak_aware"], methods)
        self.assertIn(self.selected["test_method_names"]["day_week_blend"], methods)

    def test_constraint_audit_all_passes(self) -> None:
        audit = pd.read_csv(self.output / "constraint_audit.csv")
        self.assertTrue(audit["solver_success"].all())
        for column in (
            "soc_violations",
            "power_violations",
            "simultaneous_charge_discharge_violations",
            "soc_transition_violations",
            "nan_or_inf_count",
        ):
            self.assertEqual(int(audit[column].sum()), 0, column)
        self.assertTrue((audit["initial_soc_error"].abs() <= 1e-6).all())
        self.assertTrue((audit["terminal_soc_error"].abs() <= 1e-6).all())

    def test_report_and_figures_exist(self) -> None:
        required = [
            ROOT / "reports" / "phase6_report.md",
            self.output / "figures" / "01_validation_day_week_blend.png",
            self.output / "figures" / "02_validation_peak_weighting.png",
            self.output / "figures" / "03_test_daily_realized_peaks.png",
            self.output / "figures" / "04_representative_day.png",
        ]
        self.assertTrue(all(path.is_file() and path.stat().st_size > 0 for path in required))


if __name__ == "__main__":
    unittest.main()
