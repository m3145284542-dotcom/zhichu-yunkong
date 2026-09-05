# Claim consistency — PASS

Inherited mapping: Phase 13.5 claim_traceability.md C01–C18 and Phase 13.4 master record/language guide. Claims themselves are unchanged. Machine checks: qa/technical_audit.json.

| Claim | Frozen evidence reviewed | Boundary preserved |
|---|---|---|
| Forecast ≠ decision | Phase 9 final_benchmark.csv: XGBoost RMSE 0.216751 < 0.216942; regret 0.117534 > 0.116127 | Project-specific counterexample, not universal causality |
| DOEF idea | Phase 9.1 final_reporting_summary.json; Phase 9 final_algorithm.json | Fixed per-building LightGBM/DayWeek blend, not end-to-end learning |
| Validation selection | Summary selection_source=Validation; Phase 8 selected_weights.csv | All 8 weight pairs preserved; 6 differ across selection objectives |
| Test role | Summary evaluation_only; test_can_promote_algorithm=false | Historical Test visibility caveat retained |
| Frozen reuse | Summary invariance: 5,760 samples, maximum difference 0.0; 76-file hash audit | No new prediction/model/dispatch run |
| Multi-building scope | Summary: 8 buildings; not_unseen_building_transfer=true | Fixed office sample and one future month |
| Regret | Phase 9.1 metric_semantics.json | Realized daily peak minus non-deployable Oracle, normalized by Train mean; not money |
| Battery | Phase 7 building_battery_configs.csv; unchanged MILP equations | Train-scaled capacity; 25%/h power; 10–90% SOC; 50% daily endpoints; 90% round trip |
| DOEF results | Frozen summary/benchmark: 6.3585%, 3.6147%, 6/2/0 | Negative minimum -1.0170% remains |
| Bootstrap | Frozen summary: -0.004198, interval [-0.006850,-0.001719], 10,000 resamples | Existing descriptive result; no new test or significance claim |
| Failed experiments | Phase 5.7 summary 20.4635 vs 11.1274 kW; Phase 9.1 peak-aware role=rejected | Supporting negative results, never promoted |
| Engineering value | Metric semantics has no tariff/cost/carbon outcome model | Simulation relevance only, no quantified deployment savings |

Scientific semantic changes: 0. Key-number mismatches: 0. The author correction does not change any scientific proposition or the reference set.
