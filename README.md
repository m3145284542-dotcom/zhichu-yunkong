# 智储云控 · DOEF

**让负荷预测服务于储能削峰决策。** 本项目面向 AI+能源科技创新组，使用 BDG2 小时级负荷数据，将周期基线与 LightGBM 融合，以验证集上的储能决策后悔值选择权重，再在冻结测试期评价。

当前成果为 **DOEF v1.0、8 栋固定办公建筑的仿真评测、15 页技术报告与 23 页答辩 PPT**。研究对象是逐建筑预测与储能调度；尚无真实在线部署、Web API 或前端。

## 先看什么

| 目的 | 材料 |
| --- | --- |
| 阅读正式技术报告 | [技术报告 PDF](reports/phase13_6/technical_report_submission.pdf) |
| 演示与答辩 | [可编辑 PPTX](outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx) · [演示 PDF](outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pdf) |
| 快速读报告、准备讲解与答疑 | [报告导读与答辩指南](docs/REPORT_AND_DEFENSE_GUIDE.md) |
| 查看报告正文来源 | [技术报告 Markdown](reports/phase13_5/technical_report_final.md)；其封面占位字段不代表正式 PDF 的封面 |
| 核对算法和核心结果 | [最终算法](outputs/phase9/final_algorithm.json) · [基准表](outputs/phase9/final_benchmark.csv) · [最终报告口径](outputs/phase9_1/final_reporting_summary.json) |
| 了解数据来源与使用方式 | [数据说明](docs/DATASET.md) |
| 追溯各阶段实验与命令 | [开发记录](docs/DEVELOPMENT_HISTORY.md) |

PPT 第 1–12 页为主讲，第 13–23 页为答疑附录。报告 PDF 按比赛参考大纲重新组织了标题，章节编号与 Markdown 不完全相同。

材料状态分别由 [PPT 验收记录](outputs/phase13_3/acceptance_report.json)和[报告清单](reports/phase13_6/manifest.json)记录。旧 [Phase 14 审计](reports/phase14_submission_readiness_audit.md)记录的是此前的阻塞快照；当前文件导航不据此推断本次比赛审计结论，也不等同于已经上传报名系统。

## 方法与结果

对每栋建筑，`DOEF = w × LightGBM + (1 − w) × DayWeek`，其中 `DayWeek` 为前一日与前一周同小时负荷的等权平均。`w` 从 `0.0, 0.1, …, 1.0` 中按验证集平均日决策后悔值选择，并在测试前冻结。各方法共享同一建筑的电池配置和优化器，优化所得计划作用于实际负荷后再评价。

| 八建筑等权聚合指标 | LightGBM | DOEF | 相对改善 |
| --- | ---: | ---: | ---: |
| 平均归一化 MAE | 0.147338 | 0.137970 | 6.36% |
| 平均归一化决策后悔值 | 0.116127 | 0.111929 | 3.61% |

来源：[冻结基准表](outputs/phase9/final_benchmark.csv)与[最终报告口径](outputs/phase9_1/final_reporting_summary.json)。归一化使用各建筑训练期平均负荷；相对改善按未舍入值计算。

- 相对 LightGBM 的建筑级决策后悔值比较：**6 胜、2 平、0 负**。
- DOEF 平均整段削峰率 **6.4423%**，最小值 **−1.0170%**；存在反向削峰案例。
- 建筑级配对 bootstrap 的归一化后悔值差（DOEF − LightGBM）为 **−0.004198**，95% 区间 **[−0.006850, −0.001719]**，重采样 10,000 次，随机种子 42。

这些结果仅覆盖固定 8 栋办公建筑、每栋 30 个测试日。各建筑使用自身历史训练，不构成未见建筑迁移验证。测试期在早期阶段已被查看，称为“冻结的留出评价期”。削峰率不代表节电率、电费下降或碳减排；Oracle 使用未来实际负荷，仅作不可部署的事后参照。

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
python scripts/validate_phase13_3_presentation.py --pptx outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx --pdf outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pdf
python reports/phase13_6/validate_pdf.py
```

PDF 验证器会刷新 `reports/phase13_6/qa/` 下的检查结果；这不运行模型实验。版面检查仍需打开 PDF/PPT，自动检查不能替代视觉复核。验证器引用历史 Git 提交，复核时应保留完整仓库历史。

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
| `outputs/phase7/`–`outputs/phase9_1/` | 最终多建筑实验、冻结权重与科研证据 |
| `outputs/phase13_3/` | PPTX、演示 PDF 与验收记录 |
| `reports/phase13_5/`、`reports/phase13_6/` | 报告正文、正式 PDF、排版源与检查记录 |
| `docs/competition_rules/` | 保存的比赛规则与报告参考大纲 |

历史阶段记录保留其原有实验口径。解读最终结论时，以 Phase 9/9.1 的机器可读证据及正式技术报告为入口。
