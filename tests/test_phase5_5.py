import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.phase5_5 import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    TEST_END,
    TEST_START,
    paired_bootstrap,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "phase5_5"
TEXT_SUFFIXES = {".csv", ".json", ".md", ".txt"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches_frozen_sha256(path: Path, expected: str) -> bool:
    """Match historical byte hashes without treating CRLF/LF as a content change.

    Phase 5.5 froze hashes on a Windows working tree. GitHub Actions checks out
    normalized text with LF on Linux, so byte-identical scientific artifacts can
    otherwise fail solely because of line endings. Binary files remain strict.
    """
    if sha256(path) == expected:
        return True
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    data = path.read_bytes()
    lf = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return hashlib.sha256(crlf).hexdigest() == expected


class Phase55UnitTests(unittest.TestCase):
    def test_paired_bootstrap_is_seeded_and_paired(self) -> None:
        difference = np.array([1.0, 2.0, 3.0])
        first = paired_bootstrap(difference, seed=42, resamples=1000)
        second = paired_bootstrap(difference, seed=42, resamples=1000)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["mean_paired_difference"], 2.0)
        self.assertAlmostEqual(first["median_paired_difference"], 2.0)

    def test_frozen_bootstrap_configuration(self) -> None:
        self.assertEqual(BOOTSTRAP_SEED, 42)
        self.assertEqual(BOOTSTRAP_RESAMPLES, 10_000)

    def test_frozen_hash_match_only_normalizes_text_line_endings(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.csv"
            windows_bytes = b"a,b\r\n1,2\r\n"
            expected = hashlib.sha256(windows_bytes).hexdigest()
            path.write_bytes(b"a,b\n1,2\n")
            self.assertTrue(matches_frozen_sha256(path, expected))
            path.write_bytes(b"a,b\n1,3\n")
            self.assertFalse(matches_frozen_sha256(path, expected))


class Phase55AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (OUTPUT / "summary.json").exists():
            raise AssertionError("Run `python scripts/run_phase5_5.py` before acceptance tests")
        cls.summary = json.loads((OUTPUT / "summary.json").read_text(encoding="utf-8"))
        cls.predictions = pd.read_csv(ROOT / "outputs" / "phase4" / "test_prediction.csv")
        cls.predictions["timestamp"] = pd.to_datetime(cls.predictions["timestamp"])
        cls.daily = pd.read_csv(OUTPUT / "daily_diagnostics.csv")
        cls.audit = pd.read_csv(OUTPUT / "constraint_audit.csv")

    def test_test_period_and_target_timestamp_integrity(self) -> None:
        timestamps = self.predictions["timestamp"]
        self.assertEqual(len(timestamps), 720)
        self.assertEqual(timestamps.min(), TEST_START)
        self.assertEqual(timestamps.max(), TEST_END)
        self.assertFalse(timestamps.duplicated().any())
        self.assertTrue(timestamps.diff().dropna().eq(pd.Timedelta(hours=1)).all())
        self.assertEqual(timestamps.dt.normalize().nunique(), 30)
        self.assertTrue(timestamps.groupby(timestamps.dt.normalize()).size().eq(24).all())

    def test_phase4_actual_matches_raw_load(self) -> None:
        raw = pd.read_csv(
            ROOT / "data" / "raw" / "electricity_cleaned.csv",
            usecols=["timestamp", "Hog_office_Rolando"],
        )
        raw["timestamp"] = pd.to_datetime(raw["timestamp"])
        aligned = raw.set_index("timestamp")["Hog_office_Rolando"].reindex(self.predictions["timestamp"])
        np.testing.assert_allclose(aligned, self.predictions["actual"], atol=1e-10, rtol=0.0)

    def test_phase4_and_phase5_outputs_are_unchanged(self) -> None:
        hashes = self.summary["input_audit"]["frozen_output_sha256"]
        for relative, expected in hashes.items():
            self.assertTrue(matches_frozen_sha256(ROOT / relative, expected), relative)

    def test_saved_prediction_was_used_without_retraining(self) -> None:
        self.assertTrue(
            matches_frozen_sha256(
                ROOT / "outputs" / "phase4" / "test_prediction.csv",
                self.summary["input_audit"]["phase4_prediction_sha256"],
            )
        )
        source = (ROOT / "src" / "phase5_5.py").read_text(encoding="utf-8")
        self.assertNotIn("fit_lgbm(", source)
        self.assertNotIn("LGBMRegressor(", source)

    def test_phase5_baseline_reproduces_and_uses_original_config(self) -> None:
        reproduction = self.summary["baseline_reproduction"]
        self.assertTrue(reproduction["passed"])
        self.assertLessEqual(reproduction["maximum_absolute_difference"], 1e-8)
        phase5 = json.loads((ROOT / "outputs" / "phase5" / "phase5_config.json").read_text())
        self.assertEqual(
            self.summary["battery_baseline_configuration"],
            phase5["battery_configs"]["Medium"],
        )

    def test_realized_metrics_use_actual_and_oracle_is_benchmark_only(self) -> None:
        self.assertEqual(self.summary["methodology"]["realized_evaluation_load"], "actual")
        self.assertEqual(self.summary["methodology"]["oracle_role"], "perfect-information hindsight benchmark; not deployable")
        self.assertTrue((self.daily["oracle_forecast_mae"] == 0.0).all())

    def test_constraints_hold_for_every_experiment(self) -> None:
        self.assertTrue(self.audit["solver_success"].all())
        for column in (
            "soc_violations",
            "power_violations",
            "simultaneous_charge_discharge_violations",
            "initial_soc_violations",
            "terminal_soc_violations",
        ):
            self.assertEqual(int(self.audit[column].sum()), 0, column)

    def test_sensitivity_and_bias_baselines_match(self) -> None:
        for filename in ("battery_capacity_sensitivity.csv", "battery_power_sensitivity.csv"):
            frame = pd.read_csv(OUTPUT / filename)
            baseline = frame.loc[np.isclose(frame["multiplier"], 1.0)]
            self.assertEqual(set(baseline["controller"]), {"Persistence", "LightGBM", "Oracle"})
            self.assertTrue(baseline["is_phase5_baseline"].all())
            self.assertLessEqual(float(baseline["baseline_max_abs_difference"].max()), 1e-8)
        bias = pd.read_csv(OUTPUT / "forecast_bias_stress_test.csv")
        zero = bias.loc[np.isclose(bias["bias"], 0.0)].iloc[0]
        self.assertLessEqual(float(zero["baseline_max_abs_difference"]), 1e-8)

    def test_outputs_have_no_nan_or_infinity(self) -> None:
        for path in OUTPUT.glob("*.csv"):
            frame = pd.read_csv(path)
            numeric = frame.select_dtypes(include=[np.number]).to_numpy()
            self.assertTrue(np.isfinite(numeric).all(), path.name)
        self.assertNotIn("NaN", (OUTPUT / "summary.json").read_text(encoding="utf-8"))
        self.assertNotIn("Infinity", (OUTPUT / "summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
