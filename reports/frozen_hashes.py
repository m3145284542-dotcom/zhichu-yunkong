"""Compare historical text hashes across Git checkout newline conventions."""
import hashlib
from pathlib import Path


TEXT_SUFFIXES = {'.csv', '.json', '.md', '.py', '.txt'}


def matches_frozen_hash(path, data, expected, text_identity=None):
    candidates = {data}
    if Path(path).suffix.lower() in TEXT_SUFFIXES:
        # Only UTF-8 text receives newline equivalence; binary evidence is exact.
        data.decode('utf-8')
        lf = data.replace(b'\r\n', b'\n')
        candidates.update((lf, lf.replace(b'\n', b'\r\n')))
        if (text_identity and text_identity['path'] == str(path)
                and text_identity['original_sha256'] == expected
                and hashlib.sha256(lf).hexdigest() == text_identity['lf_sha256']):
            return True
    return any(hashlib.sha256(value).hexdigest() == expected for value in candidates)
