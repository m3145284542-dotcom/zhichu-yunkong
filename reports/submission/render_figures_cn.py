"""Translate existing conceptual diagrams; preserve source structure and semantics.
Contract: explain causal train/validation/test flow with no experimental data changes.
Single-axis schematic: comparable quantitative panel alignment is not applicable.
"""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
import build_phase13_1_visual_assets as source
import matplotlib as mpl
from matplotlib.text import Text
source.OUT=HERE/'figures_cn'
translations=json.loads((HERE/'figure_translations.json').read_text(encoding='utf-8'))
original_save=source.save_pair
def save(fig,directory,stem,transparent=False):
 for t in fig.findobj(Text):
  old=t.get_text()
  t.set_text('\n'.join(translations.get(line,line) for line in old.split('\n')))
  t.set_fontfamily('Microsoft YaHei')
  if old=='frozen weight transfer':
   t.set_position((0.69,0.305));t.set_rotation(0)
  if old=='direct forecast-metric path':t.set_position((0.65,0.105))
 target=source.OUT/directory;target.mkdir(parents=True,exist_ok=True)
 fig.savefig(target/(stem+'.pdf'))
 return original_save(fig,directory,stem,transparent)
source.save_pair=save
source.configure_style();mpl.rcParams['font.family']='Microsoft YaHei';mpl.rcParams['pdf.fonttype']=42
for f in [source.architecture,source.conceptual_bridge,source.conceptual_contributions]:f()
