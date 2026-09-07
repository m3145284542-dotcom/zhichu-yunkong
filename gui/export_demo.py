"""Build a portable, network-independent HTML with verified frozen evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from server import ROOT, payload


def export():
    data = payload()  # Includes daily-to-final metric reconciliation.
    template = (ROOT / 'gui/index.html').read_text(encoding='utf-8')
    css = (ROOT / 'gui/style.css').read_text(encoding='utf-8')
    js = (ROOT / 'gui/app.js').read_text(encoding='utf-8')
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    html = template.replace('<link rel="stylesheet" href="/style.css">', '<style>' + css + '</style>')
    html = html.replace('<script src="/app.js"></script>', '<script type="application/json" id="demo-data">' + encoded + '</script><script>' + js + '</script>')
    html = html.replace('href="/"', 'href="#"')
    output = ROOT / 'outputs/gui_demo'
    output.mkdir(exist_ok=True)
    target = output / 'DOEF_Dynamic_Demo.html'
    target.write_text(html, encoding='utf-8')
    manifest = {'schema_version': 1, 'status': 'canonical', 'role': 'portable presentation only; does not replace scientific sources',
                'producer': 'gui/export_demo.py', 'created_at': datetime.now(timezone.utc).isoformat(),
                'acceptance': '30 daily records per building/method reconciled to final peaks and regret; all assets inlined',
                'artifact': target.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(target.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
                'hash_normalization': 'UTF-8 text with LF line endings', 'sources': data['lineage']['sources'],
                'implementation': [{'path': p, 'sha256': hashlib.sha256((ROOT/p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()} for p in ['gui/index.html','gui/app.js','gui/style.css','gui/server.py','gui/export_demo.py']]}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    export()
