# Phase 13.5 核心结论追溯表

状态：PASS
原则：Phase 7/8/9/9.1 机器可读文件优先；Phase 13.0A/13.0B/13.1/13.2/13.4 用于解释、图表与比赛表述约束。未根据记忆填写数值。

| 编号 | 报告中的核心结论或定义 | 冻结证据 | 状态与边界 |
| --- | --- | --- | --- |
| C01 | 任务是 24 h 超前的小时级建筑负荷预测，并用于确定性日内储能削峰 | `outputs/phase9/final_algorithm.json`; `outputs/phase13_0b/doef_pipeline_spec.json` | 支持；不是一小时超前或在线控制 |
| C02 | BDG2 原始读数为每小时区间 kWh，调度按 1 h 区间解释为平均 kW | `outputs/phase9_1/unit_semantics.json`; `reports/phase13_4/master_project_record.md` | 支持；kW 与 kWh 未混用 |
| C03 | 1,578 条建筑序列、296 个办公候选、82 个质量通过、最终 8 栋 | `outputs/phase7/selected_buildings.json`; `outputs/phase13_4/numeric_evidence_registry.csv` | 支持 |
| C04 | 最终建筑以锚点加训练期形态最远点采样选出，验证和测试成绩未参与选楼 | `outputs/phase7/selected_buildings.json`; `outputs/phase9_1/final_reporting_summary.json` | 支持；只称多建筑稳健性，不称未见建筑迁移 |
| C05 | Train / Validation / Test 时间切分、目标可用性清除、每栋测试 720 h / 30 日 | `outputs/phase7/model_selection_config.json`; `outputs/phase9/run_config.json`; `outputs/phase9/leakage_audit.json` | 支持；测试集历史已查看，不称全新盲测 |
| C06 | Day、Week、DayWeek 定义；Persistence 与 Day 等价 | `outputs/phase9/final_benchmark.csv`; `outputs/phase9/final_algorithm.json`; `reports/phase13_4/terminology_and_naming_standard.md` | 支持 |
| C07 | LightGBM 因果特征为当前负荷、日历编码、正滞后及移位滚动统计，无未来目标或未来天气 | `outputs/phase7/model_selection_config.json`; `outputs/phase7/leakage_audit.json` | 支持；未声称天气或节假日增强 |
| C08 | 电池容量、功率、SOC、效率、每日重置与 MILP 约束 | `outputs/phase7/building_battery_configs.csv`; `src/battery/model.py`; `src/battery/optimizer.py`; `outputs/phase9/constraint_summary.json` | 支持；同一建筑内所有方法共享配置 |
| C09 | 决策后悔值为预测驱动实际日峰值减 Oracle 实际日峰值，不是货币后悔值 | `outputs/phase9_1/metric_semantics.json`; `src/phase7/evaluation.py` | 支持 |
| C10 | XGBoost 的归一化 RMSE 略低于 LightGBM，但归一化决策后悔值更高 | `outputs/phase9/final_benchmark.csv`; Phase 13.1 图 `SCI-01` | 支持；只作为项目范围内方向性反例 |
| C11 | DOEF 公式为 `w_b * LightGBM + (1-w_b) * DayWeek`，权重来自验证集下游决策后悔值 | `outputs/phase9/final_algorithm.json`; `outputs/phase8/selected_weights.csv`; `outputs/phase9_1/final_reporting_summary.json` | 支持；不是简单平均或端到端训练 |
| C12 | 8 栋中有 6 栋的预测指标权重与决策指标权重不同 | `outputs/phase8/selected_weights.csv`; `outputs/phase9_1/final_reporting_summary.json`; Phase 13.1 图 `SCI-04` | 支持 |
| C13 | DOEF 相对 LightGBM：归一化 MAE 改善 6.3585%，归一化决策后悔值改善 3.6147%，建筑级 6/2/0 | `outputs/phase9/final_benchmark.csv`; `outputs/phase9_1/final_reporting_summary.json`; Phase 13.1 图 `SCI-02/03` | 支持；比较范围为固定八建筑测试集 |
| C14 | DOEF 整段削峰率均值 6.4423%、中位数 5.6291%、最小 -1.0170%、最大 14.0162% | `outputs/phase9/final_benchmark.csv` | 支持；负值案例未删除，不外推为成本或碳收益 |
| C15 | 建筑级 bootstrap 点估计 -0.004198，95% 区间 [-0.006850, -0.001719] | `outputs/phase9_1/building_level_bootstrap_summary.json`; `outputs/phase9_1/final_reporting_summary.json` | 支持；仅描述 8 个建筑单位内不确定性，不新增显著性声明 |
| C16 | 5,760 个 DOEF 测试预测重建最大绝对差 0.0 kW | `outputs/phase9_1/doef_prediction_invariance.json` | 支持 |
| C17 | Phase 7/8/9/9.1 登记文件 76/76 哈希一致 | `outputs/phase9_1/artifact_hash_audit.json`; `outputs/phase13_4/master_evidence_manifest.json` | 支持 |
| C18 | CatBoost 极端负削峰与 Phase 5.7 稳健调度负结果保留 | `outputs/phase9_1/final_reporting_summary.json`; `outputs/phase5_7/summary.json`; `outputs/phase13_4/negative_result_registry.csv` | 支持；正文保留 CatBoost 极端值，局限性保留方法边界 |

## 跨材料控制

- 比赛表述采用 `reports/phase13_4/competition_claim_language_guide.md` 的允许、限定和禁止清单。
- 术语采用 `reports/phase13_4/terminology_and_naming_standard.md`。
- 图 1 至图 4 仅复用 Phase 13.1 图所对应的冻结数据源，中文渲染清单见 `outputs/phase13_5/figure_manifest.json`。
- 参考文献元数据来自 `outputs/phase12/literature_registry_frozen.csv`；未新增未经核验的文献。
- 未发现 `NEEDS EVIDENCE TRACE` 项。
