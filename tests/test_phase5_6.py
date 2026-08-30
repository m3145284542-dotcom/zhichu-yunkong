import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.forecast_artifacts import (
    CANONICAL_PREDICTION_RELATIVE_PATH,
    EXPECTED_TEST_ROWS,
    TEST_TARGET_END,
    TEST_TARGET_START,
    load_canonical_test_forecast,
)


ROOT = Path(__file__).resolve().parents[1]


class CanonicalForecastArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.forecast, cls.metadata = load_canonical_test_forecast(ROOT)

    def test_phase45_is_the_canonical_downstream_source(self) -> None:
        self.assertEqual(self.metadata["canonical_phase"], "phase4_5")
        self.assertEqual(
            self.metadata["canonical_prediction_file"],
            CANONICAL_PREDICTION_RELATIVE_PATH.as_posix(),
        )
        self.assertEqual(self.metadata["test_split_filter"], "split == 'test'")
        self.assertFalse(self.metadata["selection_protocol"]["test_used_for_selection"])

    def test_normalized_schema_and_target_time_integrity(self) -> None:
        self.assertEqual(
            list(self.forecast.columns),
            ["timestamp", "actual", "prediction", "error", "abs_error"],
        )
        self.assertEqual(len(self.forecast), EXPECTED_TEST_ROWS)
        self.assertEqual(self.forecast["timestamp"].min(), TEST_TARGET_START)
        self.assertEqual(self.forecast["timestamp"].max(), TEST_TARGET_END)
        self.assertFalse(self.forecast["timestamp"].duplicated().any())
        self.assertTrue(
            self.forecast["timestamp"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
        )
        self.assertEqual(self.forecast["timestamp"].dt.normalize().nunique(), 30)
        self.assertTrue(
            self.forecast.groupby(self.forecast["timestamp"].dt.normalize()).size().eq(24).all()
        )

    def test_phase45_prediction_is_not_silently_equal_to_phase4(self) -> None:
        phase4 = pd.read_csv(ROOT / "outputs" / "phase4" / "test_prediction.csv")
        phase4["timestamp"] = pd.to_datetime(phase4["timestamp"])
        self.assertTrue(phase4["timestamp"].equals(self.forecast["timestamp"]))
        np.testing.assert_allclose(
            phase4["actual"].to_numpy(dtype=float),
            self.forecast["actual"].to_numpy(dtype=float),
            atol=1e-10,
            rtol=0.0,
        )
        maximum_prediction_change = float(
            np.max(
                np.abs(
                    phase4["prediction"].to_numpy(dtype=float)
                    - self.forecast["prediction"].to_numpy(dtype=float)
                )
            )
        )
        self.assertGreater(maximum_prediction_change, 1e-8)

    def test_existing_phase5_documents_the_old_wrong_source(self) -> None:
        phase5 = json.loads(
            (ROOT / "outputs" / "phase5" / "phase5_config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(phase5["input_prediction_file"], "outputs/phase4/test_prediction.csv")


if __name__ == "__main__":
    unittest.main()
