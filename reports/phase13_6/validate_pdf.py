"""Read-only acceptance checks on scientific sources; writes only Phase 13.6 QA."""
from pathlib import Path
import hashlib,json,re,subprocess,csv,xml.etree.ElementTree as ET
import fitz
R=Path(__file__).resolve().parents[2]; H=R/'reports/phase13_6';Q=H/'qa'
BASE='4a72c23d4b735e5679c900c6d06160faba2bc866'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
git=lambda *a:subprocess.check_output(['git',*a],cwd=R).strip()
source=R/'reports/phase13_5/technical_report_final.md';raw=source.read_text(encoding='utf-8')
pdf=H/'technical_report_submission.pdf';d=fitz.open(pdf)
full='\n'.join(p.get_text() for p in d);(Q/'extracted_text.txt').write_text(full,encoding='utf-8')
norm=lambda s:re.sub(r'\s+','',s).replace('−','-').replace('｜','|')
errors=[]
def check(ok,label):
    if not ok:errors.append(label)
parts=[]
for block in re.split(r'\n\s*\n',raw[raw.index('## 摘要'):]):
    if block.startswith(('#','![',r'\[')):continue
    if block.startswith('|'):
        for line in block.splitlines():
            if re.match(r'^\|\s*:?-',line):continue
            parts.extend(x.strip() for x in line.strip('|').split('|') if x.strip())
    else:parts.append(block)
segments=[]
for part in parts:
    for piece in re.split(r'\\\(.*?\\\)',part):
        t=norm(piece.replace('**','').replace('*','').replace('`',''))
        if len(t)>1:segments.append({'text':t,'found':t in norm(full) or t.replace('-','') in norm(full).replace('-','')})
check(all(x['found'] for x in segments),'prose/table preservation')
numbers=sorted(set(re.findall(r'(?<!\w)-?\d+\.\d+%?',re.sub(r'^#+.*$','',raw,flags=re.M))))
missing=[x for x in numbers if norm(x) not in norm(full)];check(not missing,'decimal token preservation')
tex=(H/'technical_report_layout.tex').read_text(encoding='utf-8')
math=lambda s,display:[re.sub(r'\s+','',x) for x in re.findall(r'\\\[(.*?)\\\]' if display else r'\\\((.*?)\\\)',s,re.S)]
check(math(raw,True)==math(tex,True),'display equations unchanged')
check(math(raw,False)==math(tex,False),'inline equations unchanged')
correction=json.loads((H/'reference_correction.json').read_text(encoding='utf-8'))
for c in correction['files']:
    original=git('show',BASE+':'+c['path']).replace(b'\r\n',b'\n')
    actual=(R/c['path']).read_bytes().replace(b'\r\n',b'\n').strip()
    check(original.replace(c['old_text'].encode(),c['new_text'].encode())==actual,'only authorized reference edit '+c['path'])
frozen=[]
for a in json.loads((R/'outputs/phase9_1/artifact_hash_audit.json').read_text(encoding='utf-8'))['artifacts']:
    p=R/a['path'];data=p.read_bytes();expected=a.get('after_sha256') or a['before_sha256']
    same=git('hash-object',a['path'])==git('rev-parse',BASE+':'+a['path'])
    hashok=sha(p)==expected or hashlib.sha256(data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')).hexdigest()==expected
    check(same and hashok,'frozen '+a['path']);frozen.append({'path':a['path'],'baseline_blob_unchanged':same,'registered_hash_matches':hashok})
protected=git('diff','--name-only',BASE,'--','outputs/phase7','outputs/phase8','outputs/phase9','outputs/phase9_1','src')
check(not protected,'all protected paths unchanged')
fonts={}
for p in d:
    for f in p.get_fonts(full=True):fonts[f[0]]={'name':f[3],'embedded':bool(d.extract_font(f[0])[3])}
check(all(f['embedded'] for f in fonts.values()),'fonts embedded')
check(not d.is_encrypted,'unencrypted');check(pdf.stat().st_size<10_000_000,'file size')
annots=sum(len(list(p.annots() or [])) for p in d);check(annots==0,'no review annotations')
check(d.embfile_count()==0,'no embedded attachments')
check(not re.search(r'[A-Z]:[\\/]|file://',full+str(d.metadata)),'local paths')
check('提交前填写' not in full and 'Amasyali' not in full,'no obsolete draft placeholders')
check(not any(s['type']==3 for p in d for s in p.get_texttrace()),'no invisible text')
check(not d.get_ocgs(),'no optional hidden layers')
blanks=[];bounds=[];links=[];pagination=[]
for i,p in enumerate(d):
    check(abs(p.rect.width-595.276)<0.1 and abs(p.rect.height-841.89)<0.1,'A4 page '+str(i+1))
    if len(p.get_text().strip())<50:blanks.append(i+1)
    for w in p.get_text('words'):
        if w[0]<0 or w[1]<0 or w[2]>p.rect.width+1 or w[3]>p.rect.height+1:bounds.append([i+1,w])
    for l in p.get_links():
        links.append({'page':i+1,'kind':l['kind'],'target_page':l.get('page')})
        check(l['kind'] in (1,4) and 0<=l['page']<len(d),'valid internal link')
    pagination.append(str(i+1) in p.get_text(clip=fitz.Rect(200,780,395,820)))
check(not blanks,'no blank pages');check(not bounds,'text within page bounds');check(all(pagination),'page numbering')
for level,title,pageno in d.get_toc():check(norm(title) in norm(d[pageno-1].get_text()),'bookmark destination '+title)
log=(H/'technical_report_layout.log').read_text(encoding='utf-8',errors='replace') if (H/'technical_report_layout.log').exists() else (Q/'xelatex.log').read_text(encoding='utf-8',errors='replace')
warnings=re.findall(r'^.*(?:Overfull|Missing character|Warning).*$' ,log,re.M);check(not warnings,'no typesetting warnings')
# Reversing the three presentation edits must recover the entire frozen SVG byte-for-byte.
svg=(H/'assets/figure_04_layout.svg').read_text(encoding='utf-8')
original=(R/'outputs/phase13_5/figures_cn/sci_04_validation_weight_selection_cn.svg').read_text(encoding='utf-8')
check(svg.replace('height="708pt"','height="648pt"').replace('viewBox="0 0 1152 708"','viewBox="0 0 1152 648"').replace('<g id="legend_1" transform="translate(-350 145)">','<g id="legend_1">')==original,'SVG chart geometry and values unchanged')
def table(n):
    block=raw.split('**表 '+str(n)+'｜')[1].split('\n\n')[1]
    return [[x.strip() for x in line.strip('|').split('|')] for line in block.splitlines()[2:]]
readcsv=lambda name:list(csv.DictReader((R/name).open(encoding='utf-8')))
bench={x['display_name']:x for x in readcsv('outputs/phase9/final_benchmark.csv')}
agg={x['method']:x for x in readcsv('outputs/phase9/aggregate_metrics.csv')}
weights={x['building']:x for x in readcsv('outputs/phase8/selected_weights.csv')}
for row in table(4):
    w=weights[row[0]];check(row[1:]==[f"{float(w[k]):.1f}" for k in ['w_forecast','w_decision']],'table4 '+row[0])
for row in table(5):
    b=bench[row[0]];a=agg[b['internal_method']]
    check(row[1:]==[f"{float(b['normalized_mae_mean']):.6f}",f"{float(b['normalized_rmse_mean']):.6f}",f"{float(a['mean_MAPE_pct']):.2f}"],'table5 '+row[0])
summary=json.loads((R/'outputs/phase9_1/final_reporting_summary.json').read_text(encoding='utf-8'))
check(summary['final_algorithm']['algorithm_selection_source']=='Validation' and summary['final_algorithm']['test_role']=='evaluation_only' and not summary['final_algorithm']['test_can_promote_algorithm'],'Validation/Test claims')
check(summary['evaluation_scope']['not_unseen_building_transfer'],'scope claim')
check(summary['doef_prediction_invariance']['samples']==5760 and summary['doef_prediction_invariance']['max_absolute_delta']==0,'dispatch reuse evidence')
check(summary['doef_vs_lightgbm']['decision_regret_win_tie_loss']=={'wins':6,'ties':2,'losses':0},'win tie loss')
for k in ['normalized_mae_relative_improvement_pct','normalized_regret_relative_improvement_pct']:
    check(f"{summary['doef_vs_lightgbm'][k]:.4f}%" in raw,'relative improvement '+k)
for k in ['point_estimate','ci95_lower','ci95_upper']:check(f"{summary['building_level_bootstrap'][k]:.6f}" in raw,'bootstrap '+k)
for k in ['mean','median','min','max']:check(f"{float(bench['DOEF']['peak_reduction_'+k+'_pct']):.4f}%" in raw,'peak '+k)
check(float(bench['XGBoost']['normalized_rmse_mean'])<float(bench['LightGBM']['normalized_rmse_mean']) and float(bench['XGBoost']['normalized_decision_regret_mean'])>float(bench['LightGBM']['normalized_decision_regret_mean']),'forecast not decision counterexample')
bc=readcsv('outputs/phase7/building_battery_configs.csv')
for b in bc:
    for k,v in [('capacity_fraction_of_mean_daily_energy',.1),('soc_min_fraction',.1),('soc_max_fraction',.9),('initial_soc_fraction',.5),('terminal_soc_fraction',.5),('round_trip_efficiency',.9)]:check(abs(float(b[k])-v)<1e-12,'battery '+k)
    check(abs(float(b['max_charge_power'])/float(b['capacity'])-.25)<1e-12,'battery power')
    check(b['daily_reset']=='True','daily reset')
neg=(R/'outputs/phase5_7/summary.json').read_text(encoding='utf-8');check('20.463518670505014' in neg and '11.127371928531804' in neg and '20.4635' in raw and '11.1274' in raw,'negative robustness result')
check(not any(x in full for x in ['行业领先','首次提出','显著优于所有方法','全面优于','国际领先']),'no inflated claims')
refnums=re.findall(r'^\[(\d+)\]',raw,re.M);check(refnums==[str(i) for i in range(1,12)],'references contiguous')
abstract=raw.split('## 摘要')[1].split('关键词：')[0]
wordcount=len(re.findall(r'[\u4e00-\u9fff]|[A-Za-z0-9]+(?:[.%-][A-Za-z0-9]+)*',abstract));check(300<=wordcount<=500,'abstract word count')
result={'status':'PASS' if not errors else 'FAIL','errors':errors,'pdf_sha256':sha(pdf),'bytes':pdf.stat().st_size,'pages':len(d),'page_size_pt':list(d[0].rect),'version':d.metadata['format'],'metadata':d.metadata,'fonts':list(fonts.values()),'review_annotations':annots,'links':links,'bookmarks':d.get_toc(),'blank_pages':blanks,'out_of_page_text':bounds,'typesetting_warnings':warnings,'source_sha256':sha(source),'source_bytes':source.stat().st_size,'source_blob':git('hash-object',str(source)).decode(),'source_baseline_blob':git('rev-parse',BASE+':reports/phase13_5/technical_report_final.md').decode(),'text_segments':len(segments),'missing_segments':[s for s in segments if not s['found']],'numeric_tokens':len(numbers),'numeric_missing':missing,'display_equations':len(math(raw,True)),'inline_equations':len(math(raw,False)),'scientific_semantic_changes':0,'bibliographic_corrections':1,'abstract_word_count':wordcount,'abstract_CJK_characters':len(re.findall(r'[\u4e00-\u9fff]',abstract)),'protected_files':frozen}
(Q/'technical_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['status','errors','pdf_sha256','bytes','pages','source_sha256','text_segments','numeric_tokens','display_equations','inline_equations','abstract_word_count']},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
