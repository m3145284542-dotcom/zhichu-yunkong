# Phase 5.6：预测数据血缘修复与下游重算

## 漏洞发现与根因

Phase 4.5 已输出经过边界标签 purge 和重新拟合的 `outputs/phase4_5/final_predictions.csv`，但代码审计发现 `scripts/run_phase5.py` 的 `load_inputs()` 仍硬编码读取 `outputs/phase4/test_prediction.csv`。Phase 5.5 又复用该输入函数，因此修复前的数据链实际为 `Phase 4 -> Phase 5 -> Phase 5.5`。

不覆盖 Phase 4 的原因是它仍是可复现实验的历史基线；覆盖会破坏既有 Phase 5/5.5 的来源证据和前后对照。Phase 4.5 被设为 canonical 的理由是实验时间边界和数据可用性协议更严格，而不是根据 Test 预测或削峰结果择优。

修复后正式数据链为 `Phase 4 -> Phase 4.5 canonical forecast -> Phase 5.6 -> 后续阶段`。统一入口为 `load_canonical_test_forecast(project_root)`，且没有 Phase 4 fallback。

## 修改前审计事实

- Phase 4.5 Test feature 时间：2017-12-01 00:00:00 to 2017-12-30 23:00:00；target 时间：2017-12-02 00:00:00 to 2017-12-31 23:00:00。
- Test 为 720 小时、30 天、每日 24 条，且每行 `target_timestamp - feature_timestamp = 24h`。
- Phase 4 与 Phase 4.5 的 timestamp、actual 完全一致；720 行 prediction 全部变化，最大绝对预测差为 18.305803。
- Phase 4.5 对 Train 和 Validation 边界标签均执行 purge；配置明确 Test 不参与特征或参数选择。
- Phase 5 的旧配置明确记录 `input_prediction_file = outputs/phase4/test_prediction.csv`，绕过原因仅是硬编码输入血缘。

## Phase 4 vs Phase 4.5 预测指标

| forecast_source | MAE | RMSE | MAPE |
| --- | --- | --- | --- |
| Phase 4 historical LightGBM | 10.902081 | 17.421081 | 2.709733 |
| Phase 4.5 canonical LightGBM | 11.586274 | 17.337497 | 2.869998 |
| Persistence | 9.861111 | 15.543398 | 2.338322 |
| Oracle | 0.000000 | 0.000000 | 0.000000 |

不能把该表概括为“Phase 4.5 精度更高”：MAE/MAPE 变差而 RMSE 改善。canonical 身份来自更正确的可用性协议。

## Phase 5 vs Phase 5.6 削峰指标（Medium 为主）

| controller | battery_size | mean_daily_peak_phase5 | mean_daily_peak_phase5_6 | delta_mean_daily_peak | mean_peak_reduction_phase5 | mean_peak_reduction_phase5_6 | delta_mean_peak_reduction | mean_peak_reduction_pct_phase5 | mean_peak_reduction_pct_phase5_6 | delta_mean_peak_reduction_pct | max_peak_phase5 | max_peak_phase5_6 | delta_max_peak | oracle_capture_ratio_phase5 | oracle_capture_ratio_phase5_6 | delta_oracle_capture_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LightGBM | Medium | 430.73103600 | 431.29915581 | 0.56811981 | 12.00229734 | 11.43417753 | -0.56811981 | 2.54117917 | 2.41235091 | -0.12882826 | 451.26043852 | 453.80183921 | 2.54140069 | 0.53198019 | 0.50679930 | -0.02518089 |
| No Battery | None | 442.73333333 | 442.73333333 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 483.00000000 | 483.00000000 | 0.00000000 |  |  |  |
| Oracle | Medium | 420.17178388 | 420.17178388 | 0.00000000 | 22.56154946 | 22.56154946 | -0.00000000 | 4.94588323 | 4.94588323 | -0.00000000 | 441.44933921 | 441.44933921 | 0.00000000 | 1.00000000 | 1.00000000 | 0.00000000 |
| Persistence | Medium | 434.60317836 | 434.60317836 | -0.00000000 | 8.13015497 | 8.13015497 | -0.00000000 | 1.68362304 | 1.68362304 | -0.00000000 | 466.84210526 | 466.84210526 | -0.00000000 | 0.36035446 | 0.36035446 | -0.00000000 |

Phase 4.5 来源修复后，Medium LightGBM 的 mean daily peak 变化 +0.56811981 kW，mean peak reduction 变化 -0.56811981 kW，mean peak reduction pct 变化 -0.12882826 个百分点，max peak 变化 +2.54140069 kW，oracle capture ratio 变化 -0.02518089。

## Isolation regression 与约束审计

No Battery、Persistence、Oracle 的最大绝对指标 delta 分别为 4.477e-11、4.944e-11、4.849e-11，均在 `1e-8` 内。全部 MILP 求解成功；SOC、功率、同时充放电、初始 SOC、终端 SOC 违规数均为 0。

## 对 Phase 5.5 的影响

Phase 5.5 历史输出继续保留，但其中 LightGBM 的误差传播、鲁棒性和敏感性结论基于旧 Phase 4 forecast source，不能作为 canonical forecast 的正式下游结论。建议以 Phase 4.5 canonical forecast 重跑一个新的 corrective robustness stage；不得覆盖 Phase 5.5。

## 后续数据血缘规则

Phase 6/7、储能决策和 Web 层必须通过 canonical loader 取得正式预测，不得拼接具体阶段路径。loader 必须同时验证来源配置、时间语义、完整性、误差列一致性与 SHA-256。Oracle 仅是不可部署的 hindsight upper bound；Persistence 仍严格为目标日前已知的 `actual(T-24h)`。
