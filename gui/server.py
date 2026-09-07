"""Local, read-only presentation GUI. Run: python gui/server.py."""
import argparse
import csv
import hashlib
import json
import math
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'algorithm': 'outputs/phase9/final_algorithm.json',
    'summary': 'outputs/phase9_1/final_reporting_summary.json',
    'benchmark': 'outputs/phase9/final_benchmark.csv',
    'metrics': 'outputs/phase9/per_building_metrics.csv',
    'weights': 'outputs/phase8/selected_weights.csv',
    'search': 'outputs/phase8/validation_weight_search.csv',
    'battery': 'outputs/phase7/building_battery_configs.csv',
    'daily': 'outputs/phase8/test_daily_decision_metrics.csv',
}


def payload():
    result = {}
    lineage = []
    for key, relative in SOURCES.items():
        raw = (ROOT / relative).read_bytes()
        content = raw.decode('utf-8-sig')
        result[key] = json.loads(content) if relative.endswith('.json') else list(csv.DictReader(content.splitlines()))
        lineage.append({'path': relative, 'sha256': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()})
    if result['algorithm']['status'] != 'canonical' or result['summary']['status'] != 'canonical':
        raise ValueError('Expected canonical algorithm and reporting sources')
    buildings = result['algorithm']['fixed_buildings']
    if len(buildings) != 8 or set(buildings) != {r['building'] for r in result['weights']}:
        raise ValueError('Building coverage mismatch')
    # Fail closed: the animated daily comparison must reproduce the final metrics.
    for building in buildings:
        dates = None
        for method, final_method in [('LightGBM', 'LightGBM'), ('DecisionSelectedPerBuilding', 'Phase8_DOEF')]:
            rows = sorted([r for r in result['daily'] if r['building'] == building and r['method'] == method], key=lambda r: r['date'])
            actual_dates = [r['date'] for r in rows]
            if len(rows) != 30 or actual_dates != [(date.fromisoformat(actual_dates[0]) + timedelta(days=i)).isoformat() for i in range(30)]:
                raise ValueError('Daily replay requires 30 consecutive unique dates')
            if dates is not None and dates != actual_dates:
                raise ValueError('Comparison date mismatch')
            dates = actual_dates
            if any(r['split'] != 'test' or r['solver_success'] != 'True' for r in rows):
                raise ValueError('Invalid daily split or solver status')
            for row in rows:
                if not all(math.isfinite(float(row[k])) for k in ['original_peak', 'realized_peak', 'regret_vs_oracle']):
                    raise ValueError('Nonfinite daily data')
            final = next(r for r in result['metrics'] if r['building'] == building and r['method'] == final_method and r['split'] == 'test')
            for field, actual in [('post_dispatch_peak', max(float(r['realized_peak']) for r in rows)),
                                  ('no_battery_peak', max(float(r['original_peak']) for r in rows)),
                                  ('mean_regret_vs_oracle', sum(float(r['regret_vs_oracle']) for r in rows) / 30)]:
                if not math.isclose(actual, float(final[field]), rel_tol=1e-9, abs_tol=1e-7):
                    raise ValueError(f'Daily / final metric mismatch: {building} {field}')
        before = {r['date']: r['original_peak'] for r in result['daily'] if r['building'] == building and r['method'] == 'LightGBM'}
        if any(not math.isclose(float(r['original_peak']), float(before[r['date']])) for r in result['daily'] if r['building'] == building and r['method'] == 'DecisionSelectedPerBuilding'):
            raise ValueError('Baseline actual peaks differ between methods')
    result['lineage'] = {'schema_version': 1, 'role': 'read-only GUI projection of frozen evidence',
                         'producer': 'gui/server.py', 'hash_normalization': 'UTF-8 text with LF line endings', 'sources': lineage}
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        files = {'/': ('gui/index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('gui/app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('gui/style.css', 'text/css; charset=utf-8'),
                 '/portable-demo.html': ('outputs/gui_demo/DOEF_Dynamic_Demo.html', 'text/html; charset=utf-8'),
                 '/dispatch.png': ('outputs/phase13_1/figures/sci_05_storage_dispatch_frozen.png', 'image/png')}
        try:
            if path == '/api/demo':
                data, mime = json.dumps(payload(), ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8'
            elif path in files:
                filename, mime = files[path]
                data = (ROOT / filename).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)
        except (OSError, ValueError, KeyError) as exc:
            self.send_error(500, str(exc))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='127.0.0.1', help='Use your LAN IPv4 address for other devices')
    args = parser.parse_args()
    payload()  # Validate required inputs before accepting requests.
    print(f'智储云控演示：http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
