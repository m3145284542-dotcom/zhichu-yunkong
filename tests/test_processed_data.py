import unittest
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT_ROOT / "data" / "processed" / "campus_hourly.csv"
MANIFEST = PROJECT_ROOT / "data" / "processed" / "campus_hourly_manifest.json"


@unittest.skipUnless(PROCESSED.exists(), "Run scripts/run_data_pipeline.py first")
class ProcessedDataAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = pd.read_csv(PROCESSED, parse_dates=["timestamp"])
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_non_empty_and_required_columns(self) -> None:
        self.assertFalse(self.data.empty)
        self.assertIn("load", self.data.columns)

    def test_timestamp_is_unique_and_increasing(self) -> None:
        self.assertTrue(self.data["timestamp"].is_monotonic_increasing)
        self.assertFalse(self.data["timestamp"].duplicated().any())

    def test_load_is_numeric_non_missing_and_non_negative(self) -> None:
        self.assertTrue(pd.api.types.is_numeric_dtype(self.data["load"]))
        self.assertFalse(self.data["load"].isna().any())
        self.assertGreaterEqual(float(self.data["load"].min()), 0.0)

    def test_timestamps_are_hour_aligned(self) -> None:
        ts = self.data["timestamp"]
        self.assertTrue((ts.dt.minute == 0).all())
        self.assertTrue((ts.dt.second == 0).all())
        if len(ts) > 1:
            deltas = ts.diff().dropna()
            self.assertTrue(deltas.dt.total_seconds().eq(3600).all())

    def test_weather_schema_and_provenance_are_traceable(self) -> None:
        expected_weather = {
            "airTemperature",
            "cloudCoverage",
            "dewTemperature",
            "precipDepth1HR",
            "seaLvlPressure",
            "windSpeed",
        }
        self.assertTrue(expected_weather.issubset(self.data.columns))
        self.assertEqual(self.manifest["output_rows"], len(self.data))
        self.assertEqual(
            {item["file"] for item in self.manifest["raw_files"]},
            {"metadata.csv", "weather.csv", "electricity_cleaned.csv"},
        )
        self.assertIn("no zero fill", self.manifest["aggregation"].lower())
        self.assertIn("no interpolation", self.manifest["aggregation"].lower())


if __name__ == "__main__":
    unittest.main()
