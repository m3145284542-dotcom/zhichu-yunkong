# 智储云控

## 基于决策导向预测融合的建筑储能削峰优化系统

全球校园人工智能算法精英大赛 · AI+能源科技创新组

参赛团队：电协 · 团队编号：AIC-2026-27833449

建筑储能的削峰效果，既取决于负荷预测精度，也取决于预测误差出现的时段。智储云控围绕这一问题，完成了负荷预测、电池调度和实际峰值评价的仿真程序，并提出决策导向预测融合方法 DOEF v1.0。

DOEF 融合 DayWeek 周期基线与 LightGBM，在验证集上按储能调度表现选择逐建筑权重。在 8 栋办公建筑的测试中，相比 LightGBM，平均归一化预测 MAE 降低 6.36%，平均归一化决策后悔值降低 3.61%。

## 最终成果

[技术报告 PDF](outputs/provincial_20261012/DOEF_Technical_Report_Submission.pdf)（16 页） · [答辩 PPTX](outputs/provincial_20261012/DOEF_Provincial_Submission.pptx) / [PDF](outputs/provincial_20261012/DOEF_Provincial_Submission.pdf)（12 页） · [中文演示视频](outputs/demo_video/DOEF_Demo_Narrated.mp4)（4 分 56 秒）

[逐页讲稿与指标说明](docs/REPORT_AND_DEFENSE_GUIDE.md) · [提交清单](docs/SUBMISSION_CHECKLIST.md) · [报告正文](reports/provincial_20261012/technical_report.md)

当前版本由 [current_submission.json](reports/current_submission.json) 指定。仓库仅保留最终交付物、维护代码及必要实验依据；旧报告、旧 PPT、重复视频和制作过程已移出当前文件树。报告与 PPT 的创新定位、消融对照、样本依赖性、负向结果及适用边界一致；视频包含当前 12 页 PPT、中文合成配音与真实离线 GUI 回放。

本地整理包运行 `python scripts/package_competition_submission.py --team-id AIC-2026-27833449 --revision final-20261013` 生成；不纳入 GitHub。网盘分享与赛事报名系统提交仍需单独完成。

## 技术方案

DayWeek 用前一日和前一周同小时负荷的平均值描述周期规律，LightGBM 利用历史负荷与日历特征拟合非线性变化。DOEF 为每栋建筑选择两者的组合比例：

`DOEF = w × LightGBM + (1 − w) × DayWeek`

候选权重为 `0.0, 0.1, …, 1.0`。每组预测进入相同的电池优化器，生成充放电计划，再根据实际负荷计算相对 Oracle 的平均日决策后悔值。验证集表现决定权重，测试期保持不变。Oracle 预先知道实际负荷，仅作为事后比较基准。

电池容量按建筑训练期平均日用电量的 10% 配置，SOC 范围为 10% 至 90%，每天初始和终止 SOC 均为 50%，往返效率为 90%。同一建筑的所有预测方法使用相同电池参数，便于比较预测对调度结果的影响。

## 实验结果

实验使用 BDG2 小时级用电数据，对 8 栋预先选定的办公建筑分别训练模型，每栋测试 30 个完整调度日，共 5,760 个小时目标。跨建筑指标先除以各建筑训练期平均负荷，再等权平均。

| 指标 | LightGBM | DOEF | 相对改善 |
| --- | ---: | ---: | ---: |
| 平均归一化 MAE | 0.147338 | 0.137970 | 6.36% |
| 平均归一化决策后悔值 | 0.116127 | 0.111929 | 3.61% |

DOEF 在 6 栋建筑上的决策后悔值低于 LightGBM，另 2 栋持平。建筑级配对 bootstrap 的平均归一化后悔值差为 −0.004198，95% 区间为 [−0.006850, −0.001719]，共重采样 10,000 次，随机种子为 42。

平均整段削峰率为 6.4423%，最小值为 −1.0170%。负值说明个别建筑仍出现反向削峰，后续需要改善异常负荷下的调度表现。完整结果见[基准表](outputs/phase9/final_benchmark.csv)和[统计汇总](outputs/phase9_1/final_reporting_summary.json)，相对改善由未舍入数值计算。

## 应用范围

本作品完成了离线仿真验证，各建筑使用自身历史训练，结果适用于本次 8 栋办公建筑及测试月份。未见建筑、其他季节和真实在线控制仍需独立验证。测试期在早期实验中已被查看，后续保持其边界固定，不用于模型或权重选择。

目前程序评价的是最大取电功率的削减，未建立电价与碳排放模型，因此不将削峰率解释为节电率、电费降幅或碳减排量。现已提供离线仿真决策支持 GUI 和只读回放接口；现场控制接入尚未实现。具体输入输出、EMS/PCS/BMS 接入职责、预测时点、执行回执与分阶段验收见[工程接入说明](docs/ENGINEERING_INTEGRATION.md)。

## 视频演示 GUI

运行 `python gui/server.py` 后，在浏览器打开 http://127.0.0.1:8765 。界面仅保留「八建筑巡演 → 综合结果」：一键约32秒自动播放八栋建筑，每栋曲线下方显示运行总览和电池配置，结束后停在综合汇总。[单文件便携版](outputs/gui_demo/DOEF_Dynamic_Demo.html) 可复制到其他电脑离线播放，也支持局域网访问。数据来自冻结实验，不重新训练或下发控制指令。详见 [GUI 使用说明](gui/README.md)。

## 环境与快速验证

模型实验使用 Python 3.11+。以下安装和运行命令均在仓库根目录执行，路径采用 Windows、Linux、macOS 均可识别的写法。

```sh
python -m venv .venv
```

激活环境：Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1`；Linux/macOS 使用 `source .venv/bin/activate`。

```sh
python -m pip install -r requirements.txt
```

依赖包含 pandas、NumPy、Matplotlib、SciPy/HiGHS、scikit-learn、LightGBM、XGBoost 和 CatBoost，版本范围见 [requirements.txt](requirements.txt)。这份文件是模型实验依赖；PDF 检查还需要 PyMuPDF，报告重排另需 XeLaTeX 及对应字体。

**只核对现有材料，无需下载原始数据或重新训练：**

```sh
python -m pip install -r requirements-delivery.txt
python scripts/validate_final_delivery.py
```

材料验证检查文稿、公式、数据表和 PPT 文本是否与源文件一致，同时核对科研文件哈希。检查结果写入 `reports/provincial_20261012/alignment_qa.json`。

## 从数据开始复现

下载脚本读取官方 BDG2 数据，将三个文件放入 `data/raw/`。原始数据较大，不纳入 Git；缺失值不按零值处理。

```sh
python scripts/download_bdg2.py
python scripts/run_data_pipeline.py
python scripts/validate_processed.py
```

初始数据流水线的教育类园区聚合属于早期探索；最终 DOEF 使用固定办公建筑，不能把 `campus_hourly.csv` 当作最终八建筑预测的替代输入。数据文件、单位与下载失败后的处理见[数据说明](docs/DATASET.md)。

完整实验路线、阶段依赖与历史产物见[实验复现说明](docs/REPRODUCING.md)。重跑阶段脚本会写入对应 `outputs/phase*/`，请在独立工作副本中复现，保留已冻结的提交材料供比较。代码回归入口：

```sh
python -m unittest discover -s tests -v
```

公开克隆不含 BDG2 原始大数据，因此只跳过一项直接对照原始电表数据的集成测试；下载数据后该项会自动执行。其余测试使用仓库中的冻结实验依据。

## 仓库导航

| 目录 | 内容 |
| --- | --- |
| `src/` | 预测、储能优化与评测实现 |
| `scripts/` | 数据下载、阶段运行、材料生成和验证入口 |
| `tests/` | 数据因果性、约束、算法与溯源回归检查 |
| `outputs/phase7/` 至 `outputs/phase9_1/` | 最终多建筑实验、冻结权重与科研证据 |
| `outputs/provincial_20261012/` | 当前报告 PDF、答辩 PPTX 与 PDF |
| `reports/provincial_20261012/` | 当前文稿、构建脚本、讲稿与材料校验 |
| `docs/competition_rules/` | 保存的比赛规则与报告参考大纲 |

数据来源见[数据说明](docs/DATASET.md)，算法定义见[DOEF 配置](outputs/phase9/final_algorithm.json)。必要研究证据保存在 phase3–9.1 目录；旧交付版本可从 Git 历史追溯，当前材料版本见[成果清单](reports/provincial_20261012/manifest.json)。
