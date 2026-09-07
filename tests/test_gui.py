import unittest
from gui.server import payload, ROOT
import hashlib
from unittest.mock import patch
import csv
import json


class GuiEvidenceTests(unittest.TestCase):
    def test_complete_projection_and_report_agree(self):
        d = payload()
        buildings = d['algorithm']['fixed_buildings']
        values = []
        for building in buildings:
            battery = next(r for r in d['battery'] if r['building'] == building)
            for method in ('Phase8_DOEF', 'LightGBM'):
                rows = [r for r in d['metrics'] if r['building'] == building and r['method'] == method and r['split'] == 'test']
                self.assertEqual(len(rows), 1)
                if method == 'Phase8_DOEF':
                    values.append(float(rows[0]['mean_regret_vs_oracle']) / float(battery['mean_train_load']))
            search = [r for r in d['search'] if r['building'] == building]
            self.assertEqual(len(search), 11)
            self.assertEqual({r['split'] for r in search}, {'validation'})
        benchmark = next(r for r in d['benchmark'] if r['display_name'] == 'DOEF')
        self.assertAlmostEqual(sum(values) / len(values), float(benchmark['normalized_decision_regret_mean']), places=10)

    def test_lineage_hashes(self):
        for source in payload()['lineage']['sources']:
            self.assertEqual(source['sha256'], hashlib.sha256((ROOT / source['path']).read_bytes().replace(b'\r\n', b'\n')).hexdigest())

    def test_replay_preserves_negative_days_and_pairing(self):
        d = payload()
        rows = [r for r in d['daily'] if r['method'] == 'DecisionSelectedPerBuilding']
        self.assertEqual(len(rows), 240)
        self.assertTrue(any(float(r['realized_peak']) > float(r['original_peak']) for r in rows))
        self.assertTrue(any(float(r['realized_peak']) < float(r['original_peak']) for r in rows))

    def test_corrupt_replay_is_rejected(self):
        from pathlib import Path
        original = Path.read_bytes
        def corrupt(path):
            raw = original(path)
            if path.name == 'test_daily_decision_metrics.csv':
                rows = list(csv.DictReader(raw.decode().splitlines()))
                row = next(r for r in rows if r['method'] == 'DecisionSelectedPerBuilding')
                raw = raw.replace(row['realized_peak'].encode(), b'99999999', 1)
            return raw
        with patch.object(Path, 'read_bytes', corrupt):
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                payload()

    def test_portable_bundle_matches_current_sources(self):
        manifest = json.loads((ROOT/'outputs/gui_demo/manifest.json').read_text(encoding='utf-8'))
        html = (ROOT/manifest['artifact']).read_bytes()
        self.assertEqual(hashlib.sha256(html.replace(b'\r\n', b'\n')).hexdigest(), manifest['sha256'])
        for source in manifest['sources'] + manifest['implementation']:
            self.assertEqual(hashlib.sha256((ROOT/source['path']).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), source['sha256'])
        self.assertIn(b'id="demo-data"', html)
        self.assertNotIn(b'<script src=', html)
        self.assertNotIn(b'<link rel="stylesheet"', html)


if __name__ == '__main__':
    unittest.main()
