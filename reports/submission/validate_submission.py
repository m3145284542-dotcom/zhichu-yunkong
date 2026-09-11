"""Verify the editorial report/deck against their sources without model reruns."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import fitz
from frozen_hashes import matches_frozen_hash

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
ERRORS = []
CHECKS = {}

def check(value, label):
    CHECKS[label] = bool(value)
    if not value:
        ERRORS.append(label)

def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')

def digest(path):
    data = (ROOT / path).read_bytes()
    if Path(path).name == '.gitignore' or Path(path).suffix.lower() in {'.md', '.py', '.mjs', '.json', '.csv', '.tex', '.txt', '.ps1', '.html', '.css'}:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()

def norm(text):
    return re.sub(r'\s+', '', text).replace('−', '-').replace('｜', '|')

def formulas(text, display):
    pattern = r'\\\[(.*?)\\\]' if display else r'\\\((.*?)\\\)'
    return [norm(x) for x in re.findall(pattern, text, re.S)]

def texts_from_slide(data):
    root = ET.fromstring(data)
    return ['\n'.join(''.join(t.text or '' for t in p.findall('.//a:t', NS))
                      for p in shape.findall('./p:txBody/a:p', NS))
            for shape in root.findall('.//p:sp', NS)
            if shape.find('./p:txBody', NS) is not None]

source = read('reports/phase13_5/technical_report_final.md')
report = read('reports/submission/technical_report.md')
expected = source
for item in json.loads(read('reports/submission/editorial_changes.json'))['changes']:
    check(expected.count(item['old']) == item['count'], 'report replacement count: ' + item['old'])
    expected = expected.replace(item['old'], item['new'])
check(expected == report, 'report matches approved editorial replacements')
body = lambda s: s[s.index('## 摘要'):]
def core_body(s):
    return re.sub(r'<!-- compliance-addition:([a-z]+):start -->.*?<!-- compliance-addition:\1:end -->', '', body(s), flags=re.S)

# Supplements are explicitly registered and checked verbatim below. Original
# scientific prose, values, tables, formulae and references remain invariant.
numeric = lambda s: Counter(re.findall(r'(?<![A-Za-z_])[-+]?\d+(?:[,.]\d+)*%?', core_body(s)))
check(numeric(source) == numeric(report), 'all report body numeric tokens unchanged')
supplements = json.loads(read('reports/submission/compliance_supplements.json'))
for key, value in supplements['blocks'].items():
    check(report.count(f'<!-- compliance-addition:{key}:start -->\n'+value+
                       f'<!-- compliance-addition:{key}:end -->') == 1,
          'registered compliance supplement: ' + key)
check([x for x in source.splitlines() if x.startswith('|')] ==
      [x for x in report.splitlines() if x.startswith('|')], 'all report table cells unchanged')
references = lambda s: s.split('## 参考文献')[1].split('## 附录')[0]
check(references(source) == references(report), 'references unchanged')
tex = read('reports/submission/technical_report_layout.tex')
for display in [True, False]:
    check(formulas(source, display) == formulas(report, display) == formulas(tex, display),
          'display formulas unchanged' if display else 'inline formulas unchanged')

pdf = fitz.open(ROOT / 'reports/submission/technical_report_submission.pdf')
def report_page_body(page):
    text=page.get_text().replace('第八届全球校园人工智能算法精英大赛·算法主题赛','')
    return re.sub(r'—\s*\d+\s*—', '', text)
full = norm('\n'.join(report_page_body(p) for p in pdf))
segments = []
for block in re.split(r'\n\s*\n', re.sub(r'<!--.*?-->\n?', '', body(report))):
    if block.startswith(('#', '![', r'\[')):
        continue
    parts = []
    if block.startswith('|'):
        for line in block.splitlines():
            if not re.match(r'^\|\s*:?-', line):
                parts.extend(x.strip() for x in line.strip('|').split('|') if x.strip())
    else:
        parts.append(block)
    for part in parts:
        for piece in re.split(r'\\\(.*?\\\)', part):
            text = norm(piece.replace('*', '').replace('`', ''))
            if len(text) > 1:
                segments.append(text)
missing = [s for s in segments if s not in full and s.replace('-', '') not in full.replace('-', '')]
check(not missing, 'report PDF preserves prose and tables')
check(len(pdf) >= 5 and (ROOT / 'reports/submission/technical_report_submission.pdf').stat().st_size <= 10_000_000,
      'report is complete and under official 10 MB limit')
check(all(norm(t) in full for t in ['总体架构设计','系统功能实现','实验环境与设置','应用流程与部署条件']),
      'report contains required architecture system environment and application coverage')
check('电协' in full and '提交前填写' not in full, 'report cover complete')
fonts = {f[0] for p in pdf for f in p.get_fonts(full=True)}
check(all(pdf.extract_font(x)[3] for x in fonts), 'report fonts embedded')
check(not pdf.is_encrypted and pdf.embfile_count() == 0, 'report is unencrypted without attachments')
check(all(not list(p.annots() or []) for p in pdf), 'report has no review annotations')
check(all(0 <= w[0] and 0 <= w[1] and w[2] <= p.rect.width + 1 and w[3] <= p.rect.height + 1
          for p in pdf for w in p.get_text('words')), 'report text within page bounds')
check(all(norm(title) in norm(pdf[number - 1].get_text()) for _, title, number in pdf.get_toc()),
      'report bookmarks target correct pages')
log = HERE / 'technical_report_layout.log'
if not log.exists():
    log = HERE / 'qa/compile_console.txt'
check(not re.search(r'Overfull|Missing character|Warning', log.read_text(encoding='utf-8', errors='replace')),
      'report has no typesetting warnings')

changes = json.loads(read('reports/submission/presentation_changes.json'))
localization = json.loads(read('reports/submission/figure_localization.json'))
old_ppt = ROOT / 'outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx'
new_ppt = ROOT / 'outputs/submission/DOEF_Competition_Presentation.pptx'
deck_pdf = fitz.open(ROOT / 'outputs/submission/DOEF_Competition_Presentation.pdf')
check(len(deck_pdf) == 23, 'presentation PDF has 23 pages')
with zipfile.ZipFile(old_ppt) as old, zipfile.ZipFile(new_ppt) as new:
    check(new.testzip() is None, 'PPTX ZIP integrity')
    slide_paths = [f'ppt/slides/slide{i}.xml' for i in range(1, 24)]
    check(len([n for n in new.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml', n)]) == 23,
          'PPTX has 23 slides')
    for i, path in enumerate(slide_paths, 1):
        original_texts = texts_from_slide(old.read(path))
        expected_texts = original_texts[:]
        for c in [c for c in changes if c['slide'] == i]:
            check(expected_texts.count(c['old']) == c.get('count', 1), f'one PPT source match: slide {i}: {c["old"]}')
            expected_texts = [c['new'] if t == c['old'] else t for t in expected_texts]
        extras = localization.get('extra_texts', {}).get(str(i), [])
        expected_texts += extras
        actual = texts_from_slide(new.read(path))
        check(Counter(actual) == Counter(expected_texts), f'PPT slide {i} exact text preservation/rewrite')
        page_text = norm(deck_pdf[i - 1].get_text())
        for text in extras:
            check(norm(text) in page_text, f'PDF localized label: slide {i}: {text}')
        # Visible editorial text must survive native PowerPoint PDF export.
        for c in [c for c in changes if c['slide'] == i]:
            check(norm(c['new']) in page_text, f'PDF contains edited text: slide {i}: {c["new"]}')
    media_hashes = lambda z: Counter(hashlib.sha256(z.read(n)).hexdigest()
                                   for n in z.namelist() if n.startswith('ppt/media/') and not n.endswith('/'))
    localization_path = HERE / 'figure_localization.json'
    if localization_path.exists():
        localization = json.loads(localization_path.read_text(encoding='utf-8'))
        registered = localization.get('media', {})
        check(set(registered).issubset(new.namelist()), 'all registered localized media present')
        for name in [n for n in new.namelist() if n.startswith('ppt/media/') and not n.endswith('/')]:
            if name in registered:
                item = registered[name]
                check(hashlib.sha256(new.read(name)).hexdigest() == item['sha256'] ==
                      hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest(),
                      'localized media identity: ' + name)
            else:
                check(name in old.namelist() and old.read(name) == new.read(name),
                      'unmodified media identity: ' + name)
    else:
        check(media_hashes(old) == media_hashes(new), 'all presentation media bytes unchanged')
    def notes_body(z, number):
        root = ET.fromstring(z.read(f'ppt/notesSlides/notesSlide{number}.xml'))
        return [''.join(t.text or '' for t in shape.findall('.//a:t', NS))
                for shape in root.findall('.//p:sp', NS)
                if not any(ph.get('type') == 'sldNum' for ph in shape.findall('.//p:ph', NS))]
    note_updates=json.loads(read('reports/submission/presentation_supplements.json'))['notes']
    check(all(notes_body(old, i) == notes_body(new, i) for i in range(1, 24) if str(i) not in note_updates),
          'unaffected speaker-note prose unchanged; slide-number placeholders excluded')
    for number, expected_note in note_updates.items():
        check(norm(expected_note) in norm(''.join(notes_body(new,int(number)))),
              'speaker note matches updated application slide: '+number)
    check(len([n for n in new.namelist() if re.fullmatch(r'ppt/notesSlides/notesSlide\d+.xml', n)]) == 23,
          '23 speaker note parts retained')
    check(not any(b'TargetMode="External"' in new.read(n) for n in new.namelist() if n.endswith('.rels')),
          'PPTX has no external relationships')
    for p in ['ppt/presentation.xml']:
        tag = '{' + NS['p'] + '}sldSz'
        check(ET.fromstring(old.read(p)).find(tag).attrib == ET.fromstring(new.read(p)).find(tag).attrib,
              'slide dimensions unchanged')

frozen = json.loads(read('outputs/phase9_1/artifact_hash_audit.json'))['artifacts']
text_identities = {x['path']: x for x in json.loads(read(
    'reports/submission/frozen_text_identity.json'))['artifacts']}
for item in frozen:
    data = (ROOT / item['path']).read_bytes()
    expected_hash = item.get('after_sha256') or item['before_sha256']
    check(matches_frozen_hash(item['path'], data, expected_hash, text_identities.get(item['path'])),
          'scientific source unchanged: ' + item['path'])

for path in ['README.md', 'docs/REPORT_AND_DEFENSE_GUIDE.md', 'reports/submission/technical_report.md']:
    for target in re.findall(r'\]\(([^)]+)\)', read(path)):
        if '://' not in target and not target.startswith('#'):
            check((ROOT / Path(path).parent / target.split('#')[0]).exists(), 'local link: ' + path + ' -> ' + target)
manifest_path = HERE / 'manifest.json'
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for item in manifest.get('artifacts', []) + manifest.get('sources', []):
        check(digest(item['path']) == item['sha256'], 'manifest identity: ' + item['path'])
else:
    check(False, 'release manifest exists')
result = {'status': 'PASS' if not ERRORS else 'FAIL', 'errors': ERRORS,
          'checks_passed': sum(CHECKS.values()), 'checks_total': len(CHECKS),
          'report_pages': len(pdf), 'report_text_segments': len(segments),
          'report_missing_segments': missing, 'presentation_pages': len(deck_pdf),
          'edited_presentation_textboxes': len(changes), 'frozen_files_checked': len(frozen),
          'checks': CHECKS}
(HERE / 'qa').mkdir(exist_ok=True)
(HERE / 'qa/validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, ensure_ascii=False, indent=2))
sys.exit(bool(ERRORS))
