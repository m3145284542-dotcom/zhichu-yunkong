"""Build a narrated MP4 from frozen evidence and actual GUI capture."""
import asyncio, hashlib, json, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/demo_video'
WORK = ROOT/'tmp/demo_video'
FF = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = 'zh-CN-XiaoxiaoNeural'

def source_hash(path):
    """Text evidence is invariant to Git's Windows newline conversion."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
# title, seconds, narration, screen bullets
SCENES = [
('智储云控',18,'大家好，这是智储云控。我们关注一个具体问题：怎样让人工智能的负荷预测，真正帮助建筑储能降低用电峰值？接下来，用四分半展示作品功能、实现流程和实验效果。',['让负荷预测服务于储能削峰决策','DOEF v1.0  ·  电协团队','功能演示 / 实现流程 / 应用效果']),
('为什么预测更准，还不够？',24,'储能削峰，需要提前安排电池什么时候充电、什么时候放电。但预测误差出现的时间，同样重要。即使平均误差更小，如果错过关键峰值，也可能做出较差的调度。因此，我们不仅评价预测准不准，还直接评价预测带来的储能决策。',['预测负荷 → 安排充放电 → 评价实际峰值','关键问题：误差是否出现在峰值时段？','评价预测，也评价预测产生的决策']),
('从历史数据到调度评价',28,'实现流程分为四步。首先，读取建筑小时级用电数据，构造历史负荷和日历特征。接着，分别生成周期基线与机器学习预测。然后，把预测送入同一个电池优化器，求出充放电计划。最后，使用实际负荷评价调度后的峰值。本次实验固定八栋办公建筑，每栋测试三十个完整调度日。',['01  BDG2 小时级数据 → 历史负荷与日历特征','02  DayWeek 周期基线 + LightGBM 预测','03  统一电池优化器 → 充放电计划','04  实际负荷 → 调度后峰值与决策后悔值']),
('DOEF：按决策表现选择权重',26,'核心方法叫作决策导向集成预测。它将周期基线与机器学习预测进行加权组合。我们为每栋建筑，在验证集上比较不同权重的储能调度表现，选出决策后悔值更低的组合。这里的后悔值，表示相对预先知道实际负荷的理想基准，还存在多少峰值差距。权重选定后，在测试期保持冻结。',['DOEF = w × LightGBM + (1 − w) × DayWeek','候选权重：0.0、0.1、…、1.0','验证集：按平均日决策后悔值选择','测试集：权重冻结；Oracle 仅作事后基准']),
('统一电池约束，公平比较',24,'为了公平比较，同一栋建筑的各预测方法使用相同电池配置。电池容量按训练期平均日用电量的百分之十设置。荷电状态限制在百分之十到九十之间，每天开始和结束都保持百分之五十，往返效率为百分之九十。这样，可以比较预测方法本身对调度结果的影响。',['容量：训练期平均日用电量的 10%','SOC：10%–90%','每日初始 / 终止 SOC：50% / 50%','往返效率：90%']),
('真实界面 · 八建筑动态巡演',38,'现在进入作品的实际演示界面。点击开始巡演，系统依次展示八栋建筑。灰色曲线是无储能日峰值，蓝色对应机器学习预测调度，绿色对应我们的集成方法。横轴是三十个调度日，纵轴是每日最大取电功率。曲线下方同步显示当前建筑的运行总览和电池配置。巡演期间支持暂停、继续和切换下一栋，结束后自动进入综合结果。这里回放的是已经完成的离线实验，不是现场实时控制。',[]),
('综合结果：预测与决策同时评价',24,'巡演结束后，可以查看逐建筑结果及整体比较。相对机器学习基线，八栋建筑的平均归一化预测误差降低百分之六点三六，平均归一化决策后悔值降低百分之三点六一。归一化时，先除以各建筑训练期平均负荷，再对八栋建筑等权平均，避免大建筑单独主导结果。',[]),
('应用效果，也保留负向结果',24,'从建筑数量看，六栋建筑的决策后悔值有所改善，两栋持平。平均整段削峰率约为百分之六点四四。但最小值约为负百分之一点零二，说明个别建筑仍出现反向削峰。我们保留这些结果，因为它们提醒我们，异常负荷下的调度仍需改进。削峰率不能直接理解为节电率或电费降幅。',['6 栋改善 / 2 栋持平','平均整段削峰率：6.4423%','最小整段削峰率：−1.0170%','限定：固定八建筑测试；存在反向削峰']),
('运行与复核',20,'使用时，在项目目录运行演示服务，用浏览器打开本地地址，即可开始巡演。也可以直接打开单文件离线演示。项目提供算法代码、实验结果、技术报告和答辩材料，便于复核。当前成果用于办公建筑储能方案的离线分析，真实设备接入和跨季节效果，还需要进一步验证。',['python gui/server.py','浏览器打开 127.0.0.1:8765 → 开始巡演','便携版：DOEF_Dynamic_Demo.html','可复核：算法代码 / 冻结实验 / 报告 / 答辩材料']),
('让预测服务于决策',14,'智储云控把负荷预测、储能调度和实际效果评价连接起来。我们希望用可复核的实验，推动人工智能从预测数值，走向改善决策。以上就是本次作品演示，谢谢观看。',['负荷预测 → 储能调度 → 实际效果评价','智储云控 · DOEF v1.0','离线仿真验证 · 可复核实验']),
]
# Preserve the original neural voice cadence rather than speeding up narration.
SCENES = [(title, seconds, text, lines) for (title, _, text, lines), seconds in
          zip(SCENES, [18,24,30,30,27,40,28,30,28,18])]
TOTAL_SECONDS = sum(s[1] for s in SCENES)

def run(args):
    subprocess.run([str(x) for x in args],check=True,stdout=subprocess.DEVNULL)

def font(n,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('msyhbd.ttc' if bold else 'msyh.ttc'),n)

def card(i,title,lines):
    im=Image.new('RGB',(1920,1080),'#0b2030'); d=ImageDraw.Draw(im)
    d.rectangle((0,0,1920,12),fill='#4cd8be')
    d.text((105,78),'智储云控  /  DOEF DEMONSTRATION',font=font(27),fill='#74d9c8')
    d.text((105,170),title,font=font(72,True),fill='white')
    d.text((108,277),['作品概览','问题场景','实现流程','核心方法','电池约束','功能演示','实验结果','应用效果','运行方式','结束'][i],font=font(27),fill='#9bb7c8')
    for j,line in enumerate(lines):
        y=375+j*110
        d.rounded_rectangle((105,y,1815,y+86),radius=16,fill='#17394a')
        d.rectangle((105,y+22,111,y+64),fill='#4cd8be')
        d.text((145,y+17),line,font=font(34),fill='#edf6fa')
    d.text((108,880),'BDG2  ·  固定八栋办公建筑  ·  离线仿真验证',font=font(25),fill='#95adbe')
    p=WORK/f'card{i}.png'; im.save(p); return p

async def speech(i,text):
    path=WORK/f'voice{i}.mp3'; events=[]
    comm=edge_tts.Communicate(text,VOICE,rate='+0%',boundary='WordBoundary')
    with path.open('wb') as f:
        async for chunk in comm.stream():
            if chunk['type']=='audio':f.write(chunk['data'])
            elif chunk['type']=='WordBoundary':events.append(chunk)
    (WORK/f'voice{i}.json').write_text(json.dumps(events,ensure_ascii=False),encoding='utf-8')
    (WORK/f'voice{i}.txt').write_text(text,encoding='utf-8')
    return events

async def capture():
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        ctx=await browser.new_context(viewport={'width':1920,'height':960},record_video_dir=str(WORK/'capture'),record_video_size={'width':1920,'height':960},device_scale_factor=1)
        page=await ctx.new_page(); await page.goto((ROOT/'outputs/gui_demo/DOEF_Dynamic_Demo.html').as_uri())
        await page.locator('#replay-chart svg').wait_for()
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(WORK/'gui-start.png'))
        await page.locator('#tour').click()
        await page.wait_for_timeout(35000)
        await page.screenshot(path=str(WORK/'gui-summary.png'))
        video=page.video; await ctx.close()
        await video.save_as(str(WORK/'gui-tour.webm'))
        await browser.close()

def ass_time(t):
    h=int(t//3600);m=int(t//60)%60;s=t%60
    return f'{h}:{m:02d}:{s:05.2f}'

async def main():
    OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    if not (WORK/'gui-tour.webm').exists(): await capture()
    for i,(_,_,text,_) in enumerate(SCENES):
        if not (WORK/f'voice{i}.json').exists() or not (WORK/f'voice{i}.txt').exists() or (WORK/f'voice{i}.txt').read_text(encoding='utf-8') != text:
            await speech(i,text)
        print(f'Voice {i+1}/10 ready',flush=True)
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,38,&H00FFFFFF,&H00FFFFFF,&H00102030,&H00102030,0,0,0,0,100,100,0,0,1,1,0,2,65,65,35,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    all_srt=[];offset=0
    for i,(title,duration,narration,lines) in enumerate(SCENES):
        ev=json.loads((WORK/f'voice{i}.json').read_text(encoding='utf-8'))
        audio_end=max((e['offset']+e['duration'])/1e7 for e in ev)
        speed=max(1,audio_end/(duration-1.5))
        groups=[];buf='';start=0;end=0;cursor=0
        for e in ev:
            if not buf:start=e['offset']/1e7/speed+.5
            token=e['text']
            found=narration.find(token,cursor)
            if found>=0:
                cursor=found+len(token)
                while cursor<len(narration) and narration[cursor] in '，。！？：；、':
                    token+=narration[cursor];cursor+=1
            buf+=token;end=(e['offset']+e['duration'])/1e7/speed+.5
            if len(buf)>=24 or buf[-1:] in '。！？；' or (buf[-1:] in '，：' and len(buf)>=8):
                groups.append((start,end,buf));buf=''
        if buf:groups.append((start,end,buf))
        ass=header
        for start,end,txt in groups:
            ass+=f'Dialogue: 0,{ass_time(start)},{ass_time(min(end+.12,duration))},Default,,0,0,0,,{txt}\n'
            all_srt.append((offset+start,offset+min(end+.12,duration),txt))
        sub=WORK/f'sub{i}.ass';sub.write_text(ass,encoding='utf-8-sig')
        if i==5: inp=['-i',WORK/'gui-tour.webm'];vf='scale=1920:960,pad=1920:1080:0:0:color=0x0b2030,tpad=stop_mode=clone:stop_duration=40'
        elif i==6:inp=['-loop','1','-i',WORK/'gui-summary.png'];vf='scale=1920:960,pad=1920:1080:0:0:color=0x0b2030'
        else:inp=['-loop','1','-i',card(i,title,lines)];vf='null'
        escaped=str(sub).replace('\\','/').replace(':','\\:')
        vf+=f",subtitles='{escaped}',drawbox=x=0:y=1072:w=iw:h=8:color=0x224655:t=fill,drawbox=x=0:y=1072:w={int(1920*(offset+duration)/TOTAL_SECONDS)}:h=8:color=0x4cd8be:t=fill"
        run([FF,'-y','-loglevel','error',*inp,'-i',WORK/f'voice{i}.mp3','-vf',vf,'-af',f'atempo={speed},adelay=500|500,apad','-t',duration,'-r','25','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-movflags','+faststart',WORK/f'scene{i}.mp4'])
        offset+=duration;print(f'Encoded {i+1}/10; voice speed {speed:.3f}',flush=True)
    concat=WORK/'concat.txt';concat.write_text('\n'.join(f"file '{(WORK/f'scene{i}.mp4').as_posix()}'" for i in range(10)),encoding='utf-8')
    target=OUT/'DOEF_Demo_Narrated.mp4'
    run([FF,'-y','-loglevel','error','-f','concat','-safe','0','-i',concat,'-c','copy','-movflags','+faststart',target])
    def srt_time(t):
        ms=round(t*1000)
        return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    (OUT/'DOEF_Demo_Narrated.srt').write_text('\n\n'.join(f'{j+1}\n{srt_time(a)} --> {srt_time(b)}\n{t}' for j,(a,b,t) in enumerate(all_srt)),encoding='utf-8-sig')
    (OUT/'narration.md').write_text('# 智储云控演示视频讲解稿\n\n'+'\n\n'.join(f'## {title}（{secs} 秒）\n\n{text}' for title,secs,text,_ in SCENES),encoding='utf-8')
    manifest={'status':'candidate','role':'competition demonstration video','created_at':datetime.now(timezone.utc).isoformat(),'producer':'scripts/build_demo_video.py','artifact':target.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'planned_duration_seconds':TOTAL_SECONDS,'voice':VOICE,'voice_type':'neural synthesized Chinese narration','source_hash_normalization':'CRLF to LF; MP4 identity uses raw bytes','sources':[{'path':p,'sha256':source_hash(ROOT/p)} for p in ['outputs/gui_demo/DOEF_Dynamic_Demo.html','outputs/gui_demo/manifest.json','outputs/phase9/final_benchmark.csv','outputs/phase9_1/final_reporting_summary.json','scripts/build_demo_video.py']]}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(target,flush=True)

if __name__=='__main__':asyncio.run(main())
