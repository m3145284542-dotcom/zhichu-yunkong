"""Read-only aggregation of frozen evidence for the provincial defense revision."""
from pathlib import Path
import hashlib
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCES = [
    'outputs/phase8/global_test_summary.csv',
    'outputs/phase8/test_decision_metrics.csv',
    'outputs/phase8/test_daily_decision_metrics.csv',
    'outputs/phase8/selected_weights.csv',
    'outputs/phase8/global_selected_weights.json',
    'outputs/phase7/building_battery_configs.csv',
    'outputs/phase9/final_benchmark.csv',
    'outputs/phase9_1/final_reporting_summary.json',
    'outputs/phase9_1/building_level_bootstrap.csv',
    'reports/provincial_20261012/assets/system_demo.png',
    'src/phase8.py', 'docs/ENGINEERING_INTEGRATION.md',
]

def main():
    summary = pd.read_csv(ROOT / SOURCES[0]).set_index('method')
    decisions = pd.read_csv(ROOT / SOURCES[1])
    daily = pd.read_csv(ROOT / SOURCES[2])
    weights = pd.read_csv(ROOT / SOURCES[3])
    battery = pd.read_csv(ROOT / SOURCES[5]).set_index('building')
    paired = decisions.pivot(index='building', columns='method', values='mean_regret_vs_oracle')
    paired = paired.div(battery.mean_train_load, axis=0)
    doef = 'DecisionSelectedPerBuilding'
    refs = ['DayWeek', 'LightGBM', 'ForecastSelectedGlobal', 'ForecastSelectedPerBuilding', 'DecisionSelectedGlobal', doef]
    ablation = []
    for method in refs:
        row = summary.loc[method]
        delta = paired[doef] - paired[method]
        ablation.append(dict(method=method, mae=float(row.mean_normalized_MAE), regret=float(row.mean_normalized_regret),
            relative_improvement_pct=float(100 * (1-summary.loc[doef,'mean_normalized_regret']/row.mean_normalized_regret)),
            wins=int((delta < -1e-9).sum()), ties=int((delta.abs()<=1e-9).sum()), losses=int((delta>1e-9).sum())))
    fref = 'ForecastSelectedPerBuilding'
    loo = []
    for name in paired.index:
        q = paired.drop(name)
        loo.append(dict(omitted_building=name, relative_improvement_pct=float(100*(1-q[doef].mean()/q[fref].mean()))))
    case_pivot=daily[daily.method.isin([doef,fref])].pivot(index=['building','date'],columns='method',values='realized_peak')
    case_key=(case_pivot[doef]-case_pivot[fref]).abs().idxmax()
    case=daily[(daily.building==case_key[0])&(daily.date==case_key[1])]
    frozen=json.loads((ROOT / SOURCES[7]).read_text(encoding='utf-8'))
    result = dict(schema_version=1,status='candidate',role='derived presentation evidence; no new model or dispatch experiment',
        creation_date='2026-10-12',producer='reports/provincial_20261012/prepare_evidence.py',
        canonical_research_modified=False,
        source_artifacts=[dict(path=p,sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in SOURCES],
        ablation=ablation,weights=weights.to_dict('records'),
        benchmark=pd.read_csv(ROOT / SOURCES[6]).to_dict('records'),
        bootstrap_rows=pd.read_csv(ROOT / SOURCES[8]).to_dict('records'),
        canonical_summary=frozen,leave_one_building_out=loo,
        case=dict(building=case_key[0],date=case_key[1],selection='post-hoc maximum absolute test daily peak difference between the two selectors',
            rows=case[['method','original_peak','realized_peak','regret_vs_oracle']].to_dict('records')),
        caveats=['The two 6/2/0 and 5/2/1 comparisons have different baselines.',
                 'ForecastSelectedGlobal is numerically an equal blend because its Validation-selected weight is 0.5, not a newly preregistered equal-weight experiment.',
                 'New relative percentages and leave-one-out summaries are arithmetic reanalyses of saved metrics, not new tests or formal replacements for frozen conclusions.',
                 'The case was selected after evaluating Test; its colored historical curves are realized grid loads, not forecast loads.'])
    # Sanitize NaN from CSV alias/baseline fields, preserving absent values as null.
    result=json.loads(json.dumps(result,ensure_ascii=False),parse_constant=lambda _:None)
    (HERE/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Prepared frozen-evidence aggregation; source data unchanged.')

if __name__ == '__main__':
    main()
