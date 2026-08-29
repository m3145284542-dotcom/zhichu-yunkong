import unittest

import numpy as np
import pandas as pd

from src.make_features import FEATURE_COLUMNS, make_supervised_features
from src.train_baseline import calculate_metrics, split_by_feature_time


class Phase3FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2016-01-01", periods=24 * 400, freq="h"),
                "load": np.arange(24 * 400, dtype=float),
            }
        )

    def test_target_and_naive_baselines_are_strictly_aligned(self) -> None:
        result = make_supervised_features(self.frame)
        row = result.iloc[0]

        self.assertEqual(row["target_timestamp"], row["timestamp"] + np.timedelta64(24, "h"))
        self.assertEqual(row["target"], row["load"] + 24.0)
        self.assertEqual(row["yesterday_pred"], row["load"])
        self.assertEqual(row["last_week_pred"], row["load"] - 144.0)

    def test_rolling_features_exclude_current_load(self) -> None:
        result = make_supervised_features(self.frame)
        row = result.iloc[0]
        source = self.frame.set_index("timestamp")["load"]
        expected = source.loc[row["timestamp"] - np.timedelta64(24, "h"): row["timestamp"] - np.timedelta64(1, "h")].mean()

        self.assertEqual(row["rolling_mean_24"], expected)
        self.assertNotEqual(row["rolling_mean_24"], source.loc[row["timestamp"] - np.timedelta64(23, "h"): row["timestamp"]].mean())

    def test_required_features_are_finite(self) -> None:
        result = make_supervised_features(self.frame)
        self.assertTrue(set(FEATURE_COLUMNS).issubset(result.columns))
        self.assertTrue(np.isfinite(result[FEATURE_COLUMNS].to_numpy()).all())


class Phase3SplitAndMetricTests(unittest.TestCase):
    def test_split_uses_feature_timestamp_without_overlap(self) -> None:
        frame = pd.DataFrame({"timestamp": pd.date_range("2017-10-30", "2017-12-02", freq="h")})
        splits = split_by_feature_time(frame)
        self.assertLess(splits["train"]["timestamp"].max(), splits["validation"]["timestamp"].min())
        self.assertLess(splits["validation"]["timestamp"].max(), splits["test"]["timestamp"].min())

    def test_smape_handles_zero_denominator(self) -> None:
        metrics = calculate_metrics(np.array([0.0, 2.0]), np.array([0.0, 1.0]))
        self.assertAlmostEqual(metrics["sMAPE"], 100.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
