# Phase 6 Windows 本地独立复现与云端对齐报告

复现日期：2026-08-30（Asia/Shanghai）

## 1. 结论

**A. 完全对齐。**

Windows 本地环境在目标 commit `fa8be94ea01c4663ba12b01b36e2655eae74f078` 上完整运行 Phase 6 后，Validation 选择、Canonical reproduction、Test 预测指标、储能决策指标和电池约束审计均与该 commit 中的云端正式产物一致。4 个核心 CSV 的所有数值列最大绝对差为 `0`，两个核心 JSON 语义完全相同，72 个回归测试全部通过。

## 2. Git 状态

- 远程分支：`origin/phase6-decision-aware`
- 远程分支 SHA：`fa8be94ea01c4663ba12b01b36e2655eae74f078`
- 本地复现状态：detached HEAD（未创建新分支）
- 本地 HEAD：`fa8be94ea01c4663ba12b01b36e2655eae74f078`
- 未 merge、未 push、未创建 PR、未 commit
- 工作区不 clean。运行前唯一未跟踪文件为工程长期约定 `AGENTS.md`，不参与 Phase 6 计算，本次未覆盖或删除。

## 3. 本地运行环境

- 操作系统：Windows 11（`Windows-11-10.0.26200-SP0`）
- Python：3.12.13
- Python 可执行文件：`D:\document\aic\.venv\Scripts\python.exe`
- LightGBM：4.7.0
- NumPy：2.5.2
- pandas：2.3.3
- SciPy：1.18.1
- 云端工作流：GitHub Actions `ubuntu-latest` + Python 3.11；工作流只保存了依赖版本范围，未在仓库产物中记录云端各 Python 包的精确版本。

实际运行命令：

```powershell
& '.venv\Scripts\python.exe' 'scripts\run_phase6.py'
& '.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

Phase 6 完整运行成功，本次脚本记录耗时为 `11.076200699997571` 秒。

## 4. 数据与实验协议审计

- 本地已有冻结 BDG2 原始数据，未重复下载。
- `data/raw/electricity_cleaned.csv` SHA-256：`b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3`，与代码中冻结哈希一致。
- 日/周组合公式为 `(1-w_week) * yesterday + w_week * last_week`，候选为 `[0, 0.25, 0.5, 0.75, 1.0]`。
- 选择指标为冻结 Phase 5 Medium Battery 下的 Validation 平均每日实际峰值，不是单纯 MAE。
- Validation 在边界标签 purge 后为 696 小时、29 个完整自然日。
- Test 为 720 小时、30 个完整自然日，每日 24 条。
- 训练集高负荷阈值由 purge 后 Train target P75 冻结为 `448.0 kW`。
- 高负荷样本权重候选为 `[1.0, 1.5, 2.0, 3.0]`。
- `selected_config.json` 在 canonical Test loader 调用前写出；`test_used_for_selection=false`，`zero_test_leakage=true`。
- Phase 4.5 canonical 预测和配置、Phase 5 Medium Battery 配置的 SHA-256 在运行前后不变。

## 5. Validation 选择对齐

| 项目 | 云端正式值 | Windows 本地值 | 差异 |
| --- | ---: | ---: | ---: |
| `w_week` | 0.5 | 0.5 | 0 |
| `peak_weight_multiplier` | 2.0 | 2.0 | 0 |
| `peak_threshold` (kW) | 448.0 | 448.0 | 0 |
| Validation rows | 696 | 696 | 0 |
| Validation complete days | 29 | 29 | 0 |

`validation_day_week_candidates.csv` 共 5 行，`validation_peak_weight_candidates.csv` 共 4 行；两者的列结构均相同，所有数值列相对于目标 commit 的最大绝对差均为 `0`。

## 6. Canonical reproduction

| 项目 | 云端正式值 | Windows 本地值 | 差异 |
| --- | ---: | ---: | ---: |
| Test rows | 720 | 720 | 0 |
| 最大预测绝对差 (kW) | `5.684341886080802e-14` | `5.684341886080802e-14` | 0 |

该差异远小于 `1e-10`，属于机器精度级一致。

## 7. Test 预测与决策指标对齐

下表的云端值取自目标 commit 内的正式 CSV；δ 为“本地 - 云端”。

| 方法 | 云端 MAE | 本地 MAE | δ MAE | 云端 mean daily realized peak (kW) | 本地值 (kW) | δ peak (kW) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Persistence | 9.86111111111111 | 9.86111111111111 | 0 | 434.6031783646792 | 434.6031783646792 | 0 |
| Day-week blend (`w_week=0.5`) | 8.86875 | 8.86875 | 0 | 431.60041443900246 | 431.60041443900246 | 0 |
| Canonical LightGBM | 11.586274191057308 | 11.586274191057308 | 0 | 431.2991558056665 | 431.2991558056665 | 0 |
| Peak-aware LightGBM (`m=2`) | 10.117471111324056 | 10.117471111324056 | 0 | 432.13491756879523 | 432.13491756879523 | 0 |
| Oracle | 0.0 | 0.0 | 0 | 420.17178387713477 | 420.17178387713477 | 0 |

额外的 Last-week 和 No Battery 结果也与目标 commit 一致。`test_forecast_metrics.csv` 和 `test_decision_metrics.csv` 的所有数值列相对于目标 commit 的最大绝对差均为 `0`。

## 8. 电池约束与回归测试

- Test 电池审计：180/180 个日-方法求解成功。
- SOC 违例：0。
- 充放电功率违例：0。
- 同时充放电违例：0。
- SOC 转移违例：0。
- NaN/Inf：0。
- 最大初始 SOC 绝对误差：0。
- 最大终止 SOC 绝对误差：0。
- 完整回归测试：72 个。
- Passed：72。
- Failed：0。
- Error：0。
- Skipped：0。

测试中出现 NumPy 2.5.2 针对无单位 `timedelta` 的 `DeprecationWarning`，但未导致失败、数值偏差或约束差异。这是未来依赖兼容性提示，不是本次 Phase 6 科学逻辑回归，本次未修改代码。

## 9. 科学结论复核

- Day/week 组合 baseline 的 Test MAE 为 `8.86875`，低于 Persistence 的 `9.86111111111111`；其平均每日实际峰值为 `431.60041443900246 kW`，低于 Persistence 的 `434.6031783646792 kW`。因此 Day/week 组合 baseline 明显优于单纯 Persistence。
- Peak-aware LightGBM 的 Test MAE 从 Canonical LightGBM 的 `11.586274191057308` 改善到 `10.117471111324056`，但平均每日实际峰值由 `431.2991558056665 kW` 升至 `432.13491756879523 kW`，增加 `0.83576176312873 kW`。因此不能声称峰值加权提高了 Test 平均削峰效果。
- 负结果与云端报告一致，未重新包装，也未利用 Test 反向调参。

## 10. 本次运行的文件影响

本次未修改任何 Python 源码、测试、工作流或 Phase 3–5.7 产物。

运行后 Git 识别到两个已跟踪 JSON 变化：

- `outputs/phase6/canonical_reproduction.json`
- `outputs/phase6/selected_config.json`

两者仅为 Windows CRLF 与 Linux LF 换行差异；`git diff --ignore-space-at-eol` 无内容差异，JSON 解析后语义完全相同。

脚本新生成的未跟踪正式运行证据包括：

- `outputs/phase6/constraint_audit.csv`
- `outputs/phase6/dispatch_*.csv`（6 个方法）
- `outputs/phase6/figures/*.png`（4 张图）
- `outputs/phase6/summary.json`
- `outputs/phase6/test_daily_metrics.csv`
- `reports/phase6_local_reproduction_report.md`

运行前已存在的未跟踪 `AGENTS.md` 保持不变。

## 11. 已解决的清理与保留事项

1. 本地运行新生成、可由 `python scripts/run_phase6.py` 重现的 Phase 6 中间产物已经逐项安全清理；本地复现报告被保留并已提交。
2. `outputs/phase6/canonical_reproduction.json` 和 `outputs/phase6/selected_config.json` 仅由 CRLF/LF 引起的工作区差异已经恢复为 Git 版本，未改变任何字段或数值。
3. 运行前已存在的本地 `AGENTS.md` 继续保持未跟踪状态，未修改、未提交。
4. NumPy `timedelta` 弃用警告可在未来独立的工程兼容任务中处理；它不影响本次对齐结论，不建议在本次复现中顺手修改。

上述清理和保留处理没有修改任何实验代码、数值结果或科学结论。本次没有发现需要修复的 Phase 6 逻辑 bug，不需要调参、重写实现或改变历史科学结论。
