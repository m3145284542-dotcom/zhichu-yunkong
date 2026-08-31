# Phase 9 — Final Algorithm Validation & Freeze

## 1. 研究问题与错位机制

普通 forecast loss 对各时段近似等权，而削峰调度由日内最高负荷、可用 SOC 与功率约束共同决定；因此较小的平均误差不必然产生更小的 realized peak 或 regret。本阶段只验证 downstream-decision-aware sample weighting，不把它表述为新基础模型。

## 2. 冻结协议与审计

完整复用 Phase 7/8 的 8 栋建筑、24 h horizon、feature-time split、target-availability purge、31 个 causal features、逐建筑 LightGBM 参数/树数、Day/Week/DayWeek 定义、Phase 8 融合权重以及 Train-scale battery。Phase 3–8 正式产物在运行前后哈希一致。Persistence 与 Day 均为 t-24 同小时观测，是为满足历史命名而保留的数学等价别名。

## 3. Peak-aware weighting 与防泄漏

对 q∈{0.80,0.90}、alpha∈{0,0.5,1,2} 使用 `threshold=quantile(y_train,q)`；训练标签达到阈值时 weight=1+alpha，否则为 1。Validation 阈值只由 purge 后 Train target 计算；选定 q/alpha 后，最终 Test 模型阈值可由 Train+Validation final-fit labels 重算。Test 不参与阈值、配置、模型参数、融合权重、建筑或 battery 选择。

每栋建筑先最小化 Validation normalized mean regret；与最优值相差不超过 0.001 的候选视为 decision-equivalent，再依次选择更小 alpha、较低 normalized p90 regret、较低 normalized MAE 和更小 q。选择文件在任何 Test 评估前写出。

| building | q | alpha | normalized_mean_regret | normalized_MAE |
| --- | --- | --- | --- | --- |
| Hog_office_Rolando | 0.80000 | 0.00000 | 0.05664 | 0.02525 |
| Hog_office_Lavon | 0.80000 | 0.00000 | 0.01474 | 0.02373 |
| Hog_office_Joey | 0.80000 | 0.00000 | 0.08958 | 0.05436 |
| Lamb_office_Caitlin | 0.80000 | 0.00000 | 0.26602 | 0.57554 |
| Robin_office_Addie | 0.80000 | 0.00000 | 0.16224 | 0.10326 |
| Lamb_office_Gerardo | 0.80000 | 0.00000 | 0.02183 | 0.23271 |
| Hog_office_Alexis | 0.80000 | 0.00000 | 0.16745 | 0.16768 |
| Hog_office_Byron | 0.80000 | 2.00000 | 0.05572 | 0.02520 |

完整 64 行候选及 forecast/decision metrics 见 `validation_search.csv`。

## 4. Final benchmark — Forecast metrics

| method | mean_normalized_MAE | median_normalized_MAE | mean_normalized_RMSE | mean_MAPE_pct | mean_normalized_peak_region_MAE | mean_normalized_peak_region_RMSE |
| --- | --- | --- | --- | --- | --- | --- |
| Persistence | 0.22588 | 0.10344 | 0.43019 | 21.32510 | 0.36119 | 0.56510 |
| Day | 0.22588 | 0.10344 | 0.43019 | 21.32510 | 0.36119 | 0.56510 |
| Week | 0.20158 | 0.11662 | 0.32841 | 23.52301 | 0.25763 | 0.37676 |
| DayWeek | 0.18348 | 0.09345 | 0.29662 | 20.03230 | 0.26366 | 0.39456 |
| LightGBM | 0.14734 | 0.08499 | 0.21694 | 30.90449 | 0.21736 | 0.28027 |
| XGBoost | 0.14978 | 0.08838 | 0.21675 | 32.47506 | 0.21144 | 0.27044 |
| CatBoost | 0.17360 | 0.09232 | 0.23921 | 33.14073 | 0.23138 | 0.30090 |
| Phase8_DOEF | 0.13797 | 0.07970 | 0.20782 | 16.20115 | 0.20720 | 0.27346 |
| PeakAwareLightGBM | 0.14759 | 0.08499 | 0.21728 | 30.93504 | 0.21737 | 0.28045 |

按跨建筑 mean normalized MAE，最佳 forecast method 为 **Phase8_DOEF**。MAPE 对接近零负荷的建筑较敏感，因此结论优先使用 normalized MAE/RMSE。

## 5. Final benchmark — Decision metrics

| method | mean_normalized_daily_peak | median_normalized_daily_peak | mean_normalized_regret | median_normalized_regret | mean_normalized_p90_regret | mean_peak_reduction_pct |
| --- | --- | --- | --- | --- | --- | --- |
| Persistence | 1.69300 | 1.27377 | 0.16299 | 0.15011 | 0.31670 | -1.87845 |
| Day | 1.69300 | 1.27377 | 0.16299 | 0.15011 | 0.31670 | -1.87845 |
| Week | 1.67434 | 1.26132 | 0.14432 | 0.13766 | 0.27801 | 3.08546 |
| DayWeek | 1.67303 | 1.23625 | 0.14302 | 0.11259 | 0.28065 | 4.90690 |
| LightGBM | 1.64614 | 1.22346 | 0.11613 | 0.09638 | 0.20332 | 1.00843 |
| XGBoost | 1.64755 | 1.22539 | 0.11753 | 0.09268 | 0.22338 | 0.45283 |
| CatBoost | 1.64876 | 1.21984 | 0.11874 | 0.09427 | 0.21298 | -24.48242 |
| Phase8_DOEF | 1.64194 | 1.21778 | 0.11193 | 0.09412 | 0.19894 | 6.44233 |
| PeakAwareLightGBM | 1.64622 | 1.22346 | 0.11620 | 0.09638 | 0.20278 | 1.12881 |

按跨建筑 mean normalized regret，最佳 decision method 为 **Phase8_DOEF**。本次 aggregate forecast/decision 赢家一致；这不能单独证明二者总是等价。Phase 8 已在逐建筑 Validation 权重和 Test mismatch case 上验证了局部错位，因此证据支持“不具有一般等价关系”，但不声称本表的聚合赢家不同。

## 6. Peak-aware 是否提升及跨建筑稳定性

相对 LightGBM：0/7/1（win/tie/loss），mean normalized regret delta=0.000076。相对 Phase 8 DOEF：0/2/6，delta=0.004273。结论：Peak-aware **未成功**。

## 7. Bootstrap uncertainty

| comparison | point_estimate | ci95_lower | ci95_upper | probability_a_better | pairs | resamples |
| --- | --- | --- | --- | --- | --- | --- |
| Phase8_DOEF_minus_LightGBM | -0.00420 | -0.00783 | -0.00036 | 0.98340 | 240 | 10000 |
| PeakAwareLightGBM_minus_LightGBM | 0.00008 | -0.00041 | 0.00053 | 0.36690 | 240 | 10000 |
| PeakAwareLightGBM_minus_Phase8_DOEF | 0.00427 | 0.00039 | 0.00794 | 0.01520 | 240 | 10000 |

CI 基于与 Phase 8 相同的 10,000 次、seed=42、building-day paired normalized regret bootstrap，仅用于描述冻结后比较的不确定性，不参与 q/alpha 选择。

## 8. 计算开销

| method | training_time_seconds | inference_time_ms | artifact_size_bytes | test_samples |
| --- | --- | --- | --- | --- |
| CatBoost | 0.78447 | 1.36970 | 234118.12500 | 720 |
| LightGBM | 0.18421 | 2.15424 | 511175.12500 | 720 |
| PeakAwareLightGBM | 0.18232 | 2.16324 | 511999.37500 | 720 |
| Phase8_DOEF | 0.18748 | 2.34034 | 511190.12500 | 720 |
| XGBoost | 0.28488 | 2.16328 | 661718.87500 | 720 |

同一运行环境：Intel64 Family 6 Model 186 Stepping 2, GenuineIntel；Windows-10-10.0.26200-SP0；Python 3.11.9。训练用 `time.perf_counter()` 单次计时；inference 为同一 720 样本预测重复 20 次的中位耗时；artifact size 为实际模型 pickle 字节数，Ensemble 包含其 LightGBM 组件与权重元数据。它们是本机相对工程开销，不代表绝对部署性能。

## 9. 最终冻结

**Final frozen algorithm: DOEF — Decision-Oriented Ensemble Forecasting**（面向储能决策的集成负荷预测方法）。Case A：Peak-aware 未形成相对普通 LightGBM 的稳定跨建筑决策收益，按停止规则不再调参。

Phase 9 marks the end of algorithm development. 后续只进入 system prototype、visualization、technical report、presentation 与 demo；不再因为本次 Test 结果扩充 weighting function、模型、天气、深度学习、强化学习或 robust optimization。

## 10. 失败尝试、适用范围与局限

Phase 5.7 robust optimization 没有改善；Phase 6 单建筑 peak-aware 也未在 Test 优于 canonical LightGBM；本阶段按真实跨建筑结果记录 Peak-aware 的成功、部分成功或未成功，不做追加调参。最终创新点来自 causal forecasting protocol、decision-oriented validation、forecast-to-storage closed-loop evaluation、multi-building generalization 与 decision-oriented ensemble/peak-aware learning，而不是“全新 LightGBM”。

适用范围限于当前 8 栋 office、BDG2 固定时段、24 h 前预测、当前 Train-scale battery 和每日 SOC reset。Test 是单月且在历史阶段已经可见，不是项目级 pristine blind set；Phase 9 只保证它未进入本阶段配置选择。跨季节、其他建筑类型、不同电池或在线部署仍需独立验证。

## 11. 15 个验收问题的直接回答

1. 错位来自平均误差等权，而削峰取决于峰时与约束。
2. weighting 为 Train quantile 阈值上的 1+alpha。
3. 阈值、q/alpha、模型和融合均在 Test 前冻结。
4. Peak-aware：未成功。
5. 三者的最终去留：DOEF — Decision-Oriented Ensemble Forecasting。
6. forecast 最佳：Phase8_DOEF。
7. decision 最佳：Phase8_DOEF。
8. 聚合赢家一致；Phase 8 的逐建筑证据表明两类目标不具有一般等价关系。
9. 跨建筑证据见 0/2/6。
10. CI 如上，不扩大解释。
11. 开销如上表。
12. 冻结理由：Peak-aware 未形成相对普通 LightGBM 的稳定跨建筑决策收益，按停止规则不再调参。
13. 负结果包括 Phase 5.7 与未满足停止门槛的 Peak-aware 比较。
14. 范围与局限见上一节。
15. 预注册停止规则已触发算法收口，继续堆模型会引入 Test 后选择风险。

