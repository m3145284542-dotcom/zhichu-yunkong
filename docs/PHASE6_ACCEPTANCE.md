# Phase 6 本地执行与验收清单

本清单用于在包含 `data/raw/electricity_cleaned.csv` 的本地工作区一次性执行 Phase 6。候选集合与选择规则已经在 `docs/PHASE6_PROTOCOL.md` 冻结；看到 Test 结果后不得修改候选网格再重跑并替换正式结果。

## 1. 分支

```powershell
git fetch origin
git checkout phase6-decision-aware-optimization
git pull
```

开始运行前：

```powershell
git status --short
```

除本地被忽略的 raw 数据外，应无未提交代码改动。

## 2. 环境与基础测试

```powershell
python -m pip install -r requirements.txt
python -m unittest tests.test_phase6 -v
python -m unittest discover -s tests -v
```

必须确认：

- Phase 6 单测全部通过；
- 历史 Phase 3–5.7 测试没有因为共享 LightGBM helper 修复而回归失败；
- LightGBM 4.x 的 `eval_set` + `sample_weight` 最小训练测试通过。

如测试失败，允许修工程 bug；但不得根据 Test 指标改变 `PEAK_WEIGHT_CANDIDATES`、`BASELINE_WEEKLY_WEIGHTS` 或选择规则。

## 3. 一次性正式运行

```powershell
python scripts\run_phase6.py
```

正式输出应新增：

- `outputs/phase6/baseline_selection.csv`
- `outputs/phase6/model_selection.csv`
- `outputs/phase6/selected_config.json`
- `outputs/phase6/test_forecast_metrics.csv`
- `outputs/phase6/test_dispatch_metrics.csv`
- `outputs/phase6/test_daily_metrics.csv`
- `outputs/phase6/test_predictions.csv`
- `outputs/phase6/dispatch_phase6_lightgbm.csv`
- `outputs/phase6/dispatch_selected_blend.csv`
- `outputs/phase6/summary.json`
- `reports/phase6_report.md`

## 4. 人工必须审核的结果

### A. 选择是否只来自 Validation

打开 `selected_config.json`，确认：

- `test_used_for_selection = false`
- `test_is_historically_observed_not_pristine_blind = true`
- 选中的 baseline 和 peak-aware LightGBM 与对应 selection CSV 第一行一致。

### B. 主结论

查看 `test_dispatch_metrics.csv`：

主指标是 `mean_daily_peak`，越低越好。

重点比较：

1. `Phase 6 peak-aware LightGBM`
2. `Phase 4.5 canonical LightGBM`
3. `Selected blended persistence`
4. `Yesterday persistence`
5. `Last-week persistence`
6. `Oracle`

只有 Phase 6 peak-aware LightGBM 的 `mean_daily_peak` 低于 Phase 4.5 canonical LightGBM，才能声称 Phase 6 改善了主削峰指标。

### C. 预测与决策不能混写

查看 `test_forecast_metrics.csv`：

- 如果 MAE/RMSE 改善但削峰没有改善，只能说预测指标改善；
- 如果削峰改善但 MAE/RMSE没有改善，可说误差结构更有利于下游储能决策；
- 如果强组合 baseline 优于 LightGBM，必须如实保留，不能删掉或弱化。

### D. Test 的身份

2017-12 Test 已在历史 Phase 3–5.7 被观察过，因此报告不得写“完全未见 blind Test”“首次测试”等表述。Phase 6 的可信点是候选规则预冻结、Test 不参与本阶段选择，而不是 Test 从未被项目看过。

### E. 历史负结果保留

Phase 5.7 的结论仍是：当时的 residual-block bootstrap + CVaR 鲁棒策略在固定 Test 上明显劣于确定性 LightGBM。Phase 6 不得删除或改写成“鲁棒优化有效”。

## 5. 结果提交前检查

```powershell
git status --short
git diff --stat
git diff -- outputs/phase3 outputs/phase4 outputs/phase4_5 outputs/phase5 outputs/phase5_5 outputs/phase5_6 outputs/phase5_7
```

最后一条命令应没有历史输出修改。

确认后提交：

```powershell
git add docs/PHASE6_PROTOCOL.md docs/PHASE6_ACCEPTANCE.md src/models/train_lgbm.py src/phase6.py scripts/run_phase6.py tests/test_phase6.py outputs/phase6 reports/phase6_report.md
git commit -m "feat: complete Phase 6 decision-aware optimization"
git push origin phase6-decision-aware-optimization
```

不要在看到 Test 后新增候选、改权重网格或重新定义主指标后覆盖正式结果。若 Phase 6 失败，保留失败结果并分析原因。
