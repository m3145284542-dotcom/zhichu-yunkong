import unittest

import numpy as np
import pandas as pd

from src.data.pipeline import _select_buildings, aggregate_complete_load, merge_load_weather


class AggregateLoadTests(unittest.TestCase):
    def test_missing_building_is_not_treated_as_zero(self) -> None:
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2017-01-01", periods=3, freq="h"),
                "building_a": [10.0, np.nan, 30.0],
                "building_b": [5.0, 6.0, 7.0],
            }
        )

        result = aggregate_complete_load(frame, ["building_a", "building_b"])

        self.assertEqual(result.loc[0, "load"], 15.0)
        self.assertTrue(pd.isna(result.loc[1, "load"]))
        self.assertEqual(result.loc[2, "load"], 37.0)

    def test_aggregation_rejects_unknown_buildings(self) -> None:
        frame = pd.DataFrame(
            {"timestamp": pd.date_range("2017-01-01", periods=2, freq="h"), "known": [1, 2]}
        )
        with self.assertRaises(ValueError):
            aggregate_complete_load(frame, ["missing"])


class WeatherMergeTests(unittest.TestCase):
    def test_hourly_merge_preserves_load_timestamps(self) -> None:
        timestamps = pd.date_range("2017-01-01", periods=3, freq="h")
        load = pd.DataFrame({"timestamp": timestamps, "load": [1.0, 2.0, 3.0]})
        weather = pd.DataFrame(
            {
                "timestamp": [timestamps[0], timestamps[2]],
                "site_id": ["SiteA", "SiteA"],
                "airTemperature": [10.0, 12.0],
            }
        )

        result = merge_load_weather(load, weather, "SiteA")

        self.assertEqual(result["timestamp"].tolist(), timestamps.tolist())
        self.assertTrue(pd.isna(result.loc[1, "airTemperature"]))
        self.assertNotIn("site_id", result.columns)


class BuildingSelectionTests(unittest.TestCase):
    def test_complete_multi_building_set_excludes_avoidable_gap_source(self) -> None:
        timestamps = pd.date_range("2017-01-01", periods=100, freq="h")
        incomplete = np.arange(100, dtype=float)
        incomplete[50] = np.nan
        electricity = pd.DataFrame(
            {
                "timestamp": timestamps,
                "complete_a": np.arange(100, dtype=float) + 1,
                "complete_b": np.arange(100, dtype=float) + 2,
                "incomplete": incomplete,
            }
        )
        quality = pd.DataFrame(
            {
                "building_id": ["complete_a", "complete_b", "incomplete"],
                "valid_ratio": [1.0, 1.0, 0.99],
                "zero_ratio_valid": [0.0, 0.0, 0.0],
                "negative_count": [0, 0, 0],
            }
        )

        selected, policy = _select_buildings(
            "site", {"site": ["complete_a", "complete_b", "incomplete"]}, electricity, quality
        )

        self.assertEqual(selected, ["complete_a", "complete_b"])
        self.assertIn("complete coverage", policy.lower())


if __name__ == "__main__":
    unittest.main()
