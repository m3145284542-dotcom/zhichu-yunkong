# Phase 9.1 — Final Methodology & Reporting Audit

## Audit scope and frozen algorithm

Phase 9.1 changes statistical aggregation, methodology semantics, and reporting language only. It does not alter DOEF Test predictions, Phase 8 weights, selected buildings, model parameters, battery configurations, forecast horizon, optimizer, or dispatch constraints.

**DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法）** was fixed before Test evaluation by the Phase 8 Validation downstream storage-decision objective. `algorithm_selection_source = Validation`; `test_role = evaluation_only`.

Peak-aware LightGBM was evaluated as a frozen supporting experiment and did not demonstrate stable benefit. It has no authority to replace or promote an algorithm based on Test results.

DOEF is defined as `ŷ_t = w_b ŷ_t^(LightGBM) + (1-w_b) ŷ_t^(DayWeek)`, with `ŷ_t^(DayWeek) = 0.5 y_(t-24) + 0.5 y_(t-168)`. Each building-specific `w_b` is `w_decision` from `outputs/phase8/selected_weights.csv`, selected on Validation decision regret. The base forecasters are not claimed as novel; the contribution is the decision-oriented model-selection and ensemble framework.

## Evaluation scope and building selection

This is a **multi-building robustness evaluation** across eight heterogeneous office buildings. Each building uses its own historical training data and is evaluated on its own fixed future Test window; the experiment does not evaluate transfer to a completely new building.

Candidate buildings were first screened using fixed raw-data coverage requirements over the predefined evaluation windows. Among eligible buildings, representative sampling used only Train-period load morphology statistics and did not use Validation/Test forecasting or storage-decision performance. Future-window raw availability is therefore disclosed separately from Train-only morphology selection.

## Unit semantics

BDG2 electricity readings are hourly interval energy, `E_t` in kWh. The dispatch model uses interval-average power `P_t = E_t / Δt`; here `Δt = 1 h`, so the numerical value is unchanged while the physical interpretation is kW. Battery capacity and SOC are kWh; charge/discharge limits are kW. Peak metrics refer to interval-average power, while charge/discharge energy and throughput refer to kWh.

## Metric dictionary

- **Normalized mean daily decision regret vs Oracle:** the mean daily realized peak from forecast-driven dispatch minus the non-deployable Oracle daily peak, divided by Phase 7 Train mean load. This is the primary decision metric used for Validation selection, win/tie/loss, and the formal building-level bootstrap.
- **Peak reduction percentage:** `100 × (maximum original Test-window peak − maximum post-dispatch Test-window peak) / maximum original Test-window peak`. This is a whole-window peak-shaving metric, not the decision-regret comparison.

The project contains no energy-use, tariff, demand-charge, cost, or carbon model. Reported percentages describe simulated peak shaving only under the frozen battery and dispatch protocol.

## Formal building-level paired bootstrap

| building | mean_daily_regret_doef | mean_daily_regret_lightgbm | train_mean_load | normalized_difference |
| --- | --- | --- | --- | --- |
| Hog_office_Rolando | 10.400277 | 11.127372 | 305.323958 | -0.002381 |
| Hog_office_Lavon | 3.593370 | 5.564642 | 297.503066 | -0.006626 |
| Hog_office_Joey | 80.435709 | 85.504438 | 1190.734709 | -0.004257 |
| Lamb_office_Caitlin | 5.236262 | 5.479727 | 21.494302 | -0.011327 |
| Robin_office_Addie | 2.531494 | 2.531494 | 20.928938 | 0.000000 |
| Lamb_office_Gerardo | 2.231236 | 2.231236 | 8.544768 | 0.000000 |
| Hog_office_Alexis | 2.335955 | 2.473627 | 19.356408 | -0.007112 |
| Hog_office_Byron | 33.702481 | 35.491210 | 952.907213 | -0.001877 |

The equal-building point estimate for DOEF − LightGBM normalized mean daily regret is **-0.004198**. The 10,000-resample paired building bootstrap (seed 42, eight resampling units) gives a 95% percentile interval of **[-0.006850, -0.001719]** and `P(bootstrap mean < 0) = 1.0000`. The interval remained below zero in this experimental setting; no separate claim of statistical significance is made.

The historical Phase 9 building-day bootstrap is retained as a secondary temporal-resampling sensitivity analysis. Its 240 pairs treat dates within a building as resampling units and are not the primary evidence for variation across buildings.

## Forecast and decision objectives

Forecast-error minimization and downstream-decision optimization are not generally equivalent objectives. The complete Phase 8 weight table is:

| building | w_forecast | w_decision | weights_differ |
| --- | --- | --- | --- |
| Hog_office_Rolando | 0.9 | 0.7 | 1.0 |
| Hog_office_Lavon | 0.0 | 0.0 | 0.0 |
| Hog_office_Joey | 0.6 | 0.3 | 1.0 |
| Lamb_office_Caitlin | 0.4 | 0.8 | 1.0 |
| Robin_office_Addie | 1.0 | 1.0 | 0.0 |
| Lamb_office_Gerardo | 0.0 | 1.0 | 1.0 |
| Hog_office_Alexis | 0.6 | 0.7 | 1.0 |
| Hog_office_Byron | 0.9 | 0.8 | 1.0 |

The weights differ for **6/8** buildings. The aggregate Phase 9 benchmark happens to select DOEF as both the lowest mean normalized forecast-error method and the lowest mean normalized decision-regret method; that aggregate coincidence does not make the two objectives generally equivalent.

## Final benchmark and decision comparison

| display_name | normalized_mae_mean | normalized_rmse_mean | normalized_peak_mae_mean | normalized_decision_regret_mean | normalized_decision_regret_median | peak_reduction_mean_pct | peak_reduction_median_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Day Persistence | 0.225885 | 0.430193 | 0.361189 | 0.162986 | 0.150110 | -1.878452 | 0.635163 |
| Week | 0.201578 | 0.328414 | 0.257630 | 0.144323 | 0.137660 | 3.085463 | 4.772076 |
| DayWeek | 0.183478 | 0.296621 | 0.263659 | 0.143019 | 0.112592 | 4.906898 | 5.573690 |
| LightGBM | 0.147338 | 0.216942 | 0.217360 | 0.116127 | 0.096382 | 1.008432 | 5.057121 |
| XGBoost | 0.149781 | 0.216751 | 0.211440 | 0.117534 | 0.092679 | 0.452834 | 4.588390 |
| CatBoost | 0.173604 | 0.239211 | 0.231382 | 0.118740 | 0.094275 | -24.482416 | 4.820861 |
| DOEF | 0.137970 | 0.207822 | 0.207196 | 0.111929 | 0.094116 | 6.442332 | 5.629144 |
| Peak-aware LightGBM | 0.147587 | 0.217284 | 0.217371 | 0.116202 | 0.096382 | 1.128813 | 5.057121 |

Across the eight evaluated buildings, DOEF reduced mean normalized decision regret from 0.11613 for LightGBM to 0.11193. Building-level **decision-regret** win/tie/loss was **6/2/0**; this is not a peak-reduction win count.

## CatBoost extreme-result retention

CatBoost Test-window peak reduction is reported without deletion or winsorization: mean -24.48242%, median 4.82086%, minimum -245.94331%, and maximum 13.23669%. Hog_office_Lavon remains in the result. The small original-peak denominator and peak-timing error are consistent with the saved diagnostics and can amplify the percentage; this is not presented as a newly identified causal mechanism.

## Limitations and reproduction

The conclusions are limited to the eight office buildings, fixed data windows, one-hour resolution, 24-hour horizon, frozen battery sizing, daily SOC reset, and recorded CPU environment. Additional compute overhead was small in that recorded environment; no claim of industrial deployment readiness is made.

Reproduce the audit with `python scripts/run_phase9_1.py`; verify with `python -m unittest discover -s tests -v`. Canonical audit artifacts are registered in `outputs/phase9_1/data_lineage.json` and loaded fail-closed by `src.final_algorithm.load_final_algorithm()`.
