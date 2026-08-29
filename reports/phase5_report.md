# 第五阶段：基于负荷预测的储能削峰调度优化与决策价值评估

## 审计与口径

- 建筑：`Hog_office_Rolando`
- 原始负荷：`data/raw/electricity_cleaned.csv`
- Phase 4 预测：`outputs/phase4/test_prediction.csv`
- 预测列：`timestamp, actual, prediction, error, abs_error`
- `timestamp` 为 target timestamp；Test target 为 2017-12-02 00:00 至 2017-12-31 23:00，共 720 个连续小时、30 个完整自然日。
- Phase 4 的 720 个 `actual` 已与原始负荷逐点核对一致；LightGBM 调度只读取保存的 `prediction`，没有重新训练或用 actual 修正。
- Persistence 严格使用 `actual(T-24h)`；每个目标日所用源日均在目标日开始前结束。实验假设在目标日 00:00 一次性形成 24h 调度计划时，前一日最后一个小时的计量已经完成采集并立即可用；真实 EMS 可能存在采集、通信和数据清洗延迟。Oracle 才在优化时使用目标日 actual，且不可部署。

原始训练区间只有 1 个缺失小时。储能场景容量依据 Phase 4 实际训练样本对应的 15,573 个非缺失 `current_load` 均值确定，不插值、不填 0。`mean_train_load = 305.323958 kWh/h`，平均日能量为 7,327.774995 kWh。

BDG2 官方论文说明，能源类 meter 文件使用 `kWh_sum`，每行表示一个小时区间内累计的电能。原始 `electricity_cleaned.csv` 因此按小时累计电能解释，单位为 kWh。由于本研究固定时间步长为 Δt = 1 h，某小时的 kWh 数值转换为该小时区间平均功率后，在数值上等于 kW。储能容量与 SOC 使用 kWh，额定充放电功率使用 kW；优化程序中的单步充放电能量满足 `E = P × Δt`，因 Δt = 1 h 而与功率数值相同。本文的 Mean Daily Peak 是小时平均功率峰值，单位为 kW。来源：[Building Data Genome Project 2 官方论文](https://www.nature.com/articles/s41597-020-00712-x)。

## 储能与优化

| Size | Capacity (kWh) | Max charge/discharge (kW) | SOC min/max (kWh) | Initial/terminal SOC (kWh) |
|---|---:|---:|---:|---:|
| Small | 366.388750 | 91.597187 | 36.638875 / 329.749875 | 183.194375 |
| Medium | 732.777500 | 183.194375 | 73.277750 / 659.499750 | 366.388750 |
| Large | 1,465.554999 | 366.388750 | 146.555500 / 1,318.999499 | 732.777500 |

`eta_charge = eta_discharge = sqrt(0.9) = 0.9486833`。目标为 `min peak + 1e-6 * sum(charge + discharge)`；吞吐惩罚仅打破无意义循环。SOC 按效率方程更新，二进制 mode 显式禁止同小时充放电。求解器为 `scipy.optimize.milp` 的 HiGHS 后端。共执行 270 次单日 MILP 优化（30 天 × 3 种储能规模 × 3 种储能控制器）。EFC 统一定义为总放电能量除以名义容量。

## Medium 主结果

| Controller | Mean Daily Peak | Mean Reduction % | Max Peak | P95 | PAR | EFC | Oracle Capture |
|---|---:|---:|---:|---:|---:|---:|---:|
| No Battery | 442.7333 | 0.0000% | 483.0000 | 468.0000 | 1.1514 | 0.0000 | N/A |
| Persistence + Battery | 434.6032 | 1.6836% | 466.8421 | 448.0661 | 1.1110 | 6.5130 | 36.04% |
| LightGBM + Battery | 430.7310 | 2.5412% | 451.2604 | 444.2239 | 1.0740 | 6.0260 | 53.20% |
| Oracle / Perfect Foresight / Not Deployable | 420.1718 | 4.9459% | 441.4493 | 440.9559 | 1.0506 | 6.1863 | 100.00% |

LightGBM 将 Mean Daily Peak 比 Persistence 再降低 3.8721 kW（相对 Persistence 为 0.8910%），30 天中 19 天更好、11 天更差。它捕获 53.20% 的 Oracle 理论收益，高于 Persistence 的 36.04%，但仍比 Oracle 高 10.5593 kW。

在本 Test 集上，Persistence 的整体 MAE、RMSE 和 MAPE 分别为 9.8611、15.5434 和 2.3383%，均优于 LightGBM 的 10.9021、17.4211 和 2.7097%；但 LightGBM 驱动的储能调度取得了更低的 Mean Daily Peak。这表明传统点预测误差指标与下游削峰决策价值并不完全一致。LightGBM 获得更高决策价值的具体误差机制仍需进一步诊断。

Medium 下 LightGBM 和 Persistence 均有 8/30（26.67%）的日期出现 realized peak 高于 No Battery。因此，当前方案应被理解为平均意义有效、逐日存在风险的日前开环控制器；该结果是后续风险感知调度、fallback 策略或滚动修正研究的直接动机。

## 容量敏感性

| Size | Persistence Mean Peak | LightGBM Mean Peak | Oracle Mean Peak |
|---|---:|---:|---:|
| Small | 436.4889 | 432.4977 | 422.5154 |
| Medium | 434.6032 | 430.7310 | 420.1718 |
| Large | 434.6032 | 430.7310 | 420.1718 |

Small 增至 Medium 对三种控制器均继续改善；Medium 增至 Large 没有新增 Mean Daily Peak 收益，说明在当前 24 小时独立复位、功率/效率与负荷形状下已经进入平台期，存在明确边际收益递减。LightGBM 相对 Persistence 的优势在三档中约 4 kW，Oracle gap 没有被 Large 进一步缩小。

## 约束与限制

270 次单日 MILP 优化全部成功；SOC violations、power violations、simultaneous charge/discharge violations、initial SOC violations、terminal SOC violations 均为 0。模型采用理想确定性的电池效率和一小时控制步长；容量是场景化设定，未考虑退化成本、电价、EMS 延迟、预测发布时延、备用容量、光伏或需求响应。每日 SOC 独立复位是公平比较设计，不代表跨日连续运行。Oracle 是理论上界，不可部署。
