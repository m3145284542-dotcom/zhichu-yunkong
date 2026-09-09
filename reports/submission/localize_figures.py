"""Localize slide figures using unchanged data, source artists and registered labels."""
from pathlib import Path
import sys,json,hashlib,zipfile,importlib.util
from lxml import etree as E
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
OUT=HERE/'figures_cn';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'))
import build_phase13_1_visual_assets as source
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.text import Text
from PIL import Image, ImageDraw, ImageFont
source.OUT=OUT
translations=json.loads((HERE/'figure_translations.json').read_text(encoding='utf-8'))
original_save=source.save_pair
def save(fig,directory,stem,transparent=False):
 for t in fig.findobj(Text):
  old=t.get_text(); new='\n'.join(translations.get(line,line) for line in old.split('\n'))
  t.set_text(new);t.set_fontfamily('Microsoft YaHei')
 target=OUT/directory;target.mkdir(exist_ok=True)
 fig.savefig(target/(stem+'.pdf'))
 return original_save(fig,directory,stem,transparent)
source.save_pair=save
source.configure_style();mpl.rcParams['font.family']='Microsoft YaHei';mpl.rcParams['pdf.fonttype']=42
for f in [source.architecture,source.conceptual_bridge,source.conceptual_contributions]:f()
def sha(b):return hashlib.sha256(b).hexdigest()
dispatch_src=ROOT/'outputs/phase8/figures/06_representative_dispatch.png'
dispatch_cn=HERE/'figures_cn/dispatch_cn.png'
im=Image.open(dispatch_src).convert('RGB'); dr=ImageDraw.Draw(im)
font_path='C:/Windows/Fonts/msyh.ttc'
font_big=ImageFont.truetype(font_path,34); font=ImageFont.truetype(font_path,16)
dr.rectangle((350,10,1450,70),fill='white'); dr.text((470,18),'代表性测试调度：Hog_office_Joey，2017-12-14',font=font_big,fill='#111111')
dr.rectangle((1430,15,1790,125),fill='white');
for y,t in [(20,'实际负荷'),(55,'按决策指标选权重'),(90,'按预测指标选权重')]:dr.text((1470,y),t,font=font,fill='#222222')
dr.rectangle((250,760,1800,900),fill='white'); dr.text((430,820),'案例用于解释调度机制；曲线和数值保持不变。',font=font,fill='#5C6873');im.save(dispatch_cn)
media={
 'image.png':'outputs/phase13_5/figures_cn/sci_01_forecast_decision_mismatch_cn.png',
 'image2.png':'reports/submission/figures_cn/presentation_assets/con_01_prediction_decision_bridge.png',
 'image3.png':'reports/submission/figures_cn/architecture/doef_architecture_master.png',
 'image4.png':'outputs/phase13_5/figures_cn/sci_02_doef_main_results_cn.png',
 'image5.png':'outputs/phase13_5/figures_cn/sci_03_multibuilding_regret_cn.png',
 'image6.png':'outputs/phase13_5/figures_cn/sci_04_validation_weight_selection_cn.png',
 'image7.png':'reports/submission/figures_cn/presentation_assets/con_02_contribution_overview.png',
 'image8.png':'reports/submission/figures_cn/architecture/doef_architecture_master.png',
 'image10.png':'outputs/phase13_5/figures_cn/sci_04_validation_weight_selection_cn.png',
 'image9.png':'reports/submission/figures_cn/dispatch_cn.png'}
# Native slide text covers only the old title/legend text; curve pixels remain intact.
# Coordinates are measured on the 2048 x 1152 preview of the original figure.
overlays=[(85,20,1880,60,'代表性负荷预测与储能调度曲线',17),
 (85,94,1890,42,'固定测试案例；保留原始曲线与数值，仅将图题和图例改为中文',9),
 (560,202,1150,38,'代表性测试调度：Hog_office_Joey，2017-12-14',9),
 (1573,255,232,24,'实际负荷',6),(1573,280,232,23,'按决策指标选权重',6),
 (1573,304,232,23,'按预测指标选权重',6),
 (85,1062,1960,50,'案例用于解释调度机制，不代表普遍性能；沿用预先固定案例，未重新选择。',8)]
slide3_overlays=[(480,28,1090,42,'从负荷预测到储能决策评价',15),
                 (660,650,800,34,'概念示意：同时评价预测质量与下游储能决策价值',9)]
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
def overlay(i,v):
 x,y,w,h,text,sz=v
 x=751840+x/2048*7640320;y=1609344+y/1152*4297680;w=w/2048*7640320;h=h/1152*4297680
 s=E.fromstring(f'''<p:sp xmlns:p="{ns['p']}" xmlns:a="{ns['a']}"><p:nvSpPr><p:cNvPr id="{1000+i}" name="CN_FIGURE_{i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr lIns="0" rIns="0" tIns="0" bIns="0" anchor="ctr"/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="{sz*100}"><a:solidFill><a:srgbClr val="18212B"/></a:solidFill><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/></a:rPr><a:t/></a:r></a:p></p:txBody></p:sp>''')
 s.find('.//a:t',ns).text=text;return s
p=ROOT/'outputs/submission/DOEF_Competition_Presentation.pptx'
with zipfile.ZipFile(p) as z: entries=[(i,z.read(i.filename)) for i in z.infolist()]
with zipfile.ZipFile(p,'w') as z:
 for info,b in entries:
  if info.filename.startswith('ppt/media/') and Path(info.filename).name in media:b=(ROOT/media[Path(info.filename).name]).read_bytes()
  if info.filename in ('ppt/slides/slide3.xml','ppt/slides/slide19.xml'):
   r=E.fromstring(b); tree=r.find('.//p:spTree',ns)
   for s in list(tree):
    n=s.find('p:nvSpPr/p:cNvPr',ns)
    if n is not None and n.get('name','').startswith('CN_FIGURE_'): tree.remove(s)
   b=E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
  z.writestr(info,b)
record={'status':'candidate','producer':'reports/submission/localize_figures.py','scope':'Chinese figure labels; original data and curve pixels retained','media':{f'ppt/media/{k}':{'path':v,'sha256':sha((ROOT/v).read_bytes())} for k,v in media.items()},'extra_texts':{'19':[v[4] for v in overlays]}}
(HERE/'figure_localization.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Localized 9 image parts and the preserved dispatch figure labels.')
