"""Record the stopped production state; read-only for all upstream inputs."""
from pathlib import Path
import hashlib,json,re,subprocess,urllib.request
import fitz
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];Q=HERE/'qa'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
src=ROOT/'reports/phase13_5/technical_report_final.md'
pdf=HERE/'technical_report_candidate.pdf'
if (HERE/'technical_report_submission.pdf').exists(): (HERE/'technical_report_submission.pdf').rename(pdf)
d=fitz.open(pdf);raw=src.read_text(encoding='utf-8');full='\n'.join(p.get_text() for p in d)
norm=lambda x:re.sub(r'\s+','',x).replace('−','-').replace('｜','|')
parts=[]
for block in re.split(r'\n\s*\n',raw[raw.index('## 摘要'):]):
    if block.startswith(('#','![',r'\[')):continue
    if block.startswith('|'):
        for line in block.splitlines():
            if re.match(r'^\|\s*:?-',line):continue
            parts.extend(x.strip() for x in line.strip('|').split('|') if x.strip())
    else:parts.append(block)
checks=[]
for part in parts:
    for piece in re.split(r'\\\(.*?\\\)',part):
        t=norm(piece.replace('**','').replace('*','').replace('`',''))
        if len(t)>1:checks.append({'text':t,'found':t in norm(full).replace('-','') or t in norm(full)})
# PDF hyphenation can add a line-end hyphen in English references.
for c in checks:
    if not c['found']:c['found']=c['text'].replace('-','') in norm(full).replace('-','')
numeric=sorted(set(re.findall(r'(?<!\w)-?\d+\.\d+%?',re.sub(r'^#+.*$','',raw,flags=re.M))))
num_missing=[x for x in numeric if norm(x) not in norm(full)]
tex=(HERE/'technical_report_layout.tex').read_text(encoding='utf-8')
formula=lambda s:[re.sub(r'\s+','',x) for x in re.findall(r'\\\[(.*?)\\\]',s,re.S)]
fonts=[]
for p in d:
    for f in p.get_fonts(full=True):
        if f[0] not in [x['xref'] for x in fonts]:
            extracted=d.extract_font(f[0]);fonts.append({'xref':f[0],'name':f[3],'embedded':bool(extracted[3])})
git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
audit=json.loads((ROOT/'outputs/phase9_1/artifact_hash_audit.json').read_text(encoding='utf-8'))
frozen=[]
for a in audit['artifacts']:
    p=ROOT/a['path'];expected=a.get('after_sha256') or a['before_sha256'];data=p.read_bytes()
    frozen.append({'path':a['path'],'matches_recorded_hash':hashlib.sha256(data).hexdigest()==expected,'matches_lf_hash':hashlib.sha256(data.replace(b'\r\n',b'\n').replace(b'\r',b'\n')).hexdigest()==expected,'matches_baseline_git':git('hash-object',a['path'])==git('rev-parse','HEAD:'+a['path'])})
technical={'pdf_sha256':sha(pdf),'bytes':pdf.stat().st_size,'page_count':len(d),'page_sizes_pt':[list(p.rect) for p in d],'pdf_version':d.metadata['format'],'encrypted':d.is_encrypted,'metadata':d.metadata,'fonts':fonts,'annotations':sum(len(list(p.annots() or [])) for p in d),'links':sum(len(p.get_links()) for p in d),'bookmarks':len(d.get_toc()),'blank_pages':[i+1 for i,p in enumerate(d) if len(p.get_text().strip())<50],'local_path_leakage':bool(re.search(r'[A-Z]:[\\/]|file://',full+str(d.metadata))),'display_formula_blocks_unchanged':formula(raw)==formula(tex),'display_formula_count':len(formula(raw)),'text_segments_checked':len(checks),'text_segments_missing':[x for x in checks if not x['found']],'decimal_tokens_checked':len(numeric),'decimal_tokens_missing':num_missing,'scientific_semantic_changes':0,'frozen_artifacts':frozen,'source_sha256':sha(src),'source_bytes':src.stat().st_size,'source_blob':git('rev-parse','HEAD:reports/phase13_5/technical_report_final.md')}
(Q/'technical_audit.json').write_text(json.dumps(technical,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={'phase':'13.6','status':'BLOCKED','ready_for_next_phase':False,'producer':'Phase 13.6 layout-only XeLaTeX production','created_date':'2026-09-05','artifact_role':'technical report submission candidate; NOT approved for upload','artifact_status':'candidate','source':str(src.relative_to(ROOT)),'source_sha256':sha(src),'baseline':git('rev-parse','HEAD'),'pdf':str(pdf.relative_to(ROOT)),'pdf_sha256':sha(pdf),'blocker':'Frozen reference [2] author list does not match its DOI; STOP under user scientific-freeze rule.','team':'电协','scientific_semantic_changes':0,'reference_set_changed':False,'acceptance_reason':None}
(HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in technical.items() if k not in ['frozen_artifacts','page_sizes_pt','fonts']},ensure_ascii=False,indent=2))
