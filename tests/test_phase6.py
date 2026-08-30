from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.battery.model import BatteryConfig
from src.models.train_lgbm import fit_lgbm
from src.phase6 import (
    BASELINE_WEEKLY_WEIGHTS,
    PEAK_WEIGHT_CANDIDATES,
    evaluate_dispatch,
    forecast_metrics,
    make_peak_sample_weights,
)


class Phase6Tests(unittest.TestCase):
    def test_candidate_grids_are_frozen(self) -> None:
        self.assertEqual(
            BASELINE_WEEKLY_WEIGHTS,
            (0.0, 0.25, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0),
        )
        self.assertEqual(
            PEAK_WEIGHT_CANDIDATES,
            (
                ("uniform", None, 1.0),
                ("q80_x1_5", 0.80, 1.5),
                ("q80_x2", 0.80, 2.0),
                ("q90_x2", 0.90, 2.0),
                ("q90_x3", 0.90, 3.0),
            ),
        )

    def test_peak_sample_weights_use_training_distribution(self) -> None:
        target = np.arange(10, dtype=float)
        weights, threshold = make_peak_sample_weights(target, 0.80, 2.0)
        self.assertAlmostEqual(threshold, float(np.quantile(target, 0.80)))
        expected = np.where(target >= threshold, 2.0, 1.0)
        np.testing.assert_array_equal(weights, expected)

        reapplied, reapplied_threshold = make_peak_sample_weights(
            target + 100.0,
            0.80,
            2.0,
            threshold=threshold,
        )
        self.assertEqual(reapplied_threshold, threshold)
        self.assertTrue(np.all(reapplied == 2.0))

    def test_uniform_weights_do_not_create_threshold(self) -> None:
        weights, threshold = make_peak_sample_weights(np.array([1.0, 2.0, 3.0]), None, 1.0)
        np.testing.assert_array_equal(weights, np.ones(3))
        self.assertIsNone(threshold)

    def test_forecast_metrics_capture_peak_quality(self) -> None:
        timestamps = pd.date_range("2026-01-01", periods=24, freq="h")
        actual = np.arange(24, dtype=float)
        perfect = actual.copy()
        metrics = forecast_metrics(pd.Series(timestamps), actual, perfect)
        self.assertAlmostEqual(metrics["MAE"], 0.0)
        self.assertAlmostEqual(metrics["RMSE"], 0.0)
        self.assertAlmostEqual(metrics["daily_peak_MAE"], 0.0)
        self.assertAlmostEqual(metrics["peak_hour_MAE"], 0.0)
        self.assertAlmostEqual(metrics["peak_hour_hit_within_1h"], 1.0)

    def test_dispatch_respects_daily_battery_boundaries(self) -> None:
        timestamps = pd.Series(pd.date_range("2026-01-01", periods=24, freq="h"))
        actual = np.array([100.0] * 12 + [200.0] * 12)
        forecast = actual.copy()
        config = BatteryConfig(
            name="test",
            capacity=200.0,
            max_charge_power=50.0,
            max_discharge_power=50.0,
        )
        hourly, daily = evaluate_dispatch(timestamps, actual, forecast, config, "test")
        self.assertEqual(len(hourly), 24)
        self.assertEqual(len(daily), 1)
        self.assertTrue((hourly["soc_start"] >= config.soc_min - 1e-8).all())
        self.assertTrue((hourly["soc_end"] <= config.soc_max + 1e-8).all())
        self.assertAlmostEqual(float(hourly.iloc[0]["soc_start"]), config.initial_soc, places=7)
        self.assertAlmostEqual(float(hourly.iloc[-1]["soc_end"]), config.terminal_soc, places=7)
        self.assertLessEqual(float(daily.iloc[0]["realized_peak"]), float(daily.iloc[0]["original_peak"]) + 1e-8)

    def test_lightgbm_helper_accepts_sample_weights_with_4x_api(self) -> None:
        rng = np.random.default_rng(42)
        train = pd.DataFrame({"x": np.arange(120, dtype=float)})
        train["target"] = 2.0 * train["x"] + rng.normal(0.0, 0.1, len(train))
        validation = pd.DataFrame({"x": np.arange(120, 160, dtype=float)})
        validation["target"] = 2.0 * validation["x"]
        parameters = {
            "objective": "regression",
            "n_estimators": 30,
            "learning_rate": 0.1,
            "num_leaves": 7,
            "random_state": 42,
            "verbosity": -1,
            "deterministic": True,
            "force_col_wise": True,
        }
        weights = np.ones(len(train))
        weights[train["target"] >= train["target"].quantile(0.8)] = 2.0
        model, prediction = fit_lgbm(
            train,
            validation,
            ["x"],
            parameters,
            train_sample_weight=weights,
        )
        self.assertGreaterEqual(int(model.best_iteration_), 1)
        self.assertEqual(prediction.shape, (len(validation),))
        self.assertTrue(np.isfinite(prediction).all())


if __name__ == "__main__":
    unittest.main()
