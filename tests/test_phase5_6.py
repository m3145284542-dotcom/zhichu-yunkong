import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.forecast_artifacts import (
    CANONICAL_CONFIG_RELATIVE_PATH,
    CANONICAL_PHASE,
    CANONICAL_PREDICTION_RELATIVE_PATH,
    load_canonical_test_forecast,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "phase5_6"
EXPECTED_COLUMNS = ["timestamp", "actual", "prediction", "error", "abs_error"]


class CanonicalForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.forecast, cls.lineage = load_canonical_test_forecast(ROOT)

    def test_canonical_source_and_normalized_schema(self) -> None:
        self.assertEqual(CANONICAL_PHASE, "phase4_5")
        self.assertEqual(
            CANONICAL_PREDICTION_RELATIVE_PATH.as_posix(),
            "outputs/phase4_5/final_predictions.csv",
        )
        self.assertEqual(
            CANONICAL_CONFIG_RELATIVE_PATH.as_posix(),
            "outputs/phase4_5/final_config.json",
        )
        self.assertEqual(list(self.forecast.columns), EXPECTED_COLUMNS)

    def test_test_period_hourly_continuity_and_shape(self) -> None:
        timestamps = self.forecast["timestamp"]
        self.assertEqual(len(timestamps), 720)
        self.assertEqual(timestamps.min(), pd.Timestamp("2017-12-02 00:00:00"))
        self.assertEqual(timestamps.max(), pd.Timestamp("2017-12-31 23:00:00"))
        self.assertFalse(timestamps.duplicated().any())
        self.assertTrue(timestamps.diff().dropna().eq(pd.Timedelta(hours=1)).all())
        counts = self.forecast.groupby(timestamps.dt.normalize()).size()
        self.assertEqual(len(counts), 30)
        self.assertTrue(counts.eq(24).all())

    def test_t_plus_24_hour_semantics(self) -> None:
        source = pd.read_csv(
            ROOT / CANONICAL_PREDICTION_RELATIVE_PATH,
            parse_dates=["feature_timestamp", "target_timestamp"],
        )
        test = source.loc[source["split"].eq("test")]
        self.assertTrue(
            (test["target_timestamp"] - test["feature_timestamp"])
            .eq(pd.Timedelta(hours=24))
            .all()
        )
        pd.testing.assert_series_equal(
            self.forecast["timestamp"],
            test["target_timestamp"].reset_index(drop=True).rename("timestamp"),
        )

    def test_phase4_and_phase4_5_alignment_and_prediction_change(self) -> None:
        phase4 = pd.read_csv(ROOT / "outputs" / "phase4" / "test_prediction.csv", parse_dates=["timestamp"])
        self.assertTrue(phase4["timestamp"].equals(self.forecast["timestamp"]))
        np.testing.assert_array_equal(phase4["actual"], self.forecast["actual"])
        self.assertFalse(np.array_equal(phase4["prediction"], self.forecast["prediction"]))

    def test_selection_protocol_and_sha256_lineage(self) -> None:
        config = json.loads((ROOT / CANONICAL_CONFIG_RELATIVE_PATH).read_text(encoding="utf-8"))
        protocol = config["selection_protocol"]
        self.assertIs(protocol["test_used_for_selection"], False)
        self.assertEqual(protocol["train_target_cutoff_exclusive"], "2017-11-01 00:00:00")
        self.assertEqual(protocol["validation_target_cutoff_exclusive"], "2017-12-01 00:00:00")
        for key, relative in (
            ("prediction_sha256", CANONICAL_PREDICTION_RELATIVE_PATH),
            ("config_sha256", CANONICAL_CONFIG_RELATIVE_PATH),
        ):
            expected = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(self.lineage[key], expected)
            self.assertEqual(len(expected), 64)

    def test_loader_has_no_phase4_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            historical = root / "outputs" / "phase4" / "test_prediction.csv"
            historical.parent.mkdir(parents=True)
            historical.write_text("timestamp,actual,prediction\n", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                load_canonical_test_forecast(root)

    def test_historical_bug_is_recorded_in_phase5_config(self) -> None:
        config = json.loads(
            (ROOT / "outputs" / "phase5" / "phase5_config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["input_prediction_file"], "outputs/phase4/test_prediction.csv")


@unittest.skipUnless((OUTPUT / "summary.json").exists(), "Run Phase 5.6 before acceptance tests")
class Phase56AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = json.loads((OUTPUT / "summary.json").read_text(encoding="utf-8"))
        cls.audit = pd.read_csv(OUTPUT / "constraint_audit.csv")
        cls.comparison = pd.read_csv(OUTPUT / "comparison_vs_phase5.csv")

    def test_constraints_all_hold(self) -> None:
        self.assertTrue(self.audit["solver_success"].all())
        for column in (
            "soc_violations",
            "power_violations",
            "simultaneous_charge_discharge_violations",
        ):
            self.assertEqual(int(self.audit[column].sum()), 0, column)
        self.assertTrue((self.audit["initial_soc_error"].abs() <= 1e-6).all())
        self.assertTrue((self.audit["terminal_soc_error"].abs() <= 1e-6).all())

    def test_isolated_regression(self) -> None:
        metric_names = (
            "mean_daily_peak",
            "max_peak",
            "mean_peak_reduction",
            "mean_peak_reduction_pct",
            "p95_grid_load",
            "PAR",
            "total_charge",
            "total_discharge",
            "throughput",
            "equivalent_full_cycles",
            "oracle_capture_ratio",
        )
        for controller in ("No Battery", "Persistence", "Oracle"):
            rows = self.comparison.loc[self.comparison["controller"].eq(controller)]
            for metric in metric_names:
                delta = rows[f"delta_{metric}"].dropna().abs()
                self.assertTrue((delta <= 1e-8).all(), f"{controller}: {metric}")

    def test_required_outputs_exist(self) -> None:
        for name in (
            "phase5_6_metrics.csv",
            "daily_metrics.csv",
            "constraint_audit.csv",
            "forecast_source_comparison.csv",
            "comparison_vs_phase5.csv",
            "dispatch_lightgbm.csv",
            "dispatch_persistence.csv",
            "dispatch_oracle.csv",
            "summary.json",
        ):
            path = OUTPUT / name
            self.assertTrue(path.is_file() and path.stat().st_size > 0, name)
        self.assertEqual(self.summary["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
