import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from reports.submission.frozen_hashes import matches_frozen_hash


class SubmissionHashTests(unittest.TestCase):
    def test_lf_and_crlf_checkouts_match_both_historical_hashes(self):
        lf = b'name,value\nbuilding,6.36\n'
        crlf = lf.replace(b'\n', b'\r\n')
        for recorded in (lf, crlf):
            expected = hashlib.sha256(recorded).hexdigest()
            for checkout in (lf, crlf):
                self.assertTrue(matches_frozen_hash('table.csv', checkout, expected))
                self.assertFalse(matches_frozen_hash('table.csv', checkout.replace(b'6.36', b'6.37'), expected))

    def test_binary_evidence_requires_exact_bytes(self):
        data = b'PNG\r\n\x00\xff'
        expected = hashlib.sha256(data).hexdigest()
        self.assertTrue(matches_frozen_hash('figure.png', data, expected))
        self.assertFalse(matches_frozen_hash('figure.png', data.replace(b'\r\n', b'\n'), expected))

    def test_frozen_inventory_from_git_objects(self):
        root = Path(__file__).resolve().parents[1]
        audit = json.loads((root / 'outputs/phase9_1/artifact_hash_audit.json').read_text())
        identities = {x['path']: x for x in json.loads((root /
            'reports/submission/frozen_text_identity.json').read_text())['artifacts']}
        for item in audit['artifacts']:
            with self.subTest(path=item['path']):
                data = subprocess.check_output(['git', 'show', 'HEAD:' + item['path']], cwd=root)
                expected = item.get('after_sha256') or item['before_sha256']
                identity = identities.get(item['path'])
                self.assertTrue(matches_frozen_hash(item['path'], data, expected, identity))
                self.assertFalse(matches_frozen_hash(item['path'], data + b'changed', expected, identity))
