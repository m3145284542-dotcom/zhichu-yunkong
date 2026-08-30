import inspect
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.battery.model import BatteryConfig
from src.battery.robust_optimizer import empirical_cvar, optimize_robust_day
from src.phase5_7 import (
    METHODS,
    RANDOM_SEED,
    bootstrap_scenario_loads,
    build_residual_blocks,
    load_validation_forecast,
)


ROOT = Path(__file__).resolve().parents[1]


class ScenarioConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validation, cls.lineage = load_validation_forecast(ROOT)
        cls.blocks, cls.block_dates = build_residual_blocks(cls.validation)

    def test_validation_blocks_are_natural_24_hour_days(self) -> None:
        self.assertEqual(self.blocks.shape, (30, 24))
        self.assertEqual(len(self.block_dates), 30)
        self.assertTrue(np.isfinite(self.blocks).all())

    def test_bootstrap_shape_reproducibility_and_nonnegative_finite_load(self) -> None:
        forecast = np.full(24, 10.0)
        first, first_meta = bootstrap_scenario_loads(
            forecast, self.blocks, scenario_count=100, seed=RANDOM_SEED
        )
        second, second_meta = bootstrap_scenario_loads(
            forecast, self.blocks, scenario_count=100, seed=RANDOM_SEED
        )
        self.assertEqual(first.shape, (100, 24))
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first_meta, second_meta)
        self.assertTrue(np.isfinite(first).all())
        self.assertTrue((first >= 0.0).all())

    def test_validation_loader_does_not_use_test_residuals(self) -> None:
        self.assertEqual(self.lineage["split"], "validation")
        self.assertEqual(self.lineage["residual_definition"], "actual - prediction")
        source = inspect.getsource(load_validation_forecast)
        self.assertNotIn('eq("test")', source)
        self.assertNotIn("test_prediction.csv", source)


class RobustOptimizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BatteryConfig.from_mean_train_load(
            name="Synthetic", mean_train_load=50.0, capacity_fraction=0.20
        )

    def test_cvar_known_case(self) -> None:
        value, eta = empirical_cvar(np.array([1.0, 2.0, 3.0, 4.0]), alpha=0.5)
        self.assertAlmostEqual(value, 3.5)
        self.assertIn(eta, (2.0, 3.0))

    def test_shape_validation(self) -> None:
        with self.assertRaises(ValueError):
            optimize_robust_day(np.ones((10, 23)), self.config)
        bad = np.ones((10, 24))
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            optimize_robust_day(bad, self.config)

    def test_feasible_constraints_terminal_soc_and_reproducibility(self) -> None:
        base = np.array([40.0] * 8 + [80.0] * 8 + [40.0] * 8)
        scenarios = np.vstack([base, base + 5.0, base + np.linspace(0.0, 8.0, 24)])
        first = optimize_robust_day(scenarios, self.config, alpha=0.90, risk_lambda=1.0)
        second = optimize_robust_day(scenarios, self.config, alpha=0.90, risk_lambda=1.0)
        self.assertTrue(first.success)
        np.testing.assert_allclose(first.charge, second.charge, atol=1e-8, rtol=0.0)
        np.testing.assert_allclose(first.discharge, second.discharge, atol=1e-8, rtol=0.0)
        self.assertAlmostEqual(first.soc[0], self.config.initial_soc, places=6)
        self.assertAlmostEqual(first.soc[-1], self.config.terminal_soc, places=6)
        self.assertTrue(np.all(first.soc >= self.config.soc_min - 1e-6))
        self.assertTrue(np.all(first.soc <= self.config.soc_max + 1e-6))
        self.assertTrue(np.all(first.charge <= self.config.max_charge_power + 1e-6))
        self.assertTrue(np.all(first.discharge <= self.config.max_discharge_power + 1e-6))
        self.assertFalse(np.any((first.charge > 1e-6) & (first.discharge > 1e-6)))
        expected_soc = (
            first.soc[:-1]
            + self.config.eta_charge * first.charge
            - first.discharge / self.config.eta_discharge
        )
        np.testing.assert_allclose(first.soc[1:], expected_soc, atol=1e-6, rtol=0.0)
        expected_cvar, _ = empirical_cvar(first.scenario_peaks, 0.90)
        self.assertAlmostEqual(first.cvar_peak, expected_cvar, places=7)


class Phase57AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output = ROOT / "outputs" / "phase5_7"
        if not (cls.output / "summary.json").exists():
            raise AssertionError("Run `python scripts/run_phase5_7.py` before acceptance tests")
        cls.summary = json.loads((cls.output / "summary.json").read_text(encoding="utf-8"))

    def test_test_was_loaded_only_after_validation_selection(self) -> None:
        selected = json.loads(
            (self.output / "selected_robust_config.json").read_text(encoding="utf-8")
        )
        self.assertTrue(selected["selected_before_test_load"])
        self.assertFalse(selected["test_accessed_during_selection"])
        self.assertFalse(selected["validation_lineage"]["test_residual_used"])
        self.assertTrue(self.summary["zero_test_leakage"])

    def test_all_five_methods_and_thirty_days_are_present(self) -> None:
        daily = pd.read_csv(self.output / "test_daily_metrics.csv")
        self.assertEqual(set(daily["method"]), set(METHODS))
        self.assertTrue(daily.groupby("method").size().eq(30).all())

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

    def test_deterministic_baselines_exactly_reproduce_phase5_6(self) -> None:
        reproduction = pd.read_csv(self.output / "baseline_reproduction.csv")
        self.assertTrue(reproduction["passed"].all())
        self.assertLessEqual(float(reproduction["max_absolute_delta_vs_phase5_6"].max()), 1e-8)

    def test_required_report_and_figures_exist(self) -> None:
        required = (
            ROOT / "reports" / "phase5_7_report.md",
            self.output / "deterministic_vs_robust_daily_peaks.png",
            self.output / "daily_regret_comparison.png",
            self.output / "case_success_day.png",
            self.output / "case_failure_day.png",
            self.output / "lambda_sensitivity.png",
        )
        self.assertTrue(all(path.is_file() and path.stat().st_size > 0 for path in required))


if __name__ == "__main__":
    unittest.main()
