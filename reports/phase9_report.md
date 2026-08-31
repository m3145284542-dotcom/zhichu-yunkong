# Phase 9 — Final Algorithm Validation & Algorithm Freeze v1.0

## 1. Scope and honest evaluation protocol

Phase 9 是最后一个算法研发阶段。本次 cleanup 没有训练新模型、搜索新参数、改变建筑/切分/battery，也没有用测试结果重新选择配置。8 栋建筑、24 h horizon、31 个因果特征、Phase 7 模型参数、Phase 8 决策导向权重和全部正式数值保持不变。

正式术语为 **frozen held-out test period（冻结的留出测试区间）**。该区间在早期阶段作为固定 held-out evaluation period 使用，但历史阶段已经查看过结果；Phase 7–9 保持边界冻结，并禁止使用它重新选择模型、建筑或超参数。这是 honest evaluation protocol，不是项目级从未查看过的盲测声明。

## 2. Peak-aware design and 0.001 equivalence band

Peak-aware 仅比较 q∈{0.80,0.90}、alpha∈{0,0.5,1,2}，threshold 来自允许用于拟合/选择的 labels。为避免将 Validation 上极小、可能缺乏稳定性的数值差异解释为实质性决策提升，本阶段采用 normalized mean regret `0.001` 的等价带。与最佳候选差异不超过该阈值的配置视为决策表现近似等价，并优先选择复杂度更低、sample weighting 更弱的方案。

`0.001` 是保守的 model-selection tolerance，**不是** p-value、统计显著性阈值或置信阈值。

| building | q | alpha |
| --- | --- | --- |
| Hog_office_Rolando | 0.80000 | 0.00000 |
| Hog_office_Lavon | 0.80000 | 0.00000 |
| Hog_office_Joey | 0.80000 | 0.00000 |
| Lamb_office_Caitlin | 0.80000 | 0.00000 |
| Robin_office_Addie | 0.80000 | 0.00000 |
| Lamb_office_Gerardo | 0.80000 | 0.00000 |
| Hog_office_Alexis | 0.80000 | 0.00000 |
| Hog_office_Byron | 0.80000 | 2.00000 |

## 3. Canonical competition benchmark

原始 machine-readable 结果为兼容历史仍保留 `Persistence` 和 `Day`；两者均严格满足 `forecast(t)=actual(t-24h)`。比赛展示合并为一行 **Day Persistence**。`DOEF` 是 Phase 8 decision-oriented ensemble 在 Phase 9 正式冻结后的比赛方法名。

| display_name | normalized_mae_mean | normalized_rmse_mean | normalized_peak_mae_mean | normalized_decision_regret_mean | peak_reduction_mean_pct | peak_reduction_median_pct |
| --- | --- | --- | --- | --- | --- | --- |
| Day Persistence | 0.22588 | 0.43019 | 0.36119 | 0.16299 | -1.87845 | 0.63516 |
| Week | 0.20158 | 0.32841 | 0.25763 | 0.14432 | 3.08546 | 4.77208 |
| DayWeek | 0.18348 | 0.29662 | 0.26366 | 0.14302 | 4.90690 | 5.57369 |
| LightGBM | 0.14734 | 0.21694 | 0.21736 | 0.11613 | 1.00843 | 5.05712 |
| XGBoost | 0.14978 | 0.21675 | 0.21144 | 0.11753 | 0.45283 | 4.58839 |
| CatBoost | 0.17360 | 0.23921 | 0.23138 | 0.11874 | -24.48242 | 4.82086 |
| DOEF | 0.13797 | 0.20782 | 0.20720 | 0.11193 | 6.44233 | 5.62914 |
| Peak-aware LightGBM | 0.14759 | 0.21728 | 0.21737 | 0.11620 | 1.12881 | 5.05712 |

所有 peak-reduction 数值表示当前冻结储能容量、功率约束和调度协议下的削峰结果。**Peak shaving 不等于 energy saving**；本项目没有由该百分比推导节电量、电费或碳减排。

## 4. DOEF v1.0 core evidence

8 栋异质办公建筑上，DOEF 相对 LightGBM 的 normalized MAE 从 0.14734 降至 0.13797，程序计算的相对改善为 **6.3585%**；normalized decision regret 从 0.11613 降至 0.11193，相对改善为 **3.6147%**。

Decision win/tie/loss = **6/2/0**。DOEF − LightGBM normalized regret difference = **-0.004198**，95% CI **[-0.007830, -0.000356]**（10,000 paired bootstrap，seed 42）。

本项目的创新重点不是重新设计基础预测器，而是针对建筑储能削峰任务中“平均预测误差最优并不必然对应下游调度最优”的目标错位问题，建立预测—储能决策闭环评价体系，并通过 Validation 下游决策指标进行模型选择与融合，形成 DOEF。创新链为：Causal time-series forecasting + Decision-oriented validation + Forecast-to-storage closed-loop evaluation + Multi-building generalization + Decision-oriented ensemble。

## 5. CatBoost extreme aggregate audit

CatBoost peak reduction：mean=-24.48242%，median=4.82086%，min=-245.94331%，max=13.23669%。均值受少数建筑极端负向调度结果显著影响，因此单独使用 arithmetic mean 容易夸大其典型表现差异；这里保留真实均值，并同时报告 median、范围和全部逐建筑结果。

| building | peak_reduction_pct |
| --- | --- |
| Hog_office_Alexis | 11.68435 |
| Hog_office_Byron | 12.53391 |
| Hog_office_Joey | 0.33855 |
| Hog_office_Lavon | -245.94331 |
| Hog_office_Rolando | 5.55582 |
| Lamb_office_Caitlin | 4.08590 |
| Lamb_office_Gerardo | 2.64876 |
| Robin_office_Addie | 13.23669 |

极端值来自 Hog_office_Lavon：no-battery peak=19.192 kW，post-dispatch peak=66.393 kW，故比例为 -245.943%。其 normalized MAE=0.04797，但 daily peak-hour MAE=7.47 h。结合该建筑按 Train scale 配置、而测试负荷峰值较低的 battery 条件，错误的峰时调度会被百分比的小分母放大。这是与已保存诊断一致的解释，不是新的因果实验，也不掩盖 CatBoost 的失败。

## 6. Rejected supporting experiment: Peak-aware LightGBM

事实是 7/8 建筑选择 alpha=0，仅 Hog_office_Byron 选择 q=0.8、alpha=2.0。冻结的留出测试区间上，Peak-aware vs LightGBM 为 0/7/1，Peak-aware vs DOEF 为 0/2/6；Peak-aware − LightGBM CI 跨 0，而 Peak-aware − DOEF CI 完全高于 0。

简单的高负荷 sample weighting 没有产生稳定的跨建筑 downstream decision improvement。结果说明储能决策质量不能简单通过提高峰值样本训练权重获得；模型误差的时序结构、峰值时刻定位以及与储能约束的相互作用仍然重要。因此按照预定义停止规则，不再扩展 weighting function 或继续调参。

## 7. Engineering efficiency

| display_name | training_time_seconds_mean_across_buildings | inference_time_ms_mean_across_buildings | artifact_size_kib_mean_across_buildings | test_samples_per_building |
| --- | --- | --- | --- | --- |
| CatBoost | 0.78447 | 1.36970 | 228.63098 | 720.00000 |
| LightGBM | 0.18421 | 2.15424 | 499.19446 | 720.00000 |
| Peak-aware LightGBM | 0.18232 | 2.16324 | 499.99939 | 720.00000 |
| DOEF | 0.18748 | 2.34034 | 499.20911 | 720.00000 |
| XGBoost | 0.28488 | 2.16328 | 646.20984 | 720.00000 |

表中训练、推理和 artifact size 均为 8 栋建筑平均；inference 先对同一 720 样本重复 20 次取中位数，再跨建筑平均。环境是 summary.json 记录的 CPU 测试环境，不是嵌入式设备测试，不能外推为实际工业控制 latency。DOEF 相比标准 LightGBM 只增加很小的推理开销，在当前 CPU 测试环境下仍属于轻量级方法，但不声称已证明实时工业部署。

## 8. Final Algorithm

**DOEF v1.0**

**Decision-Oriented Ensemble Forecasting**

**面向储能决策的集成负荷预测方法**

Selection basis: Validation-selected decision-oriented ensemble, confirmed by frozen held-out multi-building evaluation. Held-out results用于报告与冻结确认，不用于重新选择建筑、模型参数或融合权重。

Core evidence: 8 heterogeneous office buildings；DOEF vs LightGBM = 6 wins / 2 ties / 0 losses；normalized MAE = 0.13797 vs 0.14734；normalized decision regret = 0.11193 vs 0.11613；bootstrap difference = -0.004198，95% CI [-0.007830, -0.000356]。

Rejected experiment: Peak-aware LightGBM 未产生稳定跨建筑收益，不进入最终算法。

**Algorithm development: FROZEN**

**Algorithm version: DOEF v1.0**
**Further algorithm R&D: STOPPED**

Phase 9 canonical consumers必须通过 `src.final_algorithm.load_final_algorithm()` 读取；Phase 9 缺失或校验失败时显式报错，不回退到 Phase 8。

