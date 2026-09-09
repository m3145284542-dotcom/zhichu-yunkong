"""Validate the delivered MP4, decode all streams, and extract review frames."""
import hashlib, importlib.util, json, re, subprocess
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('video',Path(__file__).with_name('build_demo_video.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
p=v.OUT/'DOEF_Demo_Narrated.mp4'
probe=subprocess.run([v.FF,'-hide_banner','-i',str(p)],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
m=re.search(r'Duration: (\d+):(\d+):([\d.]+)',probe)
duration=int(m[1])*3600+int(m[2])*60+float(m[3])
decode=subprocess.run([v.FF,'-v','error','-xerror','-i',str(p),'-f','null','-'],capture_output=True,text=True)
audio=subprocess.run([v.FF,'-hide_banner','-i',str(p),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
checks={'mp4_container':'mov,mp4' in probe,'duration_180_to_300_seconds':180<=duration<=300,
        'size_under_300_MB':p.stat().st_size<300_000_000,'full_hd':'1920x1080' in probe,
        'h264_video':'Video: h264' in probe,'aac_audio':'Audio: aac' in probe,
        'all_streams_decode':decode.returncode==0 and not decode.stderr.strip(),
        'audible_audio':bool(re.search(r'mean_volume: -?\d+\.\d+ dB',audio))}
manifest=json.loads((v.OUT/'manifest.json').read_text(encoding='utf-8'))
checks['source_hashes_unchanged']=all(v.source_hash(v.ROOT/x['path'])==x['sha256'] for x in manifest['sources'])
checks['artifact_identity']=hashlib.sha256(p.read_bytes()).hexdigest()==manifest['sha256']
offsets=[8,26,52,80,109,143,160,175,207,238,260]
sheet=Image.new('RGB',(1920,1440),'#0b2030')
for j,t in enumerate(offsets):
    q=v.WORK/f'qa{j}.png'
    v.run([v.FF,'-y','-loglevel','error','-ss',t,'-i',p,'-frames:v','1',q])
    sheet.paste(Image.open(q).resize((640,360)),((j%3)*640,(j//3)*360))
sheet.save(v.OUT/'contact_sheet.jpg')
record={'status':'PASS' if all(checks.values()) else 'FAIL','duration_seconds':duration,'bytes':p.stat().st_size,
        'checks':checks,'audio_level':re.findall(r'(?:mean|max)_volume: [^\n]+',audio),'decode_errors':decode.stderr,
        'visual_review_frames_seconds':offsets,'note':'Contact sheet requires visual review before canonical promotion.'}
(v.OUT/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
assert all(checks.values())
