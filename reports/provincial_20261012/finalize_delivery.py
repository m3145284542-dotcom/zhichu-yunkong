"""Register validated final materials and their current maintenance sources."""
from pathlib import Path
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for validator in ['validate_alignment.py','validate_deck.py']:
    subprocess.run([sys.executable,str(HERE/validator),'--record'],cwd=ROOT,check=True)
registry=load(ROOT/'reports/current_submission.json')
for name,artifact in [('report_visual_qa.json',registry['report']),('deck_visual_qa.json',registry['deck_pdf'])]:
    record=load(HERE/name)
    if record['status']!='PASS' or record['pdf_sha256']!=sha(ROOT/artifact):raise RuntimeError('Visual review is missing or stale: '+name)
video=load(ROOT/registry['video_manifest']);vq=load(ROOT/'outputs/demo_video/validation.json')
if video['status']!='canonical' or vq['status']!='PASS' or video['sha256']!=vq['sha256'] or sha(ROOT/registry['video'])!=vq['sha256']:raise RuntimeError('Video validation is missing or stale')
e=load(HERE/'evidence.json')
for item in e['source_artifacts']+video['sources']:
    if sha(ROOT/item['path'])!=item['sha256']:raise RuntimeError('Source changed: '+item['path'])
paths={ROOT/registry[k] for k in ['report','deck_pdf','deck_pptx','video']}
for folder in [HERE,ROOT/'outputs/demo_video']:
    paths.update(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.aux','.log','.out','.toc'] and 'qa' not in p.relative_to(folder).parts and p!=HERE/'manifest.json' and p.name!='technical_report_layout.pdf')
manifest={'schema_version':2,'status':'canonical','scope':'final technical report, defense deck and narrated video',
 'producer':'reports/provincial_20261012/finalize_delivery.py','created_utc':datetime.now(timezone.utc).isoformat(),
 'acceptance_reason':'Current content, source identities and hash-bound visual reviews passed',
 'canonical_for_scope':[registry[k] for k in ['report','deck_pdf','deck_pptx','video']],
 'source_artifacts':e['source_artifacts'],'new_experiments_run':False,
 'validation':{k:load(HERE/k)['status'] for k in ['alignment_qa.json','qa.json','report_visual_qa.json','deck_visual_qa.json']},
 'artifacts':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)],
 'limitations':['Offline fixed-eight-building evidence; no new training, field control or external competition submission.'],
 'cleanup_policy':'Only accepted deliverables, maintenance sources and required research evidence retained. Earlier tracked drafts remain in Git history.'}
(HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Registered current validated delivery.')
