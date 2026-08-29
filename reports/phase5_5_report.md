# Phase 5.5 最终报告

## 1. 代码与数据审计

实际审计并复用了 `src/battery/model.py`、`src/battery/optimizer.py`、`src/battery/metrics.py`、`scripts/run_phase5.py`、`scripts/run_phase4.py`、`src/models/train_lgbm.py`、Phase 4/5 测试、配置、逐日指标与三份 dispatch 文件。输入预测严格来自 `outputs/phase4/test_prediction.csv`，列为 `timestamp, actual, prediction, error, abs_error`；没有调用 LightGBM 拟合函数。

`timestamp` 已确认是 target timestamp，而不是 feature timestamp。范围为 2017-12-02 00:00 至 2017-12-31 23:00，共 720 个连续且不重复的小时、30 个自然日、每日 24 点。720 个 `actual` 与 `data/raw/electricity_cleaned.csv` 中 `Hog_office_Rolando` 同时刻逐点一致。Phase 5 的三份 Medium dispatch timestamp 与 Phase 4 完全对齐。

Phase 5.5 的 `1.0x baseline` 是 Phase 5 Medium：容量 732.777500 kWh，最大充/放电功率均为 183.194375 kW，SOC 范围 10%–90%，每天初始和终止 SOC 均为 50%，单程效率均为 0.9486833，往返效率 0.90。SOC 更新为 `SOC[t+1] = SOC[t] + eta_charge*charge[t] - discharge[t]/eta_discharge`；二进制 mode 禁止同小时充放电。目标为最小化 `forecast peak + 1e-6 * sum(charge + discharge)`。30 天分别独立优化，每天 SOC 重置，不跨日连续。

基线复现通过：新计算与 Phase 5 已保存 daily/dispatch 数值的最大绝对偏差为 `4.994e-11`，仅来自 CSV 十位小数舍入，低于 `1e-8` 回归容差。运行前后对 Phase 4/5 全部输出逐文件 SHA-256 核验一致。

## 2. 逐日稳健性结果

无储能平均日峰值为 442.7333 kW。Persistence、LightGBM、Oracle 的平均 realized peak 分别为 434.6032、430.7310、420.1718 kW；相应平均 decision regret 为 14.4314、10.5593、0 kW。LightGBM 在 19/30 天的 regret 低于 Persistence，Persistence 在 11/30 天更低，无平局。

LightGBM 的最差 regret 日期为 2017-12-22（28.0547 kW），其次为 2017-12-27（23.6286 kW）和 2017-12-25（21.6158 kW）。Persistence 最差日期为 2017-12-02（34.1278 kW），其次是 2017-12-11（30.3223 kW）和 2017-12-22（29.1108 kW）。这些结果说明平均优势并不等于逐日无风险；LightGBM 有 11 天不如 Persistence，且个别低负荷节假日会出现负削峰价值。

## 3. Forecast Error → Decision Regret

本报告统一定义：

`decision_regret = realized_peak_forecast_driven - realized_peak_oracle`。

等价的削峰损失定义为：

`peak_reduction_regret = oracle_peak_reduction - forecast_driven_peak_reduction`。

二者都以 actual load 评价，单位为 kW；数值越小越好。

| Controller | Error metric | Pearson | Spearman | Days |
|---|---|---:|---:|---:|
| LightGBM | daily MAE vs regret | 0.5440 | 0.4585 | 30 |
| LightGBM | daily RMSE vs regret | 0.5857 | 0.4857 | 30 |
| Persistence | daily MAE vs regret | 0.9254 | 0.8549 | 30 |
| Persistence | daily RMSE vs regret | 0.9269 | 0.8532 | 30 |

确认的事实是：两种策略的日误差与 regret 均为正相关，但 LightGBM 的关系仅中等，Persistence 的关系更强。合理解释是削峰只高度依赖峰值附近的误差及相对时序，全天平均误差不能完整描述控制价值。样本只有 30 天；相关不等于因果，表中 p 值仅保存在机器可读摘要作描述，不用于声称普适显著性。

## 4. Forecast Improvement → Decision Improvement

LightGBM 的整体 Test MAE 为 10.9021 kW，差于 Persistence 的 9.8611 kW；但 LightGBM 的平均 realized peak 低 3.8721 kW。这直接区分了“预测精度”和“决策价值”：整体 MAE 更低不是产生更好削峰的必要条件。

| Daily outcome | Days |
|---|---:|
| forecast better / decision better | 14 |
| forecast better / decision worse | 2 |
| forecast worse / decision better | 5 |
| forecast worse / decision worse | 9 |

LightGBM 的逐日 MAE 在 16/30 天胜出，decision regret 在 19/30 天胜出；14 天两者同时胜出。另有 7 天发生方向不一致（2 天预测更准但控制更差，5 天预测更差但控制更好）。因此预测优势只部分转化为决策优势，峰值位置和充放电窗口的误差结构比单一 MAE 更重要。

## 5. Battery Capacity Sensitivity

下表每格为“平均 realized peak / 平均 decision regret”（kW）。

| Capacity | Persistence | LightGBM | Oracle |
|---:|---:|---:|---:|
| 0.50x | 436.4889 / 13.9735 | 432.4814 / 9.9661 | 422.5154 / 0 |
| 0.75x | 434.8702 / 14.3347 | 430.8362 / 10.3007 | 420.5355 / 0 |
| **1.00x baseline** | **434.6032 / 14.4314** | **430.7310 / 10.5593** | **420.1718 / 0** |
| 1.25x | 434.6032 / 14.4314 | 430.7310 / 10.5593 | 420.1718 / 0 |
| 1.50x | 434.6032 / 14.4314 | 430.7310 / 10.5593 | 420.1718 / 0 |

Oracle 从 0.50x 增至 1.00x 改善 2.3436 kW，此后完全平台；LightGBM 始终优于 Persistence，优势约 3.87–4.03 kW。forecast-driven 与 Oracle 的绝对 gap 随容量由 0.50x 增至 1.00x 略扩大，因为更大的电池提高了 Oracle 可利用的完美信息价值；但 1.00x 后三者都不再改善。结论不依赖唯一容量点，但只覆盖给定的 0.50x–1.50x 范围及当前日复位模型。

## 6. Battery Power Sensitivity

0.50x、0.75x、1.00x、1.25x、1.50x 下，三种策略的平均 realized peak 均分别保持 Persistence 434.6032 kW、LightGBM 430.7310 kW、Oracle 420.1718 kW；regret 分别保持 14.4314、10.5593、0 kW。

这不是实验缺失，而是确认在固定基线容量下，即使将最大充放电功率降至 91.5972 kW，功率上限仍未成为这些日峰值解的有效瓶颈。因而 Phase 5 的核心排序对该功率范围不敏感；不能外推到低于 0.50x、亚小时控制或不同负荷形状。

## 7. Efficiency Sensitivity

保持充/放效率对称，单程效率取往返效率的平方根。

| Round-trip efficiency | Persistence peak / regret | LightGBM peak / regret | Oracle peak / regret |
|---:|---:|---:|---:|
| 0.85 | 435.0046 / 14.4515 | 431.1031 / 10.5500 | 420.5532 / 0 |
| **0.90 baseline** | **434.6032 / 14.4314** | **430.7310 / 10.5593** | **420.1718 / 0** |
| 0.95 | 434.2246 / 14.4124 | 430.3806 / 10.5683 | 419.8122 / 0 |

效率提高让三种策略的 realized peak 小幅下降，但 LightGBM 与 Persistence 的排序不变。LightGBM gap 对效率几乎不变（约 10.55–10.57 kW），未发现结论依赖 0.90 这一单点。

## 8. Forecast Bias Stress Test

只对保存的 LightGBM prediction 乘以 `1+bias`，不重新训练；所有预测仍为正，因此零截断实际触发 0 次。调度后继续用 actual 评价。

| Bias | Mean realized peak | Mean peak reduction | Mean regret |
|---:|---:|---:|---:|
| -10% | 430.6593 | 12.0740 | 10.4875 |
| -5% | 430.5801 | 12.1532 | 10.4083 |
| 0 | 430.7310 | 12.0023 | 10.5593 |
| +5% | 430.9918 | 11.7416 | 10.8200 |
| +10% | 431.2941 | 11.4392 | 11.1223 |

在该有限压力范围内，平均峰值最大变化为 0.7140 kW（-5% 到 +10%），排序总体稳定。正偏差逐步恶化，负偏差略改善，但这只是确定性扰动响应，不代表真实 bias 的概率或最优校准方向；不能据此用 Test 反向修正预测。

## 9. Bootstrap Stability

以天为配对重采样单位，对 `Persistence regret - LightGBM regret` 做 10,000 次 bootstrap，seed=42。配对均值差为 3.8721 kW，中位数差为 2.1623 kW，95% bootstrap CI 为 `[0.4714, 7.4537]` kW；LightGBM 胜 19/30 天，Persistence 胜 11/30 天。

该区间表明这 30 天内平均优势不是由单个日期单独造成，但它仍只描述当前 Test 月份，不能证明跨建筑、跨季节或普适因果效果。

## 10. Representative Case Studies

- **2017-12-22（LightGBM 最大 regret）**：实际峰在 11:00（444 kW）。LightGBM 在 08:00 低估负荷并充电 13.98 kW，把 427 kW 实际负荷推到 440.98 kW realized peak；Oracle 避免了这个错误充电窗口，日峰为 412.93 kW。
- **2017-12-11（LightGBM 最大改善）**：实际峰在 14:00（469 kW）。LightGBM 预测 465.72 kW并放电 30.16 kW；Persistence 仅预测 421 kW并放电 5.16 kW。两者最终峰值为 443.69 与 466.84 kW，说明峰值附近的排序正确比全天 MAE更关键。
- **2017-12-25（LightGBM 最大恶化）**：节假日实际峰仅 390 kW，LightGBM 当日 MAE 达 50.42 kW，并将预测峰放在 12:00。错误充电使 realized peak 达 407.51 kW，高于无储能；Persistence 峰值为 389.83 kW，接近 Oracle 的 385.90 kW。

四类 Top 3 日期完整保存在 `anomalous_date_rankings.csv`，案例图不只选择对 LightGBM 有利的日期。

## 11. 核心结论

1. **LightGBM 确实产生了下游 decision value，但不是通过更低的整体 MAE。** 它整体 MAE 更差，却把平均 realized peak 比 Persistence 降低 3.8721 kW，并在 19/30 天胜出；说明峰值附近时序信息具有额外价值。
2. **Phase 5 的平均排序不完全依赖少数日期。** 配对 bootstrap CI 为正，但 11/30 天反向，个别日会使储能后峰值恶化，因此不能描述成逐日可靠。
3. **结论不严重依赖单一 battery 参数点。** 容量 0.50x–1.50x、功率 0.50x–1.50x、往返效率 0.85–0.95 内，LightGBM 始终优于 Persistence；容量在 1.00x 后、功率在整个测试范围内呈平台。
4. **系统对 ±10% 系统性 bias 的平均响应较温和但不对称。** 正偏差更差，+10% 将平均 regret 增加 0.5631 kW；这不等于现实风险概率。
5. **LightGBM 与 Oracle 仍有明显空间。** 基线平均 gap 为 10.5593 kW；LightGBM 只捕获 Phase 5 所报 Oracle 理论削峰收益的一部分。Oracle 是 hindsight 上界，不可部署。

## 12. 输出文件

- CSV：`daily_diagnostics.csv`、`forecast_error_decision_regret.csv`、`forecast_vs_decision_consistency.csv`、`anomalous_date_rankings.csv`、三份 battery sensitivity、`forecast_bias_stress_test.csv`、`constraint_audit.csv`。
- JSON：`summary.json`、`bootstrap_decision_comparison.json`。
- Figures：误差—regret、预测—决策一致性、容量、功率、效率、bias，以及 3 张案例图，共 9 张，位于 `outputs/phase5_5/figures/`。
- Code：`src/phase5_5.py`、`scripts/run_phase5_5.py`。
- Tests：`tests/test_phase5_5.py`。

## 13. 自动验收

一键运行：`python scripts/run_phase5_5.py`。

测试命令：`python -m unittest discover -s tests -v`。提交前全量测试为 39/39 passed。验收覆盖 720 小时时间语义、raw actual 对齐、冻结预测哈希、Phase 5 基线回归、actual realized 口径、Oracle 角色、SOC/功率/互斥、1.0x 和 bias=0 回归、bootstrap seed、有限数值和原输出哈希。

## 14. Git

Phase 5.5 使用独立提交；commit hash、message 和最终 `git status` 在提交完成后的交付报告中记录。
