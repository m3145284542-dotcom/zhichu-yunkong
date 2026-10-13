"""Build a 12-slide narrated competition video; preserve the previous GUI capture."""
import argparse, hashlib, json, math, re, shutil, subprocess, wave
from datetime import datetime, timezone
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'tmp/video_candidate'
SOURCES = ROOT/'outputs/demo_video/sources'
WORK = ROOT/'tmp/ppt_video_20261013'
FF = imageio_ffmpeg.get_ffmpeg_exe()
DECK = 'outputs/provincial_20261012/DOEF_Provincial_Submission.pptx'
GUI = SOURCES/'gui_capture.mkv'
VOICE = 'Microsoft Huihui'
# Each sentence is synthesized intact; its WAV duration gives exact subtitle timing.
SCENES = [
(1,'作品介绍',[
'大家好，我们的作品是智储云控，面向办公建筑储能削峰。',
'下面结合答辩材料和实际界面，介绍决策导向预测融合、实现流程与实验效果。']),
(2,'背景与需求',[
'储能需要提前安排充放电，但电池容量有限。',
'预测高峰的时间出现偏差，就可能影响削峰效果。',
'因此，我们关心预测结果能否帮助电池做出更好的调度。']),
(3,'核心问题',[
'预测误差更小，并不保证储能决策更好。',
'验证集上，八栋建筑中有六栋，在两种选择目标下得到不同权重。',
'这说明评价预测时，还需要考察它带来的调度结果。']),
(4,'方法与工程贡献',[
'本项目的改进，是用储能决策效果选择预测组合。',
'在已有任务导向预测研究基础上，我们完成面向建筑储能的方法适配、统一评测和离线展示。',
'这里没有提出新的基础学习器或端到端训练方法。']),
(5,'技术实现流程',[
'首先，用历史负荷与日历特征，生成周期基线和机器学习预测。',
'随后，对两类预测加权融合，送入同一个电池优化器。',
'验证期按平均日决策后悔值选权重，测试期保持冻结。',
'后悔值衡量相对事后知道真实负荷的理想基准，还剩多少峰值差距。']),
(6,'实验设计',[
'实验固定八栋办公建筑，每栋三十个完整测试日。',
'各方法使用相同电池配置，每天初始和终止荷电状态都为百分之五十。',
'当前结果属于固定样本离线评测，尚未验证未见建筑迁移。']),
(7,'核心实验结果',[
'相对机器学习基线，平均归一化预测误差降低百分之六点三六，决策后悔值降低百分之三点六一。',
'逐楼比较为六栋改善、两栋持平。',
'这些均值先按训练期平均负荷归一化，再对八栋楼等权汇总，不能解释为电费降幅。']),
(8,'消融与样本依赖',[
'消融对照固定预测分量和优化器，只改变选权方式。',
'相对逐楼按预测误差选权，后悔值降低百分之十二点四八；相对全楼共用决策权重，降低百分之三点一七。',
'留一楼汇总显示收益幅度依赖样本。',
'这些对照来自已有结果整理，没有新增训练。']),
(9,'失效边界',[
'平均改善并不代表每一天都更好。',
'图示案例日，本方法的实际取电峰值高于按预测误差选权的方案。',
'这个案例按测试日峰差异事后选取。',
'整月最小削峰率约为负百分之一点零二，是另一个统计事实，两者不能混为原因与结果。']),
(10,'系统功能',[
'系统提供八建筑巡演、运行参数查看和综合结果比较。',
'下面播放现有程序的真实界面录像。']),
(0,'真实界面回放',[
'点击开始巡演后，界面依次切换八栋建筑。',
'灰色曲线表示无储能日峰值，蓝色是机器学习预测调度，绿色是本方法。',
'横轴为三十个调度日，纵轴为每日最大取电功率。',
'巡演支持暂停、继续和下一栋操作，结束后进入综合结果。',
'这里回放的是已保存的离线实验，不是现场实时控制。']),
(11,'应用价值',[
'当前成果可用于离线比较建筑储能方案。',
'项目保存预测、权重、电池配置和调度结果，并通过界面回放复核。',
'仿真指标不等于现场节电、电费或碳收益。']),
(12,'总结与展望',[
'智储云控将预测组合的选择，直接连接到储能削峰效果。',
'后续计划开展跨月份验证与电池参数敏感性分析，两项均未计入本次实验。',
'谢谢观看。'])]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj): Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def run(args): subprocess.run([str(a) for a in args],check=True)
def stamp(t):
    ms=round(t*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def ass_stamp(t): return f'{int(t//3600)}:{int(t//60)%60:02}:{t%60:05.2f}'
def wrapped(s):
    # Subtitle band has two 35px lines; keep each line within 44 full-width chars.
    if len(s)<=44: return s
    middle=len(s)//2
    choices=[i+1 for i,c in enumerate(s) if c in '，；：' and abs(i-middle)<14]
    cut=min(choices,key=lambda x:abs(x-middle)) if choices else middle
    return s[:cut]+'\n'+s[cut:]

def prepare():
    OUT.mkdir(parents=True,exist_ok=True); WORK.mkdir(parents=True,exist_ok=True)
    # Canonical source assets are retained; candidates stay in tmp.
    assert GUI.is_file()
    items=[]
    for i,(_,_,sentences) in enumerate(SCENES):
        for j,text in enumerate(sentences): items.append({'id':f'{i:02}_{j:02}','text':text})
    dump(OUT/'speech_input.json',items)
    print(f'Prepared {len(items)} complete sentences, {sum(len(x["text"]) for x in items)} characters',flush=True)

def build():
    OUT.mkdir(parents=True,exist_ok=True); WORK.mkdir(parents=True,exist_ok=True)
    audio=SOURCES/'audio'
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,35,&H00FFFFFF,&H00FFFFFF,&H00102030,&H00102030,0,0,0,0,100,100,0,0,1,1,0,2,65,65,15,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    timeline=[];captions=[];offset=0;segments=[]
    for i,(slide,title,sentences) in enumerate(SCENES):
        path=WORK/f'audio{i:02}.wav'; local=[]
        with wave.open(str(path),'wb') as output:
            cursor=.4
            for j,text in enumerate(sentences):
                with wave.open(str(audio/f'{i:02}_{j:02}.wav'),'rb') as source:
                    if j==0:
                        output.setparams(source.getparams());output.writeframes(b'\x00'*round(.4*source.getframerate())*source.getsampwidth()*source.getnchannels())
                    sec=source.getnframes()/source.getframerate()
                    output.writeframes(source.readframes(source.getnframes()))
                    local.append((cursor,cursor+sec,wrapped(text)));cursor+=sec
                    gap=.12
                    output.writeframes(b'\x00'*round(gap*source.getframerate())*source.getsampwidth()*source.getnchannels());cursor+=gap
            duration=math.ceil((cursor+.65)*25)/25
        sub=WORK/f'sub{i:02}.ass'
        sub.write_text(header+''.join(f'Dialogue: 0,{ass_stamp(a)},{ass_stamp(b)},Default,,0,0,0,,{t.replace(chr(10),chr(92)+"N")}\n' for a,b,t in local),encoding='utf-8-sig')
        captions.extend((offset+a,offset+b,t) for a,b,t in local)
        scene={'index':i,'slide':slide or None,'title':title,'start':offset,'duration':duration,'sentences':sentences}
        timeline.append(scene);offset+=duration
    assert 180<=offset<=298, f'Adjust script or native speech rate, planned duration={offset}'
    dump(OUT/'timeline.json',timeline)
    for scene in timeline:
        i=scene['index'];duration=scene['duration'];slide=scene['slide']
        if slide:
            inp=['-loop','1','-i',SOURCES/f'slide{slide:02}.png']
            vf='scale=1760:990,pad=1920:1080:80:0:color=0x0b2030'
        else:
            # Lossless GUI excerpt from the accepted recording.
            inp=['-t','40','-i',GUI]
            vf='crop=1920:960:0:0,pad=1920:1080:0:0:color=0x0b2030,tpad=stop_mode=clone:stop_duration=45'
        escaped=(WORK/f'sub{i:02}.ass').as_posix().replace(':','\\:')
        vf+=f",subtitles='{escaped}'"
        segment=WORK/f'scene{i:02}.mp4';segments.append(segment)
        run([FF,'-y','-loglevel','error',*inp,'-i',WORK/f'audio{i:02}.wav','-map','0:v','-map','1:a','-vf',vf,'-af','apad','-t',duration,'-r','25','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-ac','1',segment])
        print(f'Encoded {i+1}/{len(timeline)}: {scene["title"]}, {duration:.2f}s',flush=True)
    concat=WORK/'concat.txt';concat.write_text('\n'.join(f"file '{p.as_posix()}'" for p in segments),encoding='utf-8')
    target=OUT/'DOEF_Demo_Narrated.mp4'
    run([FF,'-y','-loglevel','error','-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',target])
    (OUT/'DOEF_Demo_Narrated.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{t}' for i,(a,b,t) in enumerate(captions))+'\n',encoding='utf-8-sig')
    (OUT/'narration.md').write_text('# 新版答辩 PPT 视频讲解稿\n\n'+ '\n\n'.join(f'## {s["title"]}（{stamp(s["start"])}，{s["duration"]:.2f}秒）\n\n'+''.join(s['sentences']) for s in timeline)+'\n',encoding='utf-8')
    inputs=[DECK,'outputs/provincial_20261012/DOEF_Provincial_Submission.pdf','reports/provincial_20261012/speaker_notes.json','reports/provincial_20261012/evidence.json','outputs/phase9/final_benchmark.csv','outputs/phase9_1/final_reporting_summary.json','docs/competition_rules/2026-07_AI+能源竞赛规则及作品提交要求-科技创新组.pdf','scripts/build_ppt_video_20261013.py','scripts/synthesize_ppt_video.ps1']
    inputs += [p.relative_to(ROOT).as_posix() for p in SOURCES.rglob('*') if p.is_file()]
    dump(OUT/'manifest.json',{'schema_version':2,'status':'candidate','role':'competition demonstration video based on current 12-slide defense','created_at':datetime.now(timezone.utc).isoformat(),'producer':'scripts/build_ppt_video_20261013.py','artifact':target.relative_to(ROOT).as_posix(),'sha256':sha(target),'bytes':target.stat().st_size,'planned_duration_seconds':offset,'voice':VOICE,'voice_type':'local Windows Chinese speech synthesis; not neural voice or voice clone','source_hash_normalization':'raw bytes','sources':[{'path':p,'sha256':sha(ROOT/p)} for p in inputs],'gui_source':{'path':GUI.relative_to(ROOT).as_posix(),'sha256':sha(GUI)},'gui_parent_time_range_seconds':[0,40],'slide_order':list(range(1,13)),'new_experiments':False,'narration_speedup':False,'limitations':['Online Edge TTS returned HTTP 403; Fal account lacked credit; local Chinese synthesis used.','GUI is historical actual offline experiment playback, not live control.']})
    print(f'Candidate complete: {offset:.2f} seconds, {target.stat().st_size/1e6:.2f} MB',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    prepare() if args.prepare else build()
