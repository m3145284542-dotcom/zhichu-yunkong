# Phase 13.5 正式科研图中文化审计

状态：PASS

| 检查项 | 数量 |
| --- | ---: |
| 正式报告图 | 4 |
| 已中文化图 | 4 |
| 残留英文语义标签 | 0 |
| 字体异常 | 0 |

## 审计范围与方法

- 扫描 `outputs/phase13_5/figures_cn/*.svg` 的全部文本节点。
- 允许 DOEF、LightGBM、XGBoost、DayWeek、MAE、RMSE、MAPE、SOC、kW、kWh、数学变量及冻结建筑标识；其他英文词计为语义标签残留。
- 渲染器实际解析字体：`Microsoft YaHei`；每个 SVG 均声明 Microsoft YaHei。
- 4 张 2400 × 1350 PNG 已逐张目视检查，未见乱码、方框字符、文字消失、裁切或错位。
- 代表性 frozen dispatch 原图含英文栅格文字，未作为正式报告插图；其复用证据改由正文表 6 和 5,760 点预测一致性记录呈现。

残留项：无
字体异常：无
