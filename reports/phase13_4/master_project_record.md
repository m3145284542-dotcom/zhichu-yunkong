# Phase 13.4 — Master Project Record

Status: **PHASE 13.4 — PASS WITH FOLLOW-UP**
Role: canonical competition-evidence audit entry for Phase 14; it does not supersede or modify scientific artifacts.

## 1. Project Identity

| Field | Frozen record |
| --- | --- |
| Competition | 全球校园人工智能算法精英大赛 |
| Track | 算法主题赛（AI+能源）—科技创新组 |
| Competition-facing project title | DOEF：让负荷预测服务于储能削峰决策 |
| Title provenance | Current Phase 13.3 title; Phase 13.2 called it a working title. Phase 13.4 freezes it as the competition-facing title without claiming that a separate registration-platform title has been verified. |
| Problem domain | AI-assisted building energy management |
| Dataset | Building Data Genome Project 2 (BDG2), electricity_cleaned.csv + metadata.csv |
| Forecasting task | 24-hour-ahead hourly building-load forecast |
| Decision task | Deterministic daily BESS dispatch for peak shaving, evaluated on realized load |
| Final algorithm | DOEF v1.0 — Decision-Oriented Ensemble Forecasting（面向储能决策的集成负荷预测方法） |
| Frozen baseline | `549abc314e93e2862bfc22965db89622c22890e1` |
| Final scientific validation | Phase 9.1 — PASS |
| Presentation | Phase 13.3 — PASS; 23 slides; audited read-only in Phase 13.4 |
| Project status | ALGORITHM FROZEN; EVIDENCE CONSOLIDATED; Phase 14 may be re-executed after follow-up review |

## 2. Final Problem Definition

`Building load forecasting → forecast error structure → battery energy storage dispatch → peak-shaving decision value`.

The project does not optimize forecast MAE/RMSE as the sole terminal objective. Frozen evidence supports the narrower statement that **forecast accuracy and downstream decision quality are related but not equivalent**: in the eight-building Test aggregate, XGBoost has slightly lower normalized RMSE than LightGBM (0.216751 vs 0.216942) while having higher normalized decision regret (0.117534 vs 0.116127). This is a project-scoped counterexample, not a universal causal law and not evidence that forecast accuracy is irrelevant.

## 3. Final Algorithm Record

- Full name: Decision-Oriented Ensemble Forecasting; abbreviation: DOEF; version: 1.0.
- Forecast horizon: 24 hours. Components: `DayWeek = 0.5·actual(t−24h) + 0.5·actual(t−168h)` and one frozen per-building LightGBM forecaster.
- DOEF formula: `ŷ_t = w_b·ŷ_t^(LightGBM) + (1−w_b)·ŷ_t^(DayWeek)`.
- Causal feature construction: current load at feature time, calendar encodings, positive lags 1/2/3/24/48/72/168/336 and shifted rolling statistics; no weather and no future target values. Complete list and per-building model parameters are canonical in `outputs/phase7/model_selection_config.json`.
- Split protocol: Phase 4.5/6 feature-time splits with target-availability purge. Anchor feature-time windows are Train 2016-01-15 through 2017-10-31, Validation 2017-11-01 through 2017-11-30, Test 2017-12-01 through 2017-12-30; the 24-hour target shift yields the documented target-time boundaries. Test has 720 hourly targets / 30 complete days per building.
- Model/config selection: per-building base-model candidates were selected before Test from Validation; DOEF searches the predeclared `0.0, 0.1, …, 1.0` weight grid on Validation mean daily regret versus the non-deployable Oracle, with frozen tie-breaks. Test is evaluation-only and cannot promote or retune the algorithm.
- Frozen weights:

| Building | w forecast | w decision (DOEF) |
| --- | ---: | ---: |
| Hog_office_Rolando | 0.9 | 0.7 |
| Hog_office_Lavon | 0.0 | 0.0 |
| Hog_office_Joey | 0.6 | 0.3 |
| Lamb_office_Caitlin | 0.4 | 0.8 |
| Robin_office_Addie | 1.0 | 1.0 |
| Lamb_office_Gerardo | 0.0 | 1.0 |
| Hog_office_Alexis | 0.6 | 0.7 |
| Hog_office_Byron | 0.9 | 0.8 |

- Downstream dispatch: every method uses the same per-building Train-scaled battery and the same deterministic daily `scipy.optimize.milp` peak-shaving formulation. Capacity is 10% of Train mean daily energy; charge/discharge power is 25% of capacity per hour; SOC is 10%–90%; initial and terminal SOC are 50% (daily reset); charge and discharge efficiencies are each 0.948683, giving 0.90 round-trip efficiency.
- Decision metrics: realized post-dispatch peak, peak reduction, and daily regret = forecast-driven realized daily peak minus non-deployable Oracle realized daily peak. Regret is not monetary regret.
- Frozen configuration sources: `outputs/phase7/model_selection_config.json`, `outputs/phase7/building_battery_configs.csv`, `outputs/phase8/run_config.json`, `outputs/phase8/selected_weights.csv`, `outputs/phase9/final_algorithm.json`, and `outputs/phase9_1/final_reporting_summary.json`.

## 4. Dataset Record

- Dataset: Building Data Genome Project 2. Final multi-building work reads `data/raw/electricity_cleaned.csv` and `data/raw/metadata.csv`; the Phase 2 campus aggregate manifest is historical and is not the Phase 7–9 benchmark source.
- Electricity semantics: raw meter values are kWh per one-hour interval; dispatch interprets them as interval-average kW using `P_t = E_t/Δt`. Numeric values coincide only because `Δt = 1 h`. Battery capacity/SOC use kWh and charge/discharge limits use kW.
- Coverage used by the frozen forecast protocol: 2016-01-15 through 2017-12-30 at feature time for the anchor configuration; fixed 24-hour target shift; Validation November 2017 and Test December 2017 (720 target hours / 30 complete days per building).
- Project universe: 1,578 building-series rows in the frozen Phase 3 selection table; 296 office candidates; 82 passed deterministic coverage/quality rules; 8 were selected.
- Canonical anchor: `Hog_office_Rolando`.
- Final eight-building benchmark: Hog_office_Rolando, Hog_office_Lavon, Hog_office_Joey, Lamb_office_Caitlin, Robin_office_Addie, Lamb_office_Gerardo, Hog_office_Alexis, Hog_office_Byron.
- Selection principle: anchor plus deterministic farthest-point sampling on robust-scaled **Train-only** load morphology among eligible buildings. Validation/Test forecast or decision performance was not used; therefore this is fixed multi-building evidence, not unseen-building transfer.

## 5. Experimental Timeline

| Stage | Verified role |
| --- | --- |
| Phase 3 | Single-building baseline and frozen project selection table |
| Phase 4 | Causal LightGBM forecasting |
| Phase 4.5 | Forecast diagnostics and canonical split protocol |
| Phase 5 | Deterministic battery peak-shaving evaluation |
| Phase 5.5 | Frozen robustness and sensitivity analysis |
| Phase 5.6 | Forecast-lineage repair and deterministic reproduction |
| Phase 5.7 | Robust-dispatch negative result retained |
| Phase 6 | Decision-oriented forecasting baseline |
| Phase 7 | Train-only eight-building deterministic benchmark |
| Phase 8 | Validation-only decision-oriented ensemble |
| Phase 9 | Final algorithm validation and DOEF v1.0 freeze |
| Phase 9.1 | Final methodology/statistical reporting audit |
| Phase 10 | Final deliverable gap audit |
| Phase 11 | Competition rules verification |
| Phase 12 | Innovation positioning and claim freeze |
| Phase 13.0A | Presentation scientific source freeze: 88/88 PASS |
| Phase 13.0B | Presentation evidence selection: 8/8 PASS |
| Phase 13.1 | Frozen visual assets |
| Phase 13.2 | Frozen 12-main + 11-appendix storyboard |
| Phase 13.3 | Accepted 23-slide competition PPTX |
| Phase 13.4 | Master evidence record and registries |

## 6. Source-of-Truth Priority

1. Phase 7/8/9/9.1 canonical machine-readable scientific artifacts.
2. Frozen scientific integrity manifests and hashes.
3. Canonical code/config used to produce those artifacts.
4. Phase 13.0A / 13.0B frozen evidence records.
5. Phase 13.1 frozen figures and visual manifest.
6. Phase 13.2 frozen storyboard.
7. Phase 13.3 competition presentation.
8. Earlier narrative reports.
9. README.
10. Historical prompts or conversation descriptions.

If presentation wording conflicts with a canonical machine-readable result, the machine-readable result wins. Phase 9.1's building-level bootstrap is the primary uncertainty statement; the earlier Phase 9 building-day bootstrap remains secondary sensitivity evidence. No conflict is resolved by rerunning experiments.

## 7. Competition Evidence Summary

- DOEF vs LightGBM on the fixed eight-building Test aggregate: normalized MAE 0.137970 vs 0.147338 (6.3585% relative improvement); normalized decision regret 0.111929 vs 0.116127 (3.6147% relative improvement); building decision-regret win/tie/loss 6/2/0.
- Peak-shaving scope: DOEF mean whole-window peak reduction 6.4423%, median 5.6291%, minimum -1.0170%; the negative building case is retained.
- Generalization boundary: evidence spans eight preselected office buildings and one fixed future Test month per building; it does not establish universal, unseen-building, seasonal or cross-year generalization.
- Negative results: Phase 5.7 robust dispatch degraded Test regret; Phase 9 peak-aware LightGBM did not produce stable gains; CatBoost's extreme negative peak case and DOEF's negative minimum building remain visible.

## 8. Presentation Audit and Innovation Boundaries

All 23 slides were read from the PPTX XML. The evidence map inventories titles, major claims, numbers, figures, algorithm descriptions, contribution statements, result summaries and appendix caveats. The defensible innovation narrative is the auditable decision-oriented model-selection/evaluation framework: downstream Validation regret selects a transparent fixed blend, followed by controlled multi-building evaluation with frozen dispatch. LightGBM, lag features, the generic battery model and generic peak-shaving optimization are not claimed as original algorithms.

Open follow-up items are authoritative in `outputs/phase13_4/discrepancy_registry.csv`. Phase 13.4 does not modify the PPTX.

## 9. Freeze Declaration and Phase 14 Contract

- DOEF v1.0 remains **ALGORITHM FROZEN**. Algorithm development ended at Phase 9.1.
- New experiments/statistical tests in Phase 13.4: 0.
- Modified canonical scientific artifacts: 0.
- Modified Phase 13.1 figures, Phase 13.2 storyboard or Phase 13.3 PPTX: 0.
- Phase 7/8/9/9.1 integrity: 76/76 PASS; LF-normalized drift = 0.

Phase 14 must begin from this Master Project Record and its machine-readable registries. It must resolve or explicitly disposition open presentation/Git discrepancies without changing scientific claims, frozen weights, predictions, dispatch or negative results.
