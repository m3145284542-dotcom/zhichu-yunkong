import unittest

import numpy as np
import pandas as pd

from src.features.load_features import (
    CALENDAR_FEATURES,
    LAG_FEATURES,
    ROLLING_FEATURES,
    build_phase4_features,
)
from src.models.train_lgbm import safe_mape, split_by_feature_time


class Phase4FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2016-01-01", periods=24 * 400, freq="h"),
                "load": np.arange(24 * 400, dtype=float) + 1.0,
            }
        )

    def test_required_feature_groups_are_complete(self) -> None:
        self.assertTrue({"day_of_month", "week_of_year"}.issubset(CALENDAR_FEATURES))
        self.assertEqual(
            LAG_FEATURES,
            ["lag_1", "lag_2", "lag_3", "lag_24", "lag_48", "lag_72", "lag_168", "lag_336"],
        )
        self.assertTrue(
            {
                "rolling_mean_3", "rolling_mean_6", "rolling_mean_24",
                "rolling_mean_48", "rolling_mean_168", "rolling_std_24",
                "rolling_std_168", "rolling_min_24", "rolling_max_24",
            }.issubset(ROLLING_FEATURES)
        )

    def test_lags_and_rolling_use_only_past_load(self) -> None:
        result = build_phase4_features(self.frame)
        row = result.iloc[0]
        source = self.frame.set_index("timestamp")["load"]
        timestamp = row["timestamp"]
        for lag in (1, 2, 3, 24, 48, 72, 168, 336):
            self.assertEqual(row[f"lag_{lag}"], source.loc[timestamp - pd.Timedelta(hours=lag)])
        expected = source.loc[timestamp - pd.Timedelta(hours=24): timestamp - pd.Timedelta(hours=1)]
        self.assertEqual(row["rolling_mean_24"], expected.mean())
        self.assertEqual(row["rolling_std_24"], expected.std())
        self.assertNotEqual(
            row["rolling_mean_24"],
            source.loc[timestamp - pd.Timedelta(hours=23): timestamp].mean(),
        )

    def test_target_remains_phase3_t_plus_24_alignment(self) -> None:
        result = build_phase4_features(self.frame)
        row = result.iloc[0]
        source = self.frame.set_index("timestamp")["load"]
        self.assertEqual(row["target_timestamp"], row["timestamp"] + pd.Timedelta(hours=24))
        self.assertEqual(row["target"], source.loc[row["target_timestamp"]])


class Phase4SplitAndMetricTests(unittest.TestCase):
    def test_split_boundaries_match_phase3(self) -> None:
        frame = pd.DataFrame({"timestamp": pd.date_range("2017-10-30", "2017-12-02", freq="h")})
        splits = split_by_feature_time(frame)
        self.assertEqual(splits["validation"]["timestamp"].min(), pd.Timestamp("2017-11-01 00:00:00"))
        self.assertEqual(splits["test"]["timestamp"].min(), pd.Timestamp("2017-12-01 00:00:00"))
        self.assertLess(splits["train"]["timestamp"].max(), splits["validation"]["timestamp"].min())

    def test_safe_mape_ignores_zero_actuals(self) -> None:
        self.assertAlmostEqual(safe_mape(np.array([0.0, 2.0]), np.array([9.0, 1.0])), 50.0)


if __name__ == "__main__":
    unittest.main()
