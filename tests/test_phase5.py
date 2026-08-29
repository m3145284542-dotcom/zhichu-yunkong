import unittest

import numpy as np

from src.battery.metrics import oracle_capture_ratio
from src.battery.model import BatteryConfig
from src.battery.optimizer import optimize_day


class BatteryConfigTests(unittest.TestCase):
    def test_config_is_derived_from_mean_train_load(self) -> None:
        config = BatteryConfig.from_mean_train_load(
            name="Medium", mean_train_load=100.0, capacity_fraction=0.10
        )
        self.assertAlmostEqual(config.capacity, 240.0)
        self.assertAlmostEqual(config.max_charge_power, 60.0)
        self.assertAlmostEqual(config.max_discharge_power, 60.0)
        self.assertAlmostEqual(config.soc_min, 24.0)
        self.assertAlmostEqual(config.soc_max, 216.0)
        self.assertAlmostEqual(config.initial_soc, 120.0)
        self.assertAlmostEqual(config.eta_charge * config.eta_discharge, 0.9)


class DailyOptimizerTests(unittest.TestCase):
    def test_peak_shaving_and_constraints(self) -> None:
        load = np.array([40.0] * 8 + [80.0] * 8 + [40.0] * 8)
        config = BatteryConfig.from_mean_train_load(
            name="Synthetic", mean_train_load=50.0, capacity_fraction=0.20
        )
        result = optimize_day(load, config)

        self.assertTrue(result.success, result.message)
        self.assertLess(result.forecast_peak, load.max())
        self.assertAlmostEqual(result.soc[0], config.initial_soc, places=6)
        self.assertAlmostEqual(result.soc[-1], config.terminal_soc, places=6)
        self.assertTrue(np.all(result.soc >= config.soc_min - 1e-6))
        self.assertTrue(np.all(result.soc <= config.soc_max + 1e-6))
        self.assertTrue(np.all(result.charge <= config.max_charge_power + 1e-6))
        self.assertTrue(np.all(result.discharge <= config.max_discharge_power + 1e-6))
        self.assertFalse(np.any((result.charge > 1e-6) & (result.discharge > 1e-6)))

    def test_requires_exactly_24_finite_values(self) -> None:
        config = BatteryConfig.from_mean_train_load(
            name="Synthetic", mean_train_load=50.0, capacity_fraction=0.20
        )
        with self.assertRaises(ValueError):
            optimize_day(np.ones(23), config)
        bad = np.ones(24)
        bad[4] = np.nan
        with self.assertRaises(ValueError):
            optimize_day(bad, config)


class DecisionValueMetricTests(unittest.TestCase):
    def test_oracle_capture_ratio(self) -> None:
        self.assertAlmostEqual(oracle_capture_ratio(100.0, 90.0, 80.0), 0.5)
        self.assertTrue(np.isnan(oracle_capture_ratio(100.0, 90.0, 100.0)))


if __name__ == "__main__":
    unittest.main()
