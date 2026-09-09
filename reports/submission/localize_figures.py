"""Localize slide figures using unchanged data, source artists and registered labels."""
from pathlib import Path
import argparse,json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
OUT=HERE/'figures_cn';OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
media={
 'image.png':'outputs/phase13_5/figures_cn/sci_01_forecast_decision_mismatch_cn.png',
 'image2.png':'reports/submission/figures_cn/presentation_assets/con_01_prediction_decision_bridge.png',
 'image3.png':'reports/submission/figures_cn/architecture/doef_architecture_master.png',
 'image4.png':'outputs/phase13_5/figures_cn/sci_02_doef_main_results_cn.png',
 'image5.png':'outputs/phase13_5/figures_cn/sci_03_multibuilding_regret_cn.png',
 'image6.png':'reports/phase13_6/assets/figure_04_layout.png',
 'image7.png':'reports/submission/figures_cn/presentation_assets/con_02_contribution_overview.png',
 'image8.png':'reports/submission/figures_cn/architecture/doef_architecture_master.png',
 'image10.png':'reports/phase13_6/assets/figure_04_layout.png',
 'image9.png':'outputs/phase8/figures/06_representative_dispatch.png'}
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pptx', type=Path, default=ROOT/'outputs/submission/DOEF_Competition_Presentation.pptx')
p=parser.parse_args().pptx
with zipfile.ZipFile(p) as z: entries=[(i,z.read(i.filename)) for i in z.infolist()]
with zipfile.ZipFile(p,'w') as z:
 for info,b in entries:
  if info.filename.startswith('ppt/media/') and Path(info.filename).name in media:b=(ROOT/media[Path(info.filename).name]).read_bytes()
  z.writestr(info,b)
record={'status':'candidate','producer':'reports/submission/localize_figures.py','scope':'Chinese figure labels; original data and curve pixels retained','media':{f'ppt/media/{k}':{'path':v,'sha256':sha((ROOT/v).read_bytes())} for k,v in media.items()},'extra_texts':{'19':['代表性测试调度：Hog_office_Joey，2017-12-14','实际负荷','决策选权重','预测选权重']}}
(HERE/'figure_localization.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Registered 10 image parts; original dispatch image retained with native Chinese labels.')
