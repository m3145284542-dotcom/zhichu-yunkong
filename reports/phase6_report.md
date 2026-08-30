# Phase 6 — 面向储能削峰决策的峰值感知负荷预测优化

## 1. 为什么做 Phase 6

前期复盘已经确认两个事实：第一，建筑负荷存在明显日/周规律，昨日 persistence 不应是唯一朴素参照；第二，全天 MAE 更低并不是储能削峰更好的必要条件，峰值附近的时序与排序更关键。Phase 5.7 又表明，单纯增加鲁棒优化复杂度并不会自动改善 Test。因此 Phase 6 不继续堆叠复杂控制器，而是把优化重点前移到‘对削峰决策真正有价值的预测’。

## 2. 研究问题

1. 昨日同小时与上周同小时的 Validation 决策价值如何组合，周规律是否应获得更高权重？
2. 对训练集中高负荷样本加权，并直接按 Validation 储能 realized peak 选择权重，能否提高 Test 的削峰决策价值？

## 3. 固定协议与防泄漏

- 建筑仍为 `Hog_office_Rolando`，预测任务仍为 feature time `t` 预测 `t+24h`。
- 完全沿用 Phase 4.5 的 31 个因果特征、LightGBM 参数和固定树数；不增加深度学习。
- Train 选择期标签严格 purge 到 Validation feature start 之前；Validation 选择只使用 target `< 2017-12-01 00:00:00` 的 696 小时，即 29 个完整自然日。
- 峰值阈值只由 purge 后 Train target 的 P75 计算并冻结。
- Medium battery 的容量、功率、效率、SOC 与 daily reset 完全复用 Phase 5。
- `selected_config.json` 在任何 canonical Test forecast loader 调用之前写出；Test 不参与 blend 权重或 peak multiplier 选择。
- Test 不是 pristine blind set，因为历史 Phase 3–5.7 Test 结果已经存在；Phase 6 不利用这些历史 Test 数值调参。

## 4. 日—周组合 baseline

定义 `prediction = (1-w) * yesterday + w * last_week`，候选 `w = {0, 0.25, 0.5, 0.75, 1}`。选择标准不是 MAE，而是先最小化 Validation mean daily realized peak，再依次比较 worst-10% daily peak、MAE 和较小 w。

| weekly_weight | validation_MAE | validation_RMSE | validation_MAPE | validation_bias | validation_actual_p75 | validation_peak_quartile_MAE | validation_peak_quartile_bias | validation_daily_peak_hour_MAE | validation_daily_peak_hour_exact_rate | validation_daily_top3_overlap | validation_mean_daily_peak | validation_worst_10pct_daily_peak | validation_max_realized_peak | validation_mean_peak_reduction | validation_mean_peak_reduction_pct | validation_throughput | days | selected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 11.7902 | 27.3556 | 2.6418 | -0.1782 | 451.5000 | 16.7126 | -12.5747 | 2.5517 | 0.1379 | 0.5747 | 467.7469 | 632.3937 | 815.4758 | 7.6325 | 1.5774 | 11979.5795 | 29 | False |
| 0.2500 | 10.2087 | 23.8988 | 2.2861 | -0.2647 | 451.5000 | 14.0043 | -11.5532 | 2.9310 | 0.1379 | 0.5977 | 463.4644 | 606.4422 | 815.5694 | 11.9149 | 2.4833 | 11975.2203 | 29 | False |
| 0.5000 | 9.4030 | 22.2492 | 2.1045 | -0.3513 | 451.5000 | 12.7787 | -10.5316 | 2.9310 | 0.1724 | 0.6322 | 460.0669 | 583.3775 | 815.6674 | 15.3124 | 3.2021 | 12263.7640 | 29 | True |
| 0.7500 | 9.0004 | 22.8023 | 2.0166 | -0.4379 | 451.5000 | 11.7773 | -9.5101 | 3.2069 | 0.2069 | 0.5862 | 462.3423 | 603.8135 | 815.7764 | 13.0371 | 2.6698 | 12268.8053 | 29 | False |
| 1.0000 | 9.5129 | 25.4146 | 2.1367 | -0.5244 | 451.5000 | 12.1782 | -8.4885 | 2.7931 | 0.2414 | 0.5632 | 465.9878 | 631.6012 | 815.8855 | 9.3915 | 1.8451 | 12448.4211 | 29 | False |

最终冻结 `weekly_weight=0.50`。Validation 选择了日、周等权组合，没有证据支持某一侧应占更高权重。

## 5. 峰值感知 LightGBM

以 purge 后 Train target 的 P75 作为高负荷阈值。普通样本权重为 1，高负荷样本候选权重为 `[1.0, 1.5, 2.0, 3.0]`。模型结构、特征和树数均不变，因此改变的只是训练目标对高负荷样本的重视程度。候选仍按 Validation 下游储能 realized peak 选择。

| peak_multiplier | validation_MAE | validation_RMSE | validation_MAPE | validation_bias | validation_actual_p75 | validation_peak_quartile_MAE | validation_peak_quartile_bias | validation_daily_peak_hour_MAE | validation_daily_peak_hour_exact_rate | validation_daily_top3_overlap | validation_mean_daily_peak | validation_worst_10pct_daily_peak | validation_max_realized_peak | validation_mean_peak_reduction | validation_mean_peak_reduction_pct | validation_throughput | days | train_peak_threshold | high_load_train_fraction | selected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.0000 | 7.7105 | 18.7797 | 1.7161 | 0.3361 | 451.5000 | 10.5715 | -5.9847 | 2.3448 | 0.1379 | 0.5057 | 458.4885 | 582.3757 | 812.5557 | 16.8908 | 3.5475 | 11407.7115 | 29 | 448.0000 | 0.2500 | False |
| 1.5000 | 8.2027 | 18.9290 | 1.8357 | 1.6925 | 451.5000 | 10.5244 | -5.1477 | 2.2069 | 0.2069 | 0.5402 | 458.4868 | 581.2329 | 811.6615 | 16.8925 | 3.5508 | 11153.6743 | 29 | 448.0000 | 0.2500 | False |
| 2.0000 | 8.0820 | 19.1136 | 1.8032 | 0.7440 | 451.5000 | 10.7622 | -5.1062 | 2.1034 | 0.1724 | 0.5287 | 458.3689 | 581.9330 | 812.8289 | 17.0104 | 3.5726 | 11549.0197 | 29 | 448.0000 | 0.2500 | True |
| 3.0000 | 8.1297 | 19.0266 | 1.8155 | 0.7004 | 451.5000 | 10.5394 | -5.5434 | 2.1379 | 0.1724 | 0.5172 | 458.8424 | 582.3433 | 811.5151 | 16.5369 | 3.4659 | 11554.7751 | 29 | 448.0000 | 0.2500 | False |

最终冻结 `peak_multiplier=2.00`。

## 6. Test 预测结果

| method | MAE | RMSE | MAPE | bias | actual_p75 | peak_quartile_MAE | peak_quartile_bias | daily_peak_hour_MAE | daily_peak_hour_exact_rate | daily_top3_overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Persistence | 9.8611 | 15.5434 | 2.3383 | 1.3278 | 430.0000 | 11.6557 | -6.4098 | 1.8333 | 0.3333 | 0.5778 |
| Last-week | 11.9931 | 18.3859 | 2.9509 | 8.0514 | 430.0000 | 6.8743 | 3.4973 | 1.7333 | 0.2000 | 0.4889 |
| Day-week blend (w_week=0.5) | 8.8688 | 12.5288 | 2.1525 | 4.6896 | 430.0000 | 7.2869 | -1.4563 | 1.5333 | 0.3000 | 0.5778 |
| Canonical LightGBM | 11.5863 | 17.3375 | 2.8700 | 8.6892 | 430.0000 | 5.8331 | -1.9891 | 3.6000 | 0.2333 | 0.5222 |
| Peak-aware LightGBM (m=2) | 10.1175 | 15.6025 | 2.5000 | 6.8975 | 430.0000 | 5.5300 | -1.3550 | 3.4667 | 0.2000 | 0.5000 |
| Oracle | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 430.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |

这里同时保留 MAE/RMSE 与 peak-quartile MAE、daily peak-hour error、Top-3 hour overlap，避免再次把单一 MAE 当作控制价值的代理。

## 7. Test 储能决策结果

| method | post_dispatch_peak | absolute_peak_reduction | peak_reduction_percentage | mean_daily_peak | worst_10pct_day_metric | mean_regret | p90_regret | max_regret | mean_peak_reduction | oracle_capture_ratio | throughput |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| No Battery | 483.0000 | 0.0000 | 0.0000 | 442.7333 | 481.0000 | 22.5615 | 39.8354 | 42.3850 | 0.0000 | 0.0000 | 0.0000 |
| Persistence | 466.8421 | 16.1579 | 3.3453 | 434.6032 | 461.3412 | 14.4314 | 27.0610 | 34.1278 | 8.1302 | 0.3604 | 10075.4800 |
| Last-week | 455.7577 | 27.2423 | 5.6402 | 432.2576 | 452.6653 | 12.0858 | 19.0359 | 35.2437 | 10.4757 | 0.4643 | 11409.1167 |
| Day-week blend (w_week=0.5) | 454.9101 | 28.0899 | 5.8157 | 431.6004 | 452.6436 | 11.4286 | 18.4220 | 32.1724 | 11.1329 | 0.4934 | 10560.1695 |
| Canonical LightGBM | 453.8018 | 29.1982 | 6.0452 | 431.2992 | 453.0817 | 11.1274 | 17.0718 | 28.5901 | 11.4342 | 0.5068 | 8762.3810 |
| Peak-aware LightGBM (m=2) | 452.9594 | 30.0406 | 6.2196 | 432.1349 | 452.5245 | 11.9631 | 18.2127 | 32.1534 | 10.5984 | 0.4698 | 9547.1961 |
| Oracle | 441.4493 | 41.5507 | 8.6026 | 420.1718 | 441.0068 | 0.0000 | 0.0000 | 0.0000 | 22.5615 | 1.0000 | 9570.0034 |

预先在 Validation 上冻结的峰值感知模型在 Test 未能优于 canonical LightGBM，平均日峰值反而增加 0.8358 kW；因此不能声称峰值加权带来 out-of-sample 改善。

冻结的日—周组合 Test mean daily peak 为 431.6004 kW；Yesterday Persistence 为 434.6032 kW；Last-week 为 432.2576 kW。这些 Test 结果只用于最终评价，不用于反调 weekly weight。

## 8. Canonical reproduction

Phase 6 用完全相同的 Phase 4.5 final-fit 协议重新训练未加权模型，与 canonical Test prediction 的最大绝对差为 `5.684e-14` kW。该检查用于确认 Phase 6 的唯一实验变量确实是样本加权/选择规则，而不是偷偷改变模型结构或数据切分。

## 9. 创新点如何表述

本项目可以把 Phase 6 表述为一个**面向下游储能决策价值的轻量级预测优化**：不是追求更复杂模型，而是用峰值样本加权改变预测关注区域，并直接用无泄漏 Validation 的储能 realized peak 作为模型选择指标；同时把日—周组合 baseline 纳入公平对照。这个做法可作为本科竞赛项目中的方法设计亮点，但不应声称它是学术上首次提出的全新算法。

## 10. 与 Phase 5.7 的关系

Phase 5.7 的负面结果不是废实验：它说明‘给优化器增加风险项’不足以解决问题。Phase 6 因而针对误差来源本身，尝试让预测更重视峰值决策窗口。两阶段共同支持一个更成熟的结论：复杂度不是目标，真正目标是 out-of-sample decision value。

## 11. 限制

结果仍只覆盖单建筑、单个 30 日 Test、固定 Medium battery 与 daily SOC reset。Validation 只有 29 个可用于严格选择的完整日；高负荷 P75 和候选 multiplier 都是轻量方案，并未证明跨建筑、跨季节普适。没有扩展到全 BDG2 建筑，是为了控制本科竞赛工程量并保持完整可解释的实验链。

## 12. Competition-report-safe conclusion

预先在 Validation 上冻结的峰值感知模型在 Test 未能优于 canonical LightGBM，平均日峰值反而增加 0.8358 kW；因此不能声称峰值加权带来 out-of-sample 改善。
无论结果正负，都只能描述为冻结协议下本建筑、本时间窗的实证结果；不得把 Oracle 描述为可部署方案，也不得根据 Test 结果继续反调权重。

## 13. 输出

- `validation_day_week_candidates.csv`：日—周组合 Validation 候选
- `validation_peak_weight_candidates.csv`：峰值权重 Validation 候选
- `selected_config.json`：Test 前冻结的选择记录
- `test_forecast_metrics.csv`：Test 预测与峰值时序指标
- `test_decision_metrics.csv`：Test 储能决策指标
- `test_daily_metrics.csv` / `dispatch_*.csv` / `constraint_audit.csv`：逐日、逐小时与约束证据
- `figures/`：Validation 选择曲线与 Test 案例图
