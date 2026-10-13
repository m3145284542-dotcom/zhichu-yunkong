"""Draw report-only scientific figures directly from saved experimental CSVs."""
from pathlib import Path
import hashlib, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'sans-serif', 'font.sans-serif':['Microsoft YaHei', 'Arial'],
 'font.size':10, 'axes.labelsize':10, 'legend.fontsize':10, 'pdf.fonttype':42,
 'ps.fonttype':42, 'svg.fonttype':'none', 'axes.unicode_minus':False,
 'axes.spines.top':False, 'axes.spines.right':False})
sources=['outputs/phase9/final_benchmark.csv','outputs/phase8/selected_weights.csv',
         'outputs/phase9_1/building_level_bootstrap.csv']
benchmark, weights, buildings=[pd.read_csv(ROOT / p) for p in sources]
blue, orange='#2166AC','#B35A16'

def canvas(height=82):
    fig, ax=plt.subplots(figsize=(154/25.4,height/25.4))
    fig.subplots_adjust(left=.18,right=.97,bottom=.20,top=.85)
    ax.set_axisbelow(True)
    return fig,ax

def save(fig,name,data):
    fig.canvas.draw()
    fig.savefig(OUT / f'{name}.pdf',facecolor='white')
    fig.savefig(OUT / f'{name}.svg',facecolor='white')
    fig.savefig(OUT / f'{name}.png',dpi=600,facecolor='white')
    data.to_csv(OUT / f'{name}.csv',index=False)
    plt.close(fig)

def grouped(name,methods,columns,labels):
    data=benchmark.set_index('display_name').loc[methods,columns]
    fig,ax=canvas()
    x=np.arange(len(columns))
    for i,method in enumerate(methods):
        bars=ax.bar(x+(i-.5)*.30,data.loc[method],.28,label=method,
                    color=[blue,orange][i],edgecolor='white',linewidth=.5)
        ax.bar_label(bars,fmt='%.6f',padding=4,fontsize=9)
    ax.set_xticks(x,labels)
    ax.set_ylabel('八建筑等权均值（无量纲）')
    ax.set_ylim(0,float(data.max().max())*1.30)
    ax.legend(loc='lower center',bbox_to_anchor=(.5,1.02),ncol=2,frameon=False)
    save(fig,name,data.reset_index())

grouped('mismatch',['LightGBM','XGBoost'],
        ['normalized_rmse_mean','normalized_decision_regret_mean'],['归一化 RMSE','归一化决策后悔值'])
grouped('main_results',['LightGBM','DOEF'],
        ['normalized_mae_mean','normalized_decision_regret_mean'],['归一化 MAE','归一化决策后悔值'])

def paired(name,data,a,b,labels,xlabel,xlim=None):
    fig,ax=canvas(92)
    y=np.arange(len(data))
    ax.hlines(y,data[a],data[b],color='#999999',linewidth=1)
    ax.scatter(data[a],y,marker='o',s=44,facecolors='white',edgecolors=blue,label=labels[0],zorder=3)
    ax.scatter(data[b],y,marker='x',s=36,color=orange,label=labels[1],zorder=4)
    ax.set_yticks(y,[s.rsplit('_',1)[-1] for s in data.building])
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    if xlim:ax.set_xlim(*xlim)
    else:ax.set_xlim(left=0)
    ax.grid(axis='x',color='#DDDDDD',linewidth=.5)
    ax.legend(loc='lower center',bbox_to_anchor=(.45,1.04),ncol=2,frameon=False)
    save(fig,name,data)

paired('weights',weights[['building','w_forecast','w_decision']], 'w_forecast','w_decision',
       ['按 MAE 选权','按后悔值选权'],'LightGBM 融合权重 w（DayWeek 权重为 1−w）',(-.035,1.035))
buildings['LightGBM']=buildings.mean_daily_regret_lightgbm/buildings.train_mean_load
buildings['DOEF']=buildings.mean_daily_regret_doef/buildings.train_mean_load
assert np.allclose(buildings.DOEF-buildings.LightGBM, buildings.normalized_difference)
paired('buildings',buildings[['building','LightGBM','DOEF']], 'LightGBM','DOEF',
       ['LightGBM','DOEF'],'归一化决策后悔值（无量纲）')
(OUT/'source_manifest.json').write_text(json.dumps({'sources':[
 {'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sources],
 'producer':'reports/provincial_20261012/render_report_figures.py',
 'new_experiments':False,'panel_alignment':'not applicable: one axes per figure'},indent=2),encoding='utf-8')
print('Rendered four data-derived figures.')
