# Phase 8 — 决策导向的预测融合与严格对照验证

## 1. Motivation

本阶段检验：按 Validation 预测误差选择的线性融合权重，是否等价于按下游储能削峰决策价值选择的权重。贡献是把 frozen battery decision value 显式用于融合权重选择并与传统 MAE 导向选择做受控比较；普通加权平均本身不是新算法。

## 2. Frozen protocol

固定 Phase 7 的 8 栋 office、24h horizon、Train/Validation/Test、target-availability purge、31 个 causal features、Day-Week weekly weight=0.5、逐建筑 frozen LightGBM configuration 与 Train-scale battery。无天气、未来天气、MPC、强化学习、深度学习或 Test-time tuning。Phase 7 未保存逐时预测，因此按其冻结配置确定性复现；端点指标与 Phase 7 正式指标核验通过后才接受本阶段结果。

## 3. Ensemble definition

`prediction = w * LightGBM + (1-w) * DayWeek`，预注册 `w={0.0,0.1,...,1.0}`。w=0/1 分别严格复现 Day-Week/LightGBM。

## 4. Forecast-oriented selection

只在 Validation 按 MAE、RMSE、距 endpoint 的距离、较小 w 的固定顺序选择。

## 5. Decision-oriented selection

同一 Validation grid 中，每个预测均进入同一 frozen battery optimizer，并在 actual load 上评价 realized result。按 mean daily regret vs Oracle、p90 regret、MAE、距 endpoint 的距离、较小 w 选择；Oracle 仅为不可部署 hindsight upper bound。

## 6. Building-specific results

| building | w_forecast | w_decision | weights_differ | validation_MAE_decision_minus_forecast | validation_regret_decision_minus_forecast | validation_MAE_decision_rank_spearman |
| --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Rolando | 0.90000 | 0.70000 | True | 0.04685 | -0.06347 | 0.95455 |
| Hog_office_Lavon | 0.00000 | 0.00000 | False | 0.00000 | 0.00000 | 1.00000 |
| Hog_office_Joey | 0.60000 | 0.30000 | True | 2.98481 | -2.18077 | 0.06364 |
| Lamb_office_Caitlin | 0.40000 | 0.80000 | True | 1.23842 | -1.01795 | -0.54545 |
| Robin_office_Addie | 1.00000 | 1.00000 | False | 0.00000 | 0.00000 | 1.00000 |
| Lamb_office_Gerardo | 0.00000 | 1.00000 | True | 0.30743 | -0.06511 | -1.00000 |
| Hog_office_Alexis | 0.60000 | 0.70000 | True | 0.04978 | -0.01523 | 0.38182 |
| Hog_office_Byron | 0.90000 | 0.80000 | True | 1.48855 | -0.61012 | 0.92727 |

8 栋中 6/8 的 forecast/decision 权重不同。Test 上 decision-oriented 相对 prediction-oriented：改善 5 栋、退化 1 栋、持平 2 栋。

## 7. Global-weight robustness

共享 forecast weight=0.5；共享 decision weight=0.8。聚合先用 Phase 7 Train mean load 逐建筑归一化，再对 8 栋等权平均。

| method | building_count | mean_normalized_MAE | median_normalized_MAE | mean_normalized_RMSE | mean_normalized_peak_quartile_MAE | mean_bias_kw | mean_daily_peak_hour_MAE | mean_daily_peak_hour_exact_rate | mean_daily_top3_overlap | mean_daily_realized_peak_kw | mean_normalized_daily_realized_peak | mean_worst_10pct_daily_peak_kw | mean_normalized_worst_10pct_daily_peak | mean_regret_vs_oracle_kw | mean_normalized_regret | mean_p90_regret_kw | mean_normalized_p90_regret | mean_max_regret_kw | mean_oracle_capture_ratio | mean_equivalent_full_cycles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DayWeek | 8 | 0.18348 | 0.09345 | 0.29662 | 0.26366 | -2.87829 | 3.44583 | 0.21667 | 0.47361 | 367.05980 | 1.67303 | 420.54981 | 2.50897 | 20.22017 | 0.14302 | 38.73759 | 0.28065 | 49.12444 | -0.44680 | 12.05379 |
| LightGBM | 8 | 0.14734 | 0.08499 | 0.21694 | 0.21736 | -4.60657 | 3.91250 | 0.20833 | 0.42361 | 365.64009 | 1.64614 | 419.00673 | 2.49639 | 18.80047 | 0.11613 | 33.15104 | 0.20332 | 51.92190 | -0.16483 | 11.31174 |
| ForecastSelectedPerBuilding | 8 | 0.16830 | 0.08061 | 0.26947 | 0.24540 | -4.87860 | 3.68333 | 0.21250 | 0.45972 | 364.49058 | 1.65790 | 417.73943 | 2.48491 | 17.65095 | 0.12789 | 30.76012 | 0.24367 | 50.87350 | -0.19683 | 11.34861 |
| DecisionSelectedPerBuilding | 8 | 0.13797 | 0.07970 | 0.20782 | 0.20720 | -4.62367 | 3.63333 | 0.22500 | 0.46528 | 364.39797 | 1.64194 | 417.51965 | 2.48207 | 17.55835 | 0.11193 | 29.01110 | 0.19894 | 51.07889 | -0.09112 | 11.15132 |
| ForecastSelectedGlobal | 8 | 0.15179 | 0.08146 | 0.23058 | 0.22263 | -3.74243 | 3.26250 | 0.21667 | 0.45972 | 364.70415 | 1.65525 | 417.12346 | 2.46499 | 17.86452 | 0.12523 | 31.31216 | 0.24260 | 47.17922 | -0.25465 | 11.88498 |
| DecisionSelectedGlobal | 8 | 0.14347 | 0.08086 | 0.21440 | 0.21441 | -4.26092 | 3.43750 | 0.22500 | 0.45417 | 364.79384 | 1.64561 | 418.41440 | 2.48002 | 17.95421 | 0.11559 | 30.79754 | 0.20167 | 49.35724 | -0.16871 | 11.50006 |
| Oracle | 8 |  |  |  |  |  |  |  |  | 346.83963 | 1.53002 | 388.50893 | 2.34545 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 1.00000 | 10.55817 |

## 8. Forecast vs decision mismatch analysis

观察到 1 个 Test mismatch case（一个方向改善而另一个方向退化）：

| building | w_forecast | w_decision | forecast_MAE_delta_decision_minus_forecast | decision_regret_delta_decision_minus_forecast | p90_regret_delta_decision_minus_forecast | worst_10pct_peak_delta_decision_minus_forecast | decision_outcome | mismatch | mismatch_type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hog_office_Joey | 0.60000 | 0.30000 | -0.60340 | 1.18359 | -7.00139 | -0.17813 | degraded | True | forecast better / decision worse |

Validation MAE 排序与 Validation decision-regret 排序的逐建筑 Spearman 相关见 selected_weights.csv；Test 只作为冻结后的泛化证据，不参与权重或 tie-break。

## 9. Statistical uncertainty

| comparison | metric | resampling_unit | pairs | seed | resamples | mean_difference | median_difference | ci95_lower | ci95_upper | probability_of_improvement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DecisionSelectedPerBuilding minus ForecastSelectedPerBuilding | daily regret difference normalized by Phase 7 Train mean load | building-day pair | 240 | 42 | 10000 | -0.01596 | 0.00000 | -0.03048 | -0.00264 | 0.99020 |

bootstrap 对 building-day normalized regret difference 作 10,000 次 paired resampling（seed=42），只描述不确定性，不参与选择。

## 10. Leakage and battery constraint audit

Leakage=PASS；battery constraints=PASS；Phase 3–7 tracked artifacts unchanged=True；endpoint reproduction=True。

## 11. Limitations

证据仅覆盖固定的 8 栋 office、单一月份 Test、简单两模型凸组合与当前 battery protocol。Test 在 Phase 3–7 已被历史阶段使用，故不是项目级从未查看过的盲测集；本阶段仅保证 Test 不进入权重选择。未尝试第三模型、细化 grid 或 Test 后目标调整。

## 12. Final conclusion

Decision-oriented ensemble 在多数建筑且平均 Test regret 上改善，可作为最终候选组成部分；但仍受单月 Test 与 bootstrap 区间约束，不表述为普遍或显著提升。

允许声称的是：本阶段实施了 Validation-only 的决策导向预测融合受控对照，并如实报告跨建筑 Test 结果与不确定性。不能声称普通 weighted average 是全新 AI 架构、Oracle 可部署、Validation 优势就是 Test 泛化、或在缺乏一致跨建筑与 CI 支持时声称显著且稳定提升。
