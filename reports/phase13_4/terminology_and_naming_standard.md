# Phase 13.4 — Terminology and Naming Standard

| Canonical term | Required meaning / use | Prohibited ambiguity |
| --- | --- | --- |
| DOEF | Decision-Oriented Ensemble Forecasting, version 1.0 | Do not call it a new LightGBM architecture or end-to-end DFL. |
| Building Load Forecasting | 24-hour-ahead hourly building-load prediction | Do not describe it as one-hour-ahead. |
| Battery Energy Storage System (BESS) | Frozen simulated battery used for dispatch comparison | Do not imply field deployment. |
| Peak Shaving | Reduction of maximum power demand under the frozen protocol | Not energy saving, tariff saving or carbon reduction. |
| Forecast Metric | MAE, RMSE, MAPE and normalized variants | Not a downstream decision metric. |
| Decision Metric | Realized peak, peak reduction and Oracle-relative regret | Regret is not monetary regret. |
| Validation | Selection split for model/weight/tie-break rules | Never call Validation Test. |
| Test | Frozen held-out evaluation period; historical results had been viewed | Do not call it pristine, never-viewed or a selection set. |
| Dispatch | Deterministic 24-hour battery plan from the frozen optimizer | Do not call it online control. |
| Regret | Realized daily peak(method) − realized daily peak(non-deployable Oracle) | Not cost, energy or carbon regret. |
| Causal Feature | Information available at feature time: load history and calendar state | No future target or future weather. |
| Day baseline | `actual(t−24h)`; historically also Persistence | Do not duplicate Persistence and Day as different scientific methods. |
| Week baseline | `actual(t−168h)` | — |
| Day/Week baseline / DayWeek | `0.5·Day + 0.5·Week` | Not a learned model. |
| Ensemble weight | Building-specific LightGBM coefficient `w_b`; DayWeek coefficient is `1−w_b` | Do not generalize Joey's 0.3 to all buildings. |

## Units

- Raw electricity reading: **kWh per hourly interval**.
- Dispatch load/power: **interval-average kW**, derived by `P_t = E_t / Δt` with `Δt = 1 h`.
- Battery capacity and SOC: **kWh**.
- Charge/discharge power: **kW**.
- kW and kWh are not interchangeable. Equality of numerical magnitudes for one-hour intervals does not erase the semantic distinction.

## Names

- Official competition: **全球校园人工智能算法精英大赛**.
- Track: **算法主题赛（AI+能源）—科技创新组**.
- Competition-facing project title: **DOEF：让负荷预测服务于储能削峰决策**.
- Scientific algorithm display name: **DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）**.

The current PPT slide 1 abbreviates the official competition identity; the discrepancy registry controls the Phase 14 follow-up.
