"""Apply the user-authorized reference [2] metadata correction only."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'reports/phase13_6'
corrections=[]
for name in ['reports/phase13_5/technical_report_final.md','reports/phase13_5/technical_report_nature.md','outputs/phase12/literature_registry_frozen.csv']:
    p=ROOT/name;before=p.read_bytes()
    if name.endswith('.csv'):
        old=b'Kadir Amasyali; Nora M. El-Gohary'
        new=b'Liang Zhang; Jin Wen; Yanfei Li; Jianli Chen; Yunyang Ye; Yangyang Fu; William Livingood'
    else:
        old=b'[2] Amasyali K, El-Gohary N M.'
        new=b'[2] Zhang L, Wen J, Li Y, Chen J, Ye Y, Fu Y, Livingood W.'
    assert before.count(old)==1, name
    after=before.replace(old,new)
    p.write_bytes(after)
    corrections.append({'path':name,'old_text':old.decode(),'new_text':new.decode(),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),'bytes':len(after)})
(HERE/'reference_correction.json').write_text(json.dumps({'authorization':'User: 处理错误 (2026-09-05)','scope':'Reference [2] author metadata only; same DOI, title, year, journal and reference set','scientific_semantic_changes':0,'bibliographic_corrections':1,'files':corrections,'evidence':['qa/reference_02_crossref.json','https://pure.psu.edu/en/publications/a-review-of-machine-learning-in-building-load-prediction/']},ensure_ascii=False,indent=2),encoding='utf-8')
print(corrections[0]['after_sha256'])
