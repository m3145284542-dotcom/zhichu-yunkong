# 智储云控

## 面向储能削峰的决策导向负荷预测

全球校园人工智能算法精英大赛 · AI+能源科技创新组

参赛团队：电协

建筑储能的削峰效果，既取决于负荷预测精度，也取决于预测误差出现的时段。智储云控围绕这一问题，完成了负荷预测、电池调度和实际峰值评价的仿真程序，并提出决策导向集成预测方法 DOEF v1.0。

DOEF 融合 DayWeek 周期基线与 LightGBM，在验证集上按储能调度表现选择逐建筑权重。在 8 栋办公建筑的测试中，相比 LightGBM，平均归一化预测 MAE 降低 6.36%，平均归一化决策后悔值降低 3.61%。

## 参赛成果

[技术报告](reports/submission/technical_report_submission.pdf) · [答辩 PPT](outputs/submission/DOEF_Competition_Presentation.pptx) · [演示 PDF](outputs/submission/DOEF_Competition_Presentation.pdf) · [答辩讲稿与资料索引](docs/REPORT_AND_DEFENSE_GUIDE.md)

作品包含 DOEF 算法实现、多建筑对比实验、储能调度程序、技术报告和答辩材料。PPT 共 23 页，其中第 1 至 12 页为主讲，第 13 至 23 页为补充实验与方法说明。报告的[Markdown 正文](reports/submission/technical_report.md)与 PDF 同步维护。

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

目前程序评价的是最大取电功率的削减，未建立电价与碳排放模型，因此不将削峰率解释为节电率、电费降幅或碳减排量。Web API、前端及现场控制接入尚未实现。

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
python -m pip install PyMuPDF
python reports/submission/validate_submission.py
```

材料验证检查文稿、公式、数据表和 PPT 文本是否与源文件一致，同时核对科研文件哈希。检查结果写入 `reports/submission/qa/validation.json`。

## 从数据开始复现

下载脚本读取官方 BDG2 数据，将三个文件放入 `data/raw/`。原始数据较大，不纳入 Git；缺失值不按零值处理。

```sh
python scripts/download_bdg2.py
python scripts/run_data_pipeline.py
python scripts/validate_processed.py
```

初始数据流水线的教育类园区聚合属于早期探索；最终 DOEF 使用固定办公建筑，不能把 `campus_hourly.csv` 当作最终八建筑预测的替代输入。数据文件、单位与下载失败后的处理见[数据说明](docs/DATASET.md)。

完整实验路线、阶段依赖与历史产物见[开发记录](docs/DEVELOPMENT_HISTORY.md)。重跑阶段脚本会写入对应 `outputs/phase*/`，请在独立工作副本中复现，保留已冻结的提交材料供比较。代码回归入口：

```sh
python -m unittest discover -s tests -v
```

## 仓库导航

| 目录 | 内容 |
| --- | --- |
| `src/` | 预测、储能优化与评测实现 |
| `scripts/` | 数据下载、阶段运行、材料生成和验证入口 |
| `tests/` | 数据因果性、约束、算法与溯源回归检查 |
| `outputs/phase7/` 至 `outputs/phase9_1/` | 最终多建筑实验、冻结权重与科研证据 |
| `outputs/submission/` | 当前答辩 PPTX 与演示 PDF |
| `reports/submission/` | 当前技术报告、排版源与材料验证 |
| `docs/competition_rules/` | 保存的比赛规则与报告参考大纲 |

数据来源见[数据说明](docs/DATASET.md)，算法定义见[DOEF 配置](outputs/phase9/final_algorithm.json)。历史实验、原版材料及验收记录保存在各阶段目录中，当前材料版本见[成果清单](reports/submission/manifest.json)。
