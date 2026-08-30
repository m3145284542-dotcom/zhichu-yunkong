# Phase 5.7 — 不确定性感知的鲁棒储能削峰优化

## 1. 研究问题

使用仅来自 Validation 的日内相关预测误差情景，CVaR 风险感知调度能否降低 Test 的极端决策损失，同时保持有竞争力的平均削峰效果。

## 2. 与 Phase 5 / 5.5 的关系

电池可行域、日调度边界、效率、功率、容量、初末 SOC 和吞吐惩罚全部复用 Phase 5 Medium 配置。Phase 5.5 的历史分析基于旧 Phase 4 forecast lineage；Phase 5.6 已证明正式后续阶段应使用 Phase 4.5 canonical prediction，因此本阶段不复用 Phase 5.5 的 Test residual。Persistence、LightGBM deterministic、Oracle 的 720 小时 charge/discharge/SOC/grid load 与 Phase 5.6 逐列最大绝对差为 4.998e-11。

## 3. 数据与时间切分

预测 horizon 为 24h，`target_timestamp = feature_timestamp + 24h`。Validation feature-time 为 2017-11-01 00:00:00 至 2017-11-30 23:00:00；对应的 Validation target-time 为 2017-11-02 00:00:00 至 2017-12-01 23:00:00，共 720 小时/30 个完整自然日。feature-time 与 target-time 相差 24 小时是由 `t -> t+24h` 的预测定义自然产生的，不是时间错位或数据泄漏。Test target 为 2017-12-02 至 2017-12-31，共 720 小时/30 日。

## 4. 防止数据泄漏措施

不确定性来源固定为 `outputs/phase4_5/final_predictions.csv` 中 `split=validation` 的保存预测；residual 定义为 actual - prediction。Test residual、Test actual 和 Test 指标均未进入情景构造或参数选择。选中配置先写入 `selected_robust_config.json`，之后才调用 canonical Test loader；Test 配置只执行一次。Persistence 使用目标日前一日 actual，Oracle 仅为不可部署的 hindsight upper bound。

## 5. Validation residual analysis

Validation residual 均值 -0.1650 kW，标准差 18.5162 kW，MAE 7.6363 kW，RMSE 18.5041 kW，范围 [-58.4224, 399.8591] kW。

## 6. Uncertainty scenario construction

按 target natural day 形成 30 个 24h residual block。每个调度日以 seed=42 有放回抽取 100 个整日 block，并与该日 LightGBM forecast 相加；日内相关结构不被逐小时打散。负情景负荷 clip 到 0；Validation 与最终 Test 共记录 0 个被 clip 的小时值。

## 7. Robust optimization mathematical formulation

同一组 charge/discharge 同时作用于所有情景：`grid[s,t] = scenario_load[s,t] + charge[t] - discharge[t]`，且 `peak[s] >= grid[s,t]`。目标为 `mean_s peak[s] + lambda * (eta + 1/((1-alpha)S) * sum_s excess[s]) + 1e-6 * throughput`，约束 `excess[s] >= peak[s] - eta`、`excess[s] >= 0`。`alpha=0.90`。lambda=0 是情景期望峰值优化，不等价于 Phase 5 确定性 baseline；后者独立调用原 optimizer。

## 8. Parameter-selection procedure

预先冻结的选择规则为：在 Validation mean daily realized peak 不超过确定性 Validation 均值 1.01 倍的候选中，最小化 Validation worst-10% daily realized peak；如相同，再依次按 mean daily peak 和较小 lambda 破同分。Test 未参与选择。最终配置为 lambda=0.5、alpha=0.9、scenarios=100。

lambda=0.5 是按照预先冻结的 Validation 选择规则确定的最终配置，但其相对于 lambda=0.25 的 Validation tail 优势仅约 0.0414 kW，因此不能描述为显著优于邻近参数。

| lambda | validation_mean_daily_peak | validation_worst_10pct_daily_peak | validation_mean_regret | validation_throughput | eligible |
| --- | --- | --- | --- | --- | --- |
| 0.0000 | 454.3177 | 522.2542 | 13.1240 | 15253.9224 | True |
| 0.2500 | 459.4020 | 521.0703 | 18.2084 | 18879.0120 | True |
| 0.5000 | 459.7208 | 521.0288 | 18.5272 | 19274.5485 | True |
| 1.0000 | 462.1936 | 523.1867 | 21.0000 | 21296.1556 | True |
| 2.0000 | 465.3947 | 525.8921 | 24.2010 | 23545.8768 | False |

## 9. Test comparison

峰值均以 actual realized grid load 计算；overall original peak 对所有方法相同。

| method | post_dispatch_peak | absolute_peak_reduction | peak_reduction_percentage | mean_daily_peak | worst_10pct_day_metric | mean_regret | p90_regret | max_regret |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| No Battery | 483.0000 | 0.0000 | 0.0000 | 442.7333 | 481.0000 | 22.5615 | 39.8354 | 42.3850 |
| Persistence deterministic | 466.8421 | 16.1579 | 3.3453 | 434.6032 | 461.3412 | 14.4314 | 27.0610 | 34.1278 |
| LightGBM deterministic | 453.8018 | 29.1982 | 6.0452 | 431.2992 | 453.0817 | 11.1274 | 17.0718 | 28.5901 |
| LightGBM robust | 465.9344 | 17.0656 | 3.5333 | 440.6353 | 462.6458 | 20.4635 | 25.6434 | 41.9091 |
| Oracle | 441.4493 | 41.5507 | 8.6026 | 420.1718 | 441.0068 | 0.0000 | 0.0000 | 0.0000 |

## 10. Robustness / tail-risk analysis

Phase 5.7 表明，显式引入预测不确定性并不必然改善储能削峰。基于 Validation 24h residual block bootstrap 与 CVaR 构建的鲁棒策略，在独立 Test 上的平均日峰值、worst-10% 日峰值和 decision regret 均劣于确定性 LightGBM 调度。因此，本实验不能支持“鲁棒优化提高了削峰性能”这一结论。

鲁棒相对确定性的 worst-10% 日峰值变化为 +9.5642 kW（负值表示改善），worst daily peak 与 regret 尾部见上表。Validation sensitivity 中，从 lambda=0 增加到最终 lambda=0.5 时，robust throughput 从约 15253.9 增加到 19274.5 kWh，但实际削峰反而更差。因此，性能下降并非主要来自电池使用不足，而更可能来自 Validation residual scenarios 与 Test 中真正影响峰值决策的误差结构之间存在分布偏移，导致有限储能资源被分配到错误的时段。这里的分布偏移解释是与观测结果一致的机制推测，而不是由当前实验直接识别出的因果事实。

方法学上，历史残差重采样在流程上可以是无泄漏、可复现的，但并不能保证构造出具有 out-of-sample 决策价值的不确定性集合。

## 11. Paired daily comparison

定义 paired difference = robust actual daily peak - deterministic actual daily peak。better/equal/worse = 1/0/29 天，均值 +9.3361 kW，中位数 +9.4382 kW，最大改善 0.2543 kW，最大恶化 13.3995 kW。

## 12. Battery constraint audit

solver failure、SOC 上下界、充放电功率、同时充放电、SOC transition、initial SOC、terminal SOC、NaN/Inf 的违规总数依次为：0、0、0、0、0、0、0、0。

## 13. Sensitivity experiment

lambda sensitivity 完全在 Validation 上完成。表中同时给出 average peak、worst-10% tail peak、mean regret 与 throughput；从 lambda=0 到 lambda=0.5，throughput 由 15253.9224 增至 19274.5485 kWh，而 Validation mean peak 和 mean regret 同时恶化，只有 tail peak 小幅下降。其变化可能非单调，因为共享 dispatch、离散充放电互斥和有限样本 CVaR 共同作用，不能据 Test 曲线反调参数。

## 14. Success-day case study

相对表现最好的日期为 2017-12-08；`case_success_day.png` 同时展示 actual、forecast、两种 grid load、battery power 与 SOC。

## 15. Failure-day case study

相对表现最差的日期为 2017-12-06；即使该日差值不为正，也仍按预先定义的“最差相对日”展示，避免只挑有利案例。详见 `case_failure_day.png`。

## 16. Limitations

本实验的适用范围严格限于单建筑 `Hog_office_Rolando`、30 日 Test、30 个 Validation residual day blocks、Phase 5 Medium battery、daily SOC reset，以及当前 scenario-based CVaR formulation。Validation block bootstrap 不能创造历史样本中未出现的误差形态，模型也不是对所有可能扰动的硬 worst-case 保证。实验未研究其他建筑、季节、时间窗口、电池尺寸、跨日能量耦合、scenario construction、风险目标、电价或退化成本。因此，当前负面结果不得外推为“鲁棒优化普遍无效”。

## 17. Competition-report-safe conclusions

Phase 5.7 表明，显式引入预测不确定性并不必然改善储能削峰。基于 Validation 24h residual block bootstrap 与 CVaR 构建的鲁棒策略，在独立 Test 上的平均日峰值、worst-10% 日峰值和 decision regret 均劣于确定性 LightGBM 调度。因此，本实验不能支持“鲁棒优化提高了削峰性能”这一结论。

具体而言，鲁棒相对确定性的平均 regret 变化为 +9.3361 kW，worst-10% 日峰值变化为 +9.5642 kW。该结论仅适用于 `Hog_office_Rolando`、30 日 Test、30 个 Validation residual day blocks、Medium battery、daily SOC reset 和当前 scenario-based CVaR formulation，不得外推为“鲁棒优化普遍无效”。Oracle 仍只是不可部署的 hindsight theoretical upper bound。
