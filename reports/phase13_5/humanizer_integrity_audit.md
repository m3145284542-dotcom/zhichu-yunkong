# Nature → Humanizer 事实一致性审计

状态：PASS

| 检查项 | 变化数量 | 结果 |
| --- | ---: | --- |
| 数值 | 0 | PASS |
| 科学 claim | 0 | PASS |
| 公式 | 0 | PASS |
| 参数 | 0 | PASS |

## 审计方法

- 比较 Nature 与 Humanizer 版本中的全部数值、百分比、日期和实验规模 token，多重集完全一致。
- 比较全部块级 LaTeX 公式，顺序和内容完全一致。
- 检查 DOEF、LightGBM、DayWeek、XGBoost、CatBoost、Oracle、BDG2 与 8 个建筑标识在两个版本中均未被替换。
- 对核心数值、Validation/Test 边界、非端到端定义、未见建筑外推限制及成本/能耗/碳收益限制执行源值断言。
- Humanizer 只改写句法、衔接和模板化表达；未改表格、公式、图引用、参考文献或证据路径。
