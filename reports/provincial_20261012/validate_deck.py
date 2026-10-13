"""Verify deck evidence, native objects and preservation of upstream artifacts."""
from pathlib import Path
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
import pymupdf

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'outputs/provincial_20261012'
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}

def main():
    e=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'))
    checks={}
    def check(name,value):
        checks[name]=bool(value)
    norm=lambda s: re.sub(r'\s+','',s).replace('−','-').replace('～','~')
    deck=OUT/'DOEF_Provincial_Submission.pptx'
    pdf=pymupdf.open(OUT/'DOEF_Provincial_Submission.pdf')
    with zipfile.ZipFile(deck) as z:
        check('zip_crc',z.testzip() is None)
        slides=sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml',n)[1]))
        check('12_slides',len(slides)==12)
        check('12_pdf_pages',len(pdf)==12)
        check('12_speaker_notes',sum(bool(re.fullmatch(r'ppt/notesSlides/notesSlide\d+.xml',n)) for n in z.namelist())==12)
        check('no_external_dependencies',not any(b'TargetMode="External"' in z.read(n) for n in z.namelist() if n.endswith('.rels')))
        native_tables={}
        for i,name in enumerate(slides,1):
            root=ET.fromstring(z.read(name))
            native_tables[i]=len(root.findall('.//a:tbl',NS))
            slide_texts=[n.text for n in root.findall('.//a:t',NS) if n.text]
            page_text=norm(pdf[i-1].get_text())
            check(f'slide_{i}_pdf_text_coverage',all(norm(t) in page_text for t in slide_texts))
            check(f'slide_{i}_renderable',len(pdf[i-1].get_pixmap().samples)>0)
        check('all_required_tables',all(native_tables[n]>=1 for n in [2,3,4,5,6,8,9,11]))
        chart_names=[n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+.xml',n)]
        check('one_native_chart',len(chart_names)==1)
        check('chart_embedded_workbook',any(n.startswith('ppt/embeddings/') and n.endswith('.xlsx') for n in z.namelist()))
        chart=ET.fromstring(z.read(chart_names[0]))
        actual=[]
        for series in chart.findall('.//c:ser',NS):
            actual.append([float(v.text) for v in series.findall('.//c:val//c:pt/c:v',NS)])
        expected=[[r[field]/r['train_mean_load'] for r in e['bootstrap_rows']] for field in ['mean_daily_regret_lightgbm','mean_daily_regret_doef']]
        check('chart_matches_saved_metrics_to_5e-10',len(actual)==2 and all(len(a)==8 and all(abs(x-y)<=5.01e-10 for x,y in zip(a,b)) for a,b in zip(actual,expected)))
        s8=norm(pdf[7].get_text())
        for row in e['ablation']:
            check('ablation_'+row['method'],f"{row['mae']:.4f}" in s8 and f"{row['regret']:.4f}" in s8)
        check('explicit_ablation_baselines',all(v in s8 for v in ['对比逐楼MAE选权','12.48%','对比全楼共用决策权重','3.17%','去掉Gerardo后仍降低3.41%']))
        definitions=norm(pdf[2].get_text())
        check('regret_is_peak_difference', '实际日峰值-同约束下Oracle理想日峰值' in definitions)
        check('oracle_boundary','已知全日实际负荷' in definitions and '事后理想参照' in definitions)
        s9=norm(pdf[8].get_text())
        case_notes=''.join(n.text or '' for n in ET.fromstring(z.read('ppt/notesSlides/notesSlide9.xml')).findall('.//a:t',NS))
        check('case_explicitly_post_hoc','事后选取' in s9 or '事后选取' in case_notes)
        check('no_preselected_case_claim','预先选定' not in ''.join(p.get_text() for p in pdf))
        check('case_daily_values',all(v in s9 for v in ['1446.77','1332.58','1380.13','1309.84','47.54']))
        check('validation_mismatch_label','验证集' in pdf[2].get_text())
        check('relative_metric_normalization_label','归一化' in pdf[6].get_text() and '归一化' in pdf[11].get_text())
    for item in e['source_artifacts']:
        check('source_unchanged_'+item['path'],hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'])
    # Screen slide text for disclosed school/teacher fields; full anonymous status
    # also relies on visual review of the existing project screenshot.
    txt=''.join(p.get_text() for p in pdf)
    check('no_appendix',not any(w in txt for w in ['附录','答疑','本轮新增','本次对齐']))
    check('cover_competition_identity','AIC-2026-27833449' in pdf[0].get_text())
    check('no_school_teacher_fields',not any(w in txt for w in ['指导教师','学校名称','南京工程学院']))
    errors=[k for k,v in checks.items() if not v]
    result=dict(status='PASS' if not errors else 'FAIL',checks_passed=sum(checks.values()),checks_total=len(checks),errors=errors,checks=checks,
        visual_review=json.loads((HERE/'deck_visual_qa.json').read_text(encoding='utf-8')),
        limitations=['No new training or battery sensitivity experiment was run.','Superseded presentation drafts are removed; scientific evidence is preserved.'])
    if '--record' in sys.argv:
        target=HERE/'qa.json'
        content=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if not target.exists() or target.read_bytes()!=content:target.write_bytes(content)
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','visual_review']},ensure_ascii=False,indent=2))
    if errors: raise SystemExit(1)

if __name__=='__main__':main()
