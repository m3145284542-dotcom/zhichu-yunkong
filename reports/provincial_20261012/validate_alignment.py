"""Check aligned report/deck against frozen artifacts without rerunning experiments."""
from pathlib import Path
import hashlib,json,re,sys
import pandas as pd
import pymupdf

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'outputs/provincial_20261012'
checks={}
def check(k,v): checks[k]=bool(v)
def norm(s):return re.sub(r'\s+','',s).replace('−','-').replace('–','-').replace('**','').replace('`','')
contract=json.loads((HERE/'report_contract.json').read_text(encoding='utf-8'))
new=(HERE/'technical_report.md').read_text(encoding='utf-8')
source=json.loads((HERE/'report_source.json').read_text(encoding='utf-8'))
e=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'))
pdf=pymupdf.open(OUT/'DOEF_Technical_Report_Submission.pdf')
deck=pymupdf.open(OUT/'DOEF_Provincial_Submission.pdf')
report_text=norm(''.join(p.get_text() for p in pdf))
deck_text=norm(''.join(p.get_text() for p in deck))
check('report_contract_registered',contract['source_sha256']==source['historical_parent']['sha256'])
check('registered_markdown',hashlib.sha256((HERE/'technical_report.md').read_bytes().replace(b'\r\n',b'\n')).hexdigest()==source['source_sha256_lf'])
for item in e['source_artifacts']:
    check('source_unchanged_'+item['path'],hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'])
check('all_original_display_equations_unchanged',contract['display_equations']==sorted(re.findall(r'\\\[.*?\\\]',new,re.S)))
for i,block in enumerate(contract['tables']):
    check(f'original_table_{i+1}_preserved',block.replace('Phase 7/8/9/9.1 科研文件哈希','实验文件哈希') in new)
check('report_under_10MB',(OUT/'DOEF_Technical_Report_Submission.pdf').stat().st_size<10_000_000)
for n in ['6.36','3.61','6.44','12.48','3.17','3.41','14.22','0.006850','0.001719']:
    check('shared_number_'+n,n in report_text and n in deck_text)
summary=pd.read_csv(ROOT/'outputs/phase8/global_test_summary.csv').set_index('method')
d=summary.loc['DecisionSelectedPerBuilding','mean_normalized_regret']
for base,expected in [('ForecastSelectedPerBuilding','12.48'),('DecisionSelectedGlobal','3.17')]:
    check('recomputed_gain_'+base,f'{100*(1-d/summary.loc[base,"mean_normalized_regret"]):.2f}'==expected)
metrics=pd.read_csv(ROOT/'outputs/phase8/test_decision_metrics.csv').pivot(index='building',columns='method',values='mean_regret_vs_oracle')
scales=pd.read_csv(ROOT/'outputs/phase7/building_battery_configs.csv').set_index('building')['mean_train_load']
metrics=metrics.div(scales,axis=0)
delta=metrics['ForecastSelectedPerBuilding']-metrics['DecisionSelectedPerBuilding']
check('gerardo_share_recomputed',f'{100*delta.loc["Lamb_office_Gerardo"]/delta.sum():.2f}'=='82.44')
loo=[]
for b in metrics.index:
    m=metrics.drop(b);v=100*(1-m.DecisionSelectedPerBuilding.mean()/m.ForecastSelectedPerBuilding.mean());loo.append(v)
    if b=='Lamb_office_Gerardo':check('gerardo_omission_recomputed',f'{v:.2f}'=='3.41')
check('leave_one_range_recomputed',f'{min(loo):.2f}'=='3.41' and f'{max(loo):.2f}'=='14.22')
check('derived_not_new_experiment','模型与权重保持不变' in report_text and '固定模型与权重的留一建筑汇总' in deck_text)
check('case_post_hoc','事后选取' in report_text)
check('prior_art_cited','10.1016/j.ijforecast.2024.11.006' in report_text)
check('core_innovation_first',new.index('方法创新：用储能调度表现')<new.index('评价贡献：'))
check('pdf_core_innovation','方法创新：用储能调度表现选择预测融合权重' in report_text)
check('no_appendix_or_editing_narration',not any(t in report_text for t in ['附录','本轮','本次对齐','写作阶段','冒充']))
check('official_main_sections',all(t in report_text for t in ['1.项目背景与意义','2.技术方案与实现','3.实验结果与分析','4.创新点与应用前景','5.结论','参考文献']))
abstract=new.split('## 摘要\n\n')[1].split('\n\n关键词')[0]
check('abstract_300_500_characters',300<=len(abstract)<=500)
tex=(HERE/'technical_report_layout.tex').read_text(encoding='utf-8')
check('official_font_and_spacing',r'\documentclass[12pt,a4paper]' in tex and r'\setCJKmainfont{SimSun}' in tex and r'\linespread{1}' in tex and r'\fontsize{10.5}{20}' in tex)
check('sequential_figure_captions',re.findall(r'^\*\*图 (\d+)',new,re.M)==list(map(str,range(1,5))))
check('sequential_table_captions',re.findall(r'^\*\*表 (\d+)',new,re.M)==list(map(str,range(1,8))))
check('deck_core_innovation','方法创新' in deck_text and '选择DayWeek与LightGBM的融合权重' in deck_text)
errors=[k for k,v in checks.items() if not v]
result=dict(status='PASS' if not errors else 'FAIL',checks_passed=sum(checks.values()),checks_total=len(checks),errors=errors,checks=checks,report_pages=len(pdf),deck_pages=len(deck),new_training=False,new_dispatch=False)
if '--record' in sys.argv:
    target=HERE/'alignment_qa.json'
    content=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if not target.exists() or target.read_bytes()!=content:target.write_bytes(content)
if '--render' in sys.argv:
    render=ROOT/'tmp/provincial_review/aligned_report';render.mkdir(parents=True,exist_ok=True)
    for i,page in enumerate(pdf):page.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).save(render/f'page-{i+1:02d}.png')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
