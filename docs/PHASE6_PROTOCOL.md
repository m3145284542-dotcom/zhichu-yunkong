# Phase 6 Protocol — 决策感知预测与项目级优化

## 1. 阶段目标

Phase 6 的目标不是继续堆叠模型复杂度，而是修正 Phase 3–5.7 暴露出的核心错配：通用预测误差（MAE/RMSE）与储能削峰的实际决策价值并不完全一致。

本阶段保留 Phase 3–5.7 的全部历史结果，不覆盖旧输出；Phase 5.7 的鲁棒优化负结果继续作为正式结论保留。

## 2. 已知背景与限制

Phase 6 的方案设计发生在 Phase 3–5.7 已经分析过 2017-12 Test 之后，因此该 Test 不能再被描述为“从未见过的 blind Test”。本阶段能保证的是：

- 下述候选集合与选择规则在 Phase 6 Test 运行前固定；
- Phase 6 不使用 Test 指标选择候选、调权或修改参数；
- 如 Test 不改善，保留负结果，不进行 Test 后反调。

真正的外部泛化仍需后续增加新建筑、新时间窗口或新的独立数据。

## 3. 固定数据与血缘

- 建筑：`Hog_office_Rolando`
- 预测 horizon：24 h
- 特征：沿用 Phase 4.5 的 31 个因果特征
- 原始数据 SHA-256：沿用 Phase 3/4 固定值
- Train/Validation/Test feature-time 边界：沿用 Phase 4.5
- 候选选择只允许使用 `target_timestamp < 2017-12-01 00:00:00` 的 Validation 标签
- Test 对照预测必须通过 `load_canonical_test_forecast()` 读取 Phase 4.5 canonical artifact
- 电池：沿用 Phase 5 frozen Medium 配置；不根据 Phase 6 Test 改容量、功率、效率或 SOC 约束

## 4. 强 baseline

昨日与上周同小时组合：

`forecast = (1-w) * yesterday + w * last_week`

固定候选周权重：

`w ∈ {0.00, 0.25, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00}`

选择顺序：

1. Validation realized mean daily peak 最小；
2. Validation worst-10% daily peak 最小；
3. Validation top-quartile-load MAE 最小；
4. 名称确定性破同分。

## 5. 峰值感知 LightGBM

保留 Phase 4.5 特征和基础参数，只改变训练样本权重。固定候选：

| candidate | peak threshold | peak sample weight |
| --- | --- | ---: |
| uniform | none | 1.0 |
| q80_x1_5 | Train target P80 | 1.5 |
| q80_x2 | Train target P80 | 2.0 |
| q90_x2 | Train target P90 | 2.0 |
| q90_x3 | Train target P90 | 3.0 |

阈值只能由训练标签计算。每个候选的 early stopping 仅使用 Validation。

模型选择顺序：

1. Validation realized mean daily peak 最小；
2. Validation worst-10% daily peak 最小；
3. Validation top-quartile-load MAE 最小；
4. candidate 名称确定性破同分。

选定后，使用该候选的 `best_iteration` 在 Test 开始前可用的 Train + Validation 标签上重新拟合；之后只生成一次 Phase 6 Test 预测。

## 6. Test 固定对照

预测层：

- Yesterday persistence
- Last-week persistence
- Validation-selected blended persistence
- Phase 4.5 canonical LightGBM
- Phase 6 peak-aware LightGBM
- Oracle（仅 hindsight upper bound）

决策层另加：

- No Battery

## 7. 固定指标

预测指标：

- MAE
- RMSE
- MAPE
- top-quartile-load MAE
- daily peak MAE
- peak-hour MAE
- peak-hour hit within ±1 h

储能决策指标：

- mean daily realized peak（主指标）
- worst-10% daily realized peak
- max daily realized peak
- mean peak reduction
- mean / P90 / max decision regret vs Oracle
- total battery throughput

## 8. 结论规则

- 只有 Phase 6 peak-aware LightGBM 的 Test realized mean daily peak 低于 Phase 4.5 canonical LightGBM，才能声称“Phase 6 改善了主削峰指标”。
- 全局 MAE/RMSE 改善但削峰不改善，不得声称控制性能提升。
- 削峰改善但 MAE/RMSE不改善，可以表述为“误差结构对下游决策更有利”，但必须同时报告通用预测指标。
- 强 baseline 若优于 Phase 6 LightGBM，必须如实报告；不得弱化或删除该 baseline。
- Phase 5.7 的鲁棒优化失败不得因 Phase 6 结果被删除或改写成成功。
- 禁止根据 Phase 6 Test 结果调整上述候选网格或选择规则。

## 9. 工程验收

Phase 6 合入主分支前必须：

1. 全量单元测试通过；
2. LightGBM 4.x 训练接口可复现；
3. Phase 6 不修改 `outputs/phase3` 至 `outputs/phase5_7`；
4. 生成 `outputs/phase6/selected_config.json`、选择表、预测/决策指标、逐日结果与 `reports/phase6_report.md`；
5. 报告明确 Test 已被历史阶段观察过，不宣称全新 blind Test。
