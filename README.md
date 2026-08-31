# 智储云控

这是“基于人工智能负荷预测与优化调度的园区智能能源管理系统”的本科生竞赛项目仓库。当前已完成数据审计、单建筑 24 小时超前负荷预测、模型诊断，以及基于预测的日前储能削峰优化。

当前没有实现强化学习、Web API 或前端。

## 环境

- Windows / Linux / macOS
- Python 3.11 或更高版本
- 当前最小依赖：pandas、numpy、matplotlib

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

在 PyCharm 中，可将项目解释器设为 `.venv\Scripts\python.exe`。若 `python` 命令未指向正常的 Python 3.11+，先在 PyCharm 中选择已安装解释器，再创建虚拟环境。

## 准备官方数据

只下载项目需要的三个 BDG2 官方文件：

```powershell
python scripts\download_bdg2.py
```

目标位置：

- `data/raw/metadata.csv`
- `data/raw/weather.csv`
- `data/raw/electricity_cleaned.csv`

大文件由 Git LFS 托管。如果脚本的一次下载失败，它会停止并打印三个官方文件页面，不会循环重试。可从页面手工下载并按上述文件名放入 `data/raw/`，然后直接继续。数据说明、论文、单位和署名要求见 `docs/DATASET.md`。

## 运行审计与预处理

```powershell
python scripts\run_data_pipeline.py
python scripts\validate_processed.py
python -m unittest discover -s tests -v
```

脚本会根据真实 metadata 自动识别 Education 建筑，对候选 site 的负荷完整性、共同覆盖、零值/负值和天气覆盖进行排名。园区聚合只在所选建筑全部有读数的小时求和；任何缺失都不会当作 0，也不执行插值。

## 输出

- `reports/data_audit.md`：三个源文件的实际数据审计
- `reports/site_selection.md`：教育类 site 排名、建筑明细与自动推荐
- `reports/processed_validation.md`：连续性、负荷异常标记、天气缺失和数据泄漏检查
- `data/processed/campus_hourly.csv`：负荷与站点天气的小时级精确时间对齐结果
- `data/processed/campus_hourly_manifest.json`：源文件哈希、建筑集合、单位和处理策略
- `reports/figures/`：五张基础数据理解图

`data/raw/` 中的大型数据被 `.gitignore` 忽略；下载脚本、文档、报告、小型处理结果和必要图表可纳入版本控制。所有项目路径均由 `pathlib` 相对项目根目录解析。

## 运行第三阶段 baseline

```powershell
python src\train_baseline.py
```

该入口校验原始电力 CSV 的 SHA-256，分块筛选一栋建筑，按 feature timestamp 固定切分 train / validation / test，训练两个朴素基线与 CPU LightGBM，并将指标、预测和图表写入 `outputs/phase3/`。原始 CSV 只读且不会被修改。

## Phase 4 — Feature Engineering and LightGBM Forecasting

第四阶段继续使用 `Hog_office_Rolando` 和第三阶段的 24 小时超前预测口径、固定时间边界。输入包括日历与周期编码、过去负荷 lag（1、2、3、24、48、72、168、336 小时），以及从 `load.shift(1)` 开始计算的 3、6、24、48、168 小时滚动统计。最终特征集合由 validation 指标选择。

所有 lag 偏移均为正数；rolling 在统计前先偏移 1 小时，因此不含当前值；缺失历史和目标直接删除，不插值或用未来目标填补。模型不使用 scaler，LightGBM 只用 train 样本拟合，validation 仅用于消融、少量候选选择和 early stopping，test 在方案锁定后只评估一次。

运行：

```powershell
python scripts\run_phase4.py
```

结果位于 `outputs/phase4/`，包括 `model_comparison.csv`、`ablation_study.csv`、`test_prediction.csv`、`feature_importance.csv`、`leakage_check.txt`、`run_config.json`、`run_report.json` 和 `figures/` 下的五张图。该入口只读取 `data/raw/electricity_cleaned.csv`，并校验其 SHA-256 与第三阶段一致。

## Phase 4.5 - Model Diagnostics and Robustness

Phase 4.5 keeps `Hog_office_Rolando`, the 24-hour horizon, and all fixed feature-time boundaries. It reproduces Phase 4 exactly, then audits boundary-label availability, runs grouped feature ablations and eight lightweight parameter checks, and produces error/curve/importance diagnostics.

The audit found no future values in lag or rolling features. It did find that the final 24 labels in the historical Train and Validation windows were not yet observable at the next forecast-period start. Phase 4.5 therefore retains the evaluation windows but purges those labels during fitting and selection. Test is never used for feature or parameter selection; however, it is not a pristine blind set because Phase 3/4 test results already existed in this repository.

The final benchmark retains the 31 Phase 4 features and original parameters. Validation MAE/RMSE are 7.6363/18.5041; Test MAE/RMSE are 11.5863/17.3375. Calendar removal causes the clearest degradation. Rolling features add modest value, while short-term lag features are substantially redundant with rolling history. Parameter changes produce only small, inconsistent differences, so the Phase 4 parameter set is retained. The largest Test errors cluster around the low-load Christmas period, where the model overpredicts.

Run:

```powershell
python scripts\phase4_5_model_diagnostics.py
```

Machine-readable results and report-ready figures are written to `outputs/phase4_5/`. Phase 4.5 validates a reproducible LightGBM benchmark, but it does not show a robust improvement over the Phase 3 LightGBM or the yesterday persistence baseline on Test.

## Phase 5 — Forecast-driven Battery Peak Shaving

Phase 5 directly reuses outputs/phase4/test_prediction.csv; it does not refit LightGBM. For each target day from 2017-12-02 through 2017-12-31, Persistence, LightGBM, and Oracle forecasts independently produce a fixed 24-hour battery schedule. Only after optimization is the schedule applied to actual load for realized-peak evaluation. Oracle uses future actual load and is explicitly non-deployable.

The optimizer is a small SciPy/HiGHS MILP with binary charge/discharge mutual exclusion, 10%–90% SOC limits, 50% daily initial/terminal SOC, and 90% round-trip efficiency. Hourly load and battery power are treated as kWh per one-hour interval, numerically equal to average kW; capacity and SOC are kWh. Equivalent full cycles use one definition throughout: total discharge energy divided by nominal capacity.

Run:

    python scripts\run_phase5.py

Core metrics, 720-row Medium dispatch files, constraint audit, configuration, summary, and report-ready figures are written to outputs/phase5/. The detailed interpretation is in reports/phase5_report.md.

## Phase 5.5 — Robustness, Sensitivity, and Error Propagation

Phase 5.5 diagnoses how frozen Phase 4 forecast errors propagate into the Phase 5 peak-shaving decisions. It does not retrain LightGBM, tune on Test, change the Test dates, or redesign the battery optimizer. LightGBM reads `outputs/phase4/test_prediction.csv`; Persistence remains `actual(t-24h)`; Oracle uses actual only as a non-deployable hindsight benchmark. Every forecast-driven schedule is evaluated on realized actual load.

The analysis covers 30 daily forecast/error diagnostics, decision regret relative to Oracle, forecast-versus-decision consistency, capacity/power/round-trip-efficiency sensitivity, synthetic multiplicative forecast bias, a 10,000-resample paired daily bootstrap with seed 42, constraint audits, and three representative case studies. Decision regret is defined as `realized_peak_forecast_driven - realized_peak_oracle` in kW. Phase 5 has no price or cost objective, so Phase 5.5 does not invent an economic-regret metric.

Run:

    python scripts\run_phase5_5.py
    python -m unittest discover -s tests -v

All new data products are written to `outputs/phase5_5/`, figures to `outputs/phase5_5/figures/`, and the detailed interpretation to `reports/phase5_5_report.md`. The runner hashes and rechecks every Phase 4/5 output, reproduces the Phase 5 Medium baseline within `1e-8`, and fails if a frozen output changes or a battery constraint is violated.

## Phase 7 — Multi-Building Generalization and Decision-Value Benchmarking

Phase 7 uses only Train-period load morphology to select eight representative office buildings, retaining `Hog_office_Rolando` as the Phase 3–6 anchor. It compares the frozen Phase 6 Day-Week baseline (`weekly_weight=0.5`) with fixed-budget LightGBM, XGBoost, and CatBoost candidates under identical Phase 4.5/6 splits, purge rules, causal features, and normalized Phase 5 battery sizing.

Run the Phase 6 acceptance artifacts first, then Phase 7 and the full suite:

```powershell
python scripts\run_phase6.py
python scripts\run_phase7.py
python -m unittest discover -s tests -v
```

Formal outputs, audits, figures, and lineage metadata are written to `outputs/phase7/`; the interpretation is in `reports/phase7_report.md`. The runner fails if any tracked Phase 3–6 artifact changes, the Hog canonical reproduction drifts, or any leakage/battery constraint audit fails. No weather, MPC, reinforcement learning, robust optimization, deep learning, or Test-time tuning is used.

## Phase 8 — Decision-Oriented Ensemble

Phase 8 only combines the frozen Phase 6 Day-Week prediction and each building's frozen/canonical Phase 7 LightGBM prediction. It compares two selection protocols over the same predeclared grid `w={0.0,0.1,...,1.0}`: forecast-oriented weights minimize Validation MAE, while decision-oriented weights minimize Validation mean daily battery regret versus the non-deployable Oracle. Both building-specific and one globally shared, Train-scale-normalized weight are evaluated.

All weights and deterministic tie-break rules are frozen using Validation before Test evaluation. Every forecast enters the same Phase 7 battery configuration and optimizer, and realized peak shaving is evaluated on actual load. The stage uses no weather or future weather, performs no Test-time tuning, and does not add a model family.

Run:

```powershell
python scripts\run_phase8.py
python -m unittest discover -s tests -v
```

Formal outputs, the frozen run configuration, lineage, leakage/constraint audits, bootstrap uncertainty, and report figures are in `outputs/phase8/`; the controlled interpretation and claim boundaries are in `reports/phase8_report.md`.

## Phase 9 — Final Algorithm Validation & Freeze

Phase 9 是最后一个算法研发阶段。它不增加模型家族，只在 Phase 7/8 完全冻结的 8 栋建筑、24 小时预测、Train/Validation/Test、31 个因果特征、逐建筑 LightGBM 参数和 Train-scale battery 上验证轻量 Peak-aware sample weighting：

```text
threshold = quantile(y_fit, q)
weight = 1 + alpha  if y_fit >= threshold else 1
q ∈ {0.80, 0.90}, alpha ∈ {0, 0.5, 1, 2}
```

Validation 搜索的阈值只来自 purge 后 Train labels。每栋建筑先比较 normalized mean daily regret；与最优值相差不超过 0.001 的候选视为决策近似等价，再优先更小 alpha、较低 p90 regret、较低 MAE 和更小 q。选择文件写出后才访问 Test；最终 refit 的阈值只可来自 Train + purged Validation。Test 不参与 q/alpha、树参数、融合权重、建筑、切分或 battery 选择。

统一 benchmark 包含 Persistence、Day、Week、DayWeek、LightGBM、XGBoost、CatBoost、Phase 8 decision-oriented ensemble 和 Peak-aware LightGBM。Persistence 与 Day 都是 t-24 同小时负荷，是为保留历史口径而列出的数学等价别名。Forecast 和储能 decision metrics 均逐建筑报告，并提供跨建筑 mean/median、win/tie/loss、10,000 次 paired bootstrap 95% CI，以及 LightGBM/XGBoost/CatBoost/Ensemble/Peak-aware 的训练时间、720 样本推理时间与实际序列化模型大小。

真实结果触发 Case A：7/8 建筑在保守 Validation 规则下选择 alpha=0；冻结 Test 上 Peak-aware 相对普通 LightGBM 为 0/7/1（win/tie/loss），相对 Phase 8 ensemble 为 0/2/6。Peak-aware minus ensemble 的 mean normalized regret difference 为 +0.004273，95% CI [+0.000395, +0.007939]。因此 Peak-aware **未成功**，不进入最终算法，也不继续增加 weighting function 或调参。

**Final frozen algorithm: DOEF — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）。** DOEF 在 Test 相对普通 LightGBM 为 6/2/0，mean normalized regret difference -0.004198，95% CI [-0.007830, -0.000356]；本次 benchmark 的 mean normalized forecast MAE 和 decision regret 最优方法均为 DOEF。Phase 8 仍记录了逐建筑 forecast/decision 选择错位，因此项目结论是二者不具有一般等价关系，而不是声称每个聚合 benchmark 的赢家都必须不同。

运行与验证：

```powershell
python scripts\run_phase9.py
python -m unittest discover -s tests -v
```

正式输出在 `outputs/phase9/`，完整解释在 `reports/phase9_report.md`。后续代码必须通过 `src.final_algorithm.load_final_algorithm()` 解析 Phase 9 canonical lineage；该加载器不回退到 Phase 8 或任何中间产物。

**Phase 9 marks the end of algorithm development.** 项目之后只进入 system prototype、visualization、technical report、presentation 和 demo，不再新增预测或储能算法。
