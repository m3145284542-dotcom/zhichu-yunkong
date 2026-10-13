"""Fail-closed verification of the final public repository snapshot."""
from pathlib import Path
import hashlib, json, subprocess, sys, zipfile, re
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def main():
    current=load('reports/current_submission.json');release=load(current['manifest'])
    if current['status']!='canonical' or release['status']!='canonical':raise RuntimeError('Release is not canonical')
    records={x['path']:x for x in release['artifacts']}
    for k in ['report','deck_pdf','deck_pptx','video']:
        if current[k] not in release['canonical_for_scope'] or current[k] not in records:raise RuntimeError('Missing role: '+k)
    for x in release['artifacts']+release['source_artifacts']:
        if sha(x['path'])!=x['sha256']:raise RuntimeError('Missing or changed release artifact: '+x['path'])
    for script in [current['validator'],'reports/provincial_20261012/validate_deck.py']:
        subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,check=True)
    vm=load(current['video_manifest']);vq=load('outputs/demo_video/validation.json')
    if not (vm['status']=='canonical' and vq['status']=='PASS' and sha(current['video'])==vm['sha256']==vq['sha256']):raise RuntimeError('Video validation is stale')
    for x in vm['sources']:
        if sha(x['path'])!=x['sha256']:raise RuntimeError('Video source mismatch: '+x['path'])
    with zipfile.ZipFile(ROOT/current['deck_pptx']) as z:
        for n in z.namelist():
            if n.startswith('ppt/notesSlides/') and n.endswith('.xml'):
                for p in re.findall(r'(?:reports|outputs|src|gui|docs)/[^\s<>]+?\.(?:md|json|csv|py|png)',z.read(n).decode('utf-8')):
                    if not (ROOT/p).is_file():raise RuntimeError('Broken PPT note source: '+p)
    for p in ['outputs/submission','reports/submission','outputs/demo_video/history','outputs/demo_video_ppt_20261013']:
        if (ROOT/p).exists():raise RuntimeError('Superseded delivery remains: '+p)
    print(json.dumps({'status':'PASS','registered_artifacts':len(records),'research_sources':len(release['source_artifacts']),'video_sources':len(vm['sources'])}))
if __name__=='__main__':main()
