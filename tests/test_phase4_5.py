import unittest

import numpy as np
import pandas as pd

from src.features.load_features import ALL_FEATURES
from src.models.train_lgbm import purge_unavailable_targets


class Phase45ProtocolTests(unittest.TestCase):
    def test_purge_removes_labels_not_known_at_forecast_start(self) -> None:
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2017-10-30", periods=72, freq="h"),
                "target_timestamp": pd.date_range("2017-10-31", periods=72, freq="h"),
            }
        )
        purged = purge_unavailable_targets(frame, "2017-11-01")
        self.assertEqual(purged["target_timestamp"].max(), pd.Timestamp("2017-10-31 23:00:00"))
        self.assertTrue((purged["target_timestamp"] < pd.Timestamp("2017-11-01")).all())

    def test_purge_requires_target_timestamp(self) -> None:
        with self.assertRaises(KeyError):
            purge_unavailable_targets(pd.DataFrame({"timestamp": ["2017-01-01"]}), "2017-02-01")

    def test_phase4_feature_list_has_no_target_columns(self) -> None:
        forbidden = {"target", "target_timestamp", "yesterday_pred", "last_week_pred"}
        self.assertTrue(forbidden.isdisjoint(ALL_FEATURES))
        self.assertEqual(len(ALL_FEATURES), len(set(ALL_FEATURES)))

    def test_smape_and_r2_diagnostic_definitions(self) -> None:
        from scripts.phase4_5_model_diagnostics import diagnostic_metrics

        actual = np.array([1.0, 2.0, 3.0])
        predicted = np.array([1.0, 2.0, 3.0])
        metrics = diagnostic_metrics(actual, predicted)
        self.assertEqual(metrics["MAE"], 0.0)
        self.assertEqual(metrics["RMSE"], 0.0)
        self.assertEqual(metrics["MAPE"], 0.0)
        self.assertEqual(metrics["sMAPE"], 0.0)
        self.assertEqual(metrics["R2"], 1.0)

    def test_ablation_groups_are_controlled_subsets(self) -> None:
        from scripts.phase4_5_model_diagnostics import ABLATION_FEATURES

        self.assertEqual(set(ABLATION_FEATURES), {"full", "without_calendar", "without_short_term_lag", "without_weekly_lag", "without_long_lag", "without_rolling", "core_lag_plus_calendar"})
        self.assertTrue(all(set(features).issubset(ALL_FEATURES) for features in ABLATION_FEATURES.values()))
        self.assertEqual(ABLATION_FEATURES["full"], ALL_FEATURES)



if __name__ == "__main__":
    unittest.main()
