"""Validate the PPT video, its full streams, subtitles and source identity."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
FF=imageio_ffmpeg.get_ffmpeg_exe()
parser=argparse.ArgumentParser();parser.add_argument('--directory',default='outputs/demo_video');parser.add_argument('--record',action='store_true',help='Write candidate validation records after checking');args=parser.parse_args()
OUT=ROOT/args.directory;WORK=ROOT/'tmp/ppt_video_20261013/qa';WORK.mkdir(parents=True,exist_ok=True)
p=OUT/'DOEF_Demo_Narrated.mp4'
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def invoke(params):return subprocess.run([FF,*map(str,params)],capture_output=True,text=True,encoding='utf-8',errors='replace')
def seconds(s):
    h,m,t=s.replace(',','.').split(':');return 3600*int(h)+60*int(m)+float(t)
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
timeline=json.loads((OUT/'timeline.json').read_text(encoding='utf-8'))
probe=invoke(['-hide_banner','-i',p]).stderr
duration=seconds(re.search(r'Duration: ([\d:.]+)',probe)[1])
decode=invoke(['-v','error','-xerror','-i',p,'-f','null','-'])
volume=invoke(['-hide_banner','-i',p,'-vn','-af','volumedetect','-f','null','-']).stderr
mean=float(re.search(r'mean_volume: (-?[\d.]+)',volume)[1]);peak=float(re.search(r'max_volume: (-?[\d.]+)',volume)[1])
captions=[]
for block in re.split(r'\n\s*\n',(OUT/'DOEF_Demo_Narrated.srt').read_text(encoding='utf-8-sig').strip()):
    lines=block.splitlines();a,b=map(seconds,lines[1].split(' --> '));captions.append((a,b,''.join(lines[2:])))
checks={
 'mp4_container':'mov,mp4' in probe,'duration_180_to_300_seconds':180<=duration<=300,
 'size_under_300_MB':p.stat().st_size<300_000_000,'full_hd':'1920x1080' in probe,
 'h264_video':'Video: h264' in probe,'aac_audio':'Audio: aac' in probe,
 'all_streams_decode':decode.returncode==0 and not decode.stderr.strip(),
 'audible_audio':-40<mean<-5,'audio_no_full_scale_peak':peak<0,
 'source_hashes_unchanged':all(sha(ROOT/x['path'])==x['sha256'] for x in manifest['sources']),
 'artifact_identity':sha(p)==manifest['sha256'],
 'gui_source_identity':sha(ROOT/manifest['gui_source']['path'])==manifest['gui_source']['sha256'],
 'planned_duration':abs(duration-manifest['planned_duration_seconds'])<.15,
 'all_12_slides_in_order':[s['slide'] for s in timeline if s['slide']]==list(range(1,13)),
 'gui_scene_present':len([s for s in timeline if s['slide'] is None])==1,
 'subtitle_matches_narration':[x[2] for x in captions]==[t for s in timeline for t in s['sentences']],
 'subtitles_inside_video':all(0<=a<b<=duration for a,b,_ in captions),
 'subtitles_do_not_overlap':all(captions[i][1]<=captions[i+1][0] for i in range(len(captions)-1)),
 'current_deck_identity':any(x['path']=='outputs/provincial_20261012/DOEF_Provincial_Submission.pptx' for x in manifest['sources']),
}
frames=[];pixel_errors={}
for s in timeline:
    t=s['start']+min(4,s['duration']/2)
    target=WORK/f'scene{s["index"]:02}.png'
    r=invoke(['-y','-loglevel','error','-ss',t,'-i',p,'-frames:v','1',target]);assert r.returncode==0,r.stderr
    frames.append((t,target))
    if s['slide']:
        actual=Image.open(target).convert('RGB').crop((80,0,1840,990))
        original=Image.open(ROOT/'outputs/demo_video/sources'/f'slide{s["slide"]:02}.png').convert('RGB').resize((1760,990),Image.Resampling.BICUBIC)
        pixel_errors[str(s['slide'])]=sum(ImageStat.Stat(ImageChops.difference(actual,original)).mean)/3
checks['rendered_slide_matches_current_ppt']=all(v<3 for v in pixel_errors.values())
sheet=Image.new('RGB',(1920,1800),'#0b2030')
for i,(_,q) in enumerate(frames):sheet.paste(Image.open(q).resize((640,360)),((i%3)*640,(i//3)*360))
sheet.save((OUT if args.record else WORK)/'contact_sheet.jpg',quality=95)
gui=next(s for s in timeline if s['slide'] is None)
for j,dt in enumerate([1,10,20,gui['duration']-2]):
    q=WORK/f'gui{j}.png';r=invoke(['-y','-loglevel','error','-ss',gui['start']+dt,'-i',p,'-frames:v','1',q]);assert r.returncode==0
record={'status':'PASS' if all(checks.values()) else 'FAIL','sha256':sha(p),'duration_seconds':duration,'bytes':p.stat().st_size,'checks':checks,'audio_level':{'mean_db':mean,'max_db':peak},'slide_pixel_mean_absolute_error':pixel_errors,'decode_errors':decode.stderr,'visual_review_frames_seconds':[t for t,_ in frames],'note':'Visual review required before canonical promotion.'}
if args.record:
    (OUT/'validation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(record,ensure_ascii=False,indent=2));assert all(checks.values())
