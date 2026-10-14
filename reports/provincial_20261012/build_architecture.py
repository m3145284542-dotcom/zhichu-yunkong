"""Render the report architecture from the documented frozen workflow."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({'font.sans-serif':['SimHei'],'axes.unicode_minus':False,'pdf.fonttype':42})
fig,ax=plt.subplots(figsize=(7.1,3.8));ax.set(xlim=(0,10),ylim=(0,5.7));ax.axis('off')
def box(x,y,title,detail,color='#edf3f8'):
 ax.add_patch(FancyBboxPatch((x,y),2.8,1.0,boxstyle='round,pad=0.04,rounding_size=0.07',facecolor=color,edgecolor='#306486',linewidth=1))
 ax.text(x+1.4,y+.7,title,ha='center',va='center',fontsize=11,fontweight='bold',color='#163b54')
 ax.text(x+1.4,y+.29,detail,ha='center',va='center',fontsize=9.5,linespacing=1.4,color='#25323a')
def arrow(a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color='#476679',linewidth=1.1))
box(.2,4.4,'数据与因果特征','BDG2 小时负荷 / 质量控制\n按时间切分与目标可用性清除')
box(3.6,4.4,'训练期','逐建筑拟合预测器\n确定负荷尺度与电池配置')
box(7,4.4,'验证期','比较模型参数与融合权重\n按调度后悔值选权并冻结')
arrow((3.02,4.9),(3.56,4.9));arrow((6.42,4.9),(6.96,4.9))
box(.2,2.65,'留出期预测','固定模型与 DOEF 权重\n生成小时负荷预测')
box(3.6,2.65,'储能优化','预测 + 同一电池约束\n求解并冻结充放电计划')
box(7,2.65,'实际效果评价','冻结计划 + 实际负荷\n峰值 / 削峰率 / 后悔值')
arrow((3.02,3.15),(3.56,3.15));arrow((6.42,3.15),(6.96,3.15))
ax.plot([8.4,8.4,1.6],[4.36,3.98,3.98],color='#476679',linewidth=1.1);arrow((1.6,3.98),(1.6,3.69))
ax.text(5,4.06,'固定配置进入留出期，不重新选权',ha='center',fontsize=9,color='#476679')
box(.2,.55,'Oracle 理想参照','实际负荷 + 同一电池约束\n仅供事后比较，不能部署','#f6f0e7')
box(3.6,.55,'结果保存与只读展示','预测 / 权重 / 配置 / 调度结果\n本地浏览器与离线 HTML')
box(7,.55,'评价边界','历史路线保留曾参考测试\n尚需新的独立外部评价','#f6f0e7')
ax.plot([8.4,8.4,5],[2.61,2.05,2.05],color='#476679',linewidth=1.1)
arrow((5,2.05),(5,1.59))
ax.text(6.7,2.15,'评价结果归档',ha='center',fontsize=9,color='#476679')
fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.02)
fig.savefig(Path(__file__).resolve().parent/'figures/architecture.pdf')
plt.close(fig)
