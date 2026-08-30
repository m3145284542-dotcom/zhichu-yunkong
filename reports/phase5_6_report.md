# Phase 5.6 — 预测产物血缘修复与储能结果回归审计

## 1. 漏洞结论

Phase 4.5 并不是“没有生成新预测”。它已经生成 `outputs/phase4_5/final_predictions.csv`，其中包含经过边界标签可用性修复后重新拟合得到的 Validation/Test 预测。

真正的问题是 Phase 5 的输入契约没有升级：Phase 5 把 `outputs/phase4/test_prediction.csv` 写死为 LightGBM 输入，因此 Phase 4.5 的修复结果没有传递到储能调度。Phase 5.5 又复用了 Phase 5 的 `load_inputs`，并在审计中继续把 Phase 4 预测视为冻结输入，所以错误血缘进一步传播到了鲁棒性分析。

这属于 **artifact lineage / stage handoff 漏洞**，而不是 LightGBM、MILP 或 SOC 约束本身的错误。

## 2. 为什么不直接覆盖 Phase 4

不删除、不覆盖 Phase 4 历史结果。Phase 4 是一个已经发生过的实验基线，保留它有利于复现和说明“Phase 4.5 修复了什么”。

Phase 5.6 引入明确的 canonical artifact 规则：

- Phase 4：历史基线，仅用于对照；
- Phase 4.5：当前权威负荷预测产物；
- Phase 5.6 及之后的预测驱动决策阶段：必须读取 Phase 4.5 的 final Test forecast，不能默认回退到 Phase 4。

权威读取接口位于 `src/forecast_artifacts.py`。

## 3. Phase 5.6 修复内容

1. 新增 `src/forecast_artifacts.py`：
   - 固定 canonical 文件为 `outputs/phase4_5/final_predictions.csv`；
   - 只读取 `split == "test"`；
   - 把 `target_timestamp / y_true / y_pred` 规范化为 Phase 5 使用的 `timestamp / actual / prediction`；
   - 强制检查 24 h horizon、720 小时、30 天、每日 24 点、时间连续性、Test 未参与模型选择；
   - 保存预测文件和配置文件 SHA-256，建立可追踪数据血缘。

2. 新增 `scripts/run_phase5_6.py`：
   - LightGBM 改用 Phase 4.5 canonical forecast；
   - Persistence 仍严格为 `actual(t-24h)`；
   - Oracle 仍只作为不可部署的 perfect-information benchmark；
   - 直接复用 Phase 5 已保存的 Small / Medium / Large 电池参数以及原优化器，保证本阶段只改变“预测来源”这一项；
   - 重新计算全部三种电池尺寸下的 Persistence / LightGBM / Oracle；
   - 强制要求 No Battery、Persistence、Oracle 与历史 Phase 5 在 `1e-8` 内保持不变；若它们变化，说明修复混入了额外因素，程序直接失败；
   - 输出修复后的指标、daily metrics、Medium dispatch、约束审计、预测源比较和与历史 Phase 5 的逐指标差值。

3. 新增 `tests/test_phase5_6.py`：
   - 验证 Phase 4.5 是 canonical source；
   - 验证 normalized Test schema 和 720 小时时间语义；
   - 验证 Phase 4 与 Phase 4.5 的 actual 完全一致但 prediction 确实不同，防止修复成为 no-op；
   - 验证历史 Phase 5 配置确实记录了旧的 `outputs/phase4/test_prediction.csv` 输入，从而把漏洞固定为可回归测试的事实。

## 4. 为什么这是正确修复

Phase 4.5 的最终 LightGBM 与 Phase 4 并非同一个拟合结果。Phase 4.5 对训练/验证边界处当时不可获得的 24 小时标签执行 purge，并在选择完成后用合法数据重新拟合最终模型。因此，若最终项目叙事采用 Phase 4.5 作为“泄漏审计后的正式模型”，下游调度必须使用 Phase 4.5 的 Test forecast。

同时，本阶段不改变电池容量、功率、SOC、效率、目标函数、Persistence 或 Oracle，这样新旧结果的差异可以归因于唯一变量：LightGBM forecast artifact 从 Phase 4 切换为 Phase 4.5。

## 5. 运行与验收

```powershell
python -m unittest tests.test_phase5_6 -v
python scripts\run_phase5_6.py
python -m unittest discover -s tests -v
```

运行后应生成：

- `outputs/phase5_6/phase5_6_metrics.csv`
- `outputs/phase5_6/daily_metrics.csv`
- `outputs/phase5_6/constraint_audit.csv`
- `outputs/phase5_6/forecast_source_comparison.csv`
- `outputs/phase5_6/comparison_vs_phase5.csv`
- `outputs/phase5_6/dispatch_lightgbm.csv`
- `outputs/phase5_6/dispatch_persistence.csv`
- `outputs/phase5_6/dispatch_oracle.csv`
- `outputs/phase5_6/summary.json`

核心验收条件：

- canonical source 必须是 Phase 4.5；
- Test 仍为 2017-12-02 00:00 至 2017-12-31 23:00，共 720 小时；
- actual 必须与 raw load 完全对齐；
- Phase 4.5 prediction 必须与 Phase 4 prediction 存在非零差异；
- Persistence / Oracle / No Battery 必须复现历史 Phase 5；
- 所有 MILP 求解成功；
- SOC、功率、充放电互斥、初始/终止 SOC 均不得违规；
- 只有 LightGBM 驱动的储能结果允许因为 forecast source 修复而变化。

## 6. 对既有 Phase 5 / 5.5 的处理

历史文件不删除，因为它们能够证明漏洞产生和传播的过程；但最终比赛报告不应再把历史 Phase 5 的 LightGBM 削峰结果作为正式结果。

Phase 5.5 的结论也应标注为“基于旧 Phase 4 forecast 的历史鲁棒性分析”。如果后续仍需要把误差传播/敏感性分析写进最终报告，应基于 Phase 5.6 canonical forecast 再生成一次对应分析，不能直接沿用旧数值。
