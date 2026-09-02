# Phase 13.0B — Frozen Presentation Evidence Selection & Story Mapping

## Verdict

**PASS.** The frozen evidence supports an evidence-first competition story centered on the mismatch between forecast metrics and storage decision value, followed by Validation-only decision-oriented selection and bounded 8-building Test evidence. No PPT, new figure, model run, prediction, optimization, bootstrap, or new statistical test was created.

## Frozen integrity gate

- Repository: `D:/document/aic`
- Branch: `codex/phase13-visual-report-demo`
- Starting HEAD: `dc9ad91c57d1e8c9037bef8216ccad23619ce85b`
- Frozen baseline: `549abc314e93e2862bfc22965db89622c22890e1`
- Frozen baseline ancestry: PASS; baseline is an ancestor and the starting HEAD is ahead 6 / behind 0.
- Phase 7/8/9/9.1 canonical modifications from frozen baseline: 0.
- Phase 9.1 registered artifact audit: 76 artifacts, 0 hash mismatches.
- Phase 13.0A registered source hashes: 88 files, 0 drift.
- Pre-existing unrelated untracked paths were preserved and excluded: `outputs/phase13/`, `reports/phase13_implementation_plan.md`.

## Story-spine audit

| Story | Verdict | Frozen basis / boundary |
|---|---|---|
| Real problem | SUPPORTED | 24 h ahead forecast feeds battery peak-shaving evaluation; no money/carbon/energy claim. |
| Forecast accuracy ≠ decision quality | SUPPORTED | XGBoost normalized RMSE 0.216751 < LightGBM 0.216942, while XGBoost normalized regret 0.117534 > LightGBM 0.116127 on the 8-building Test aggregate. |
| Decision-oriented model selection | SUPPORTED | Predeclared 11-weight grid, Validation-only regret selection, frozen per-building weights. |
| Multi-building robustness | PARTIALLY SUPPORTED | Supported across 8 pre-selected heterogeneous offices; not unseen-building transfer. |
| DOEF v1.0 final system | SUPPORTED | Formal name and structure recovered from the registered Phase 9/9.1 sources. |
| Scientific falsification | SUPPORTED AS BACKUP | Robust LightGBM Test mean regret 20.4635 kW versus 11.1274 kW deterministic; negative result retained. |

## Claim registry

- Core: 8
- Supporting: 8
- Backup/Q&A: 5
- Rejected: 12

- `CORE-01` — 预测不是终点：24 小时前瞻负荷预测服务于电池削峰决策。
- `CORE-02` — 更低的预测 RMSE 不必然带来更好的储能决策：冻结 Test 结果中，XGBoost 的 RMSE 略优，决策 regret 却更差。
- `CORE-03` — DOEF 不只按预测误差选融合权重，而是在 Validation 上按储能决策 regret 冻结权重。
- `CORE-04` — 在 296 个办公候选中按冻结质量规则筛到 82 个，再仅用 Train 期形态预选 8 栋异质办公建筑。
- `CORE-05` — DOEF v1.0（Decision-Oriented Ensemble Forecasting）把因果预测、决策导向融合和电池削峰评估连成一条冻结流程。
- `CORE-06` — 在冻结的 8 栋建筑 Test 汇总上，DOEF 相对 LightGBM 的 normalized MAE 改善 6.36%。
- `CORE-07` — DOEF 相对 LightGBM 的 normalized decision regret 改善 3.61%，建筑级结果为 6 胜、2 平、0 负。
- `CORE-08` — DOEF 的 8 栋建筑平均削峰率为 6.44%，同时如实保留最差建筑 -1.02% 的负结果。

## Metric compression

The 2,545-item numerical manifest is reduced to 35 metrics: 19 CORE, 11 SUPPORTING, and 5 BACKUP. Every row copies its value, unit, scope, source field, and SHA-256 from a resolvable Phase 13.0A manifest item.

## Figure redundancy and redraw freeze

Phase 9 figures replace redundant Phase 7/8 result views where they express the same claim at the final reporting scope. The two Phase 8 Validation-weight curves are retained for a future combined redraw from the same frozen table; Phase 7's forecast-versus-decision rank figure is also a redraw candidate. The representative dispatch image is backup-only because it may be reused as frozen but must not be mined for new numbers.

## Slide logic

- `SLIDE-01` — **预测不是终点，削峰决策才是**: 24 h ahead load forecasting supplies advance information for battery peak shaving. Primary claim: `CORE-01`.
- `SLIDE-02` — **预测更准，决策一定更好吗？**: The project tests whether conventional forecast accuracy aligns with storage decision quality. Primary claim: `CORE-02`.
- `SLIDE-03` — **先冻结范围，再看结果**: Eight heterogeneous offices are selected with Train-only morphology after frozen eligibility filtering. Primary claim: `CORE-04`.
- `SLIDE-04` — **因果可得的 24 小时前瞻预测**: DayWeek and per-building LightGBM provide complementary frozen forecast components. Primary claim: `CORE-05`.
- `SLIDE-05` — **用真实削峰结果评价预测**: Forecasts drive the same constrained battery optimizer and are evaluated on realized load using Oracle-relative regret. Primary claim: `CORE-01`.
- `SLIDE-06` — **同一预测指标不等于同一决策排序**: The frozen multi-building benchmark compares causal baselines and tree models under one decision protocol. Primary claim: `CORE-02`.
- `SLIDE-07` — **RMSE 略优，regret 反而更差**: XGBoost versus LightGBM provides a frozen 8-building Test counterexample. Primary claim: `CORE-02`.
- `SLIDE-08` — **在 Validation 上按 regret 冻结融合权重**: The same predeclared weight grid is scored by forecast MAE and decision regret; DOEF freezes the decision-selected weight. Primary claim: `CORE-03`.
- `SLIDE-09` — **从预测到削峰的冻结系统**: Causal components, decision-selected ensemble, 24 h forecast, battery optimization, and downstream evaluation form DOEF v1.0. Primary claim: `CORE-05`.
- `SLIDE-10` — **DOEF 同时改善预测与决策指标**: Against LightGBM, DOEF improves normalized MAE by 6.36% and normalized decision regret by 3.61%. Primary claim: `CORE-07`.
- `SLIDE-11` — **平均改善不隐藏最差建筑**: Mean peak reduction is 6.44%, while the building minimum is -1.02%. Primary claim: `CORE-08`.
- `SLIDE-12` — **稳定性证据与负结果同时保留**: Building-level bootstrap and exact prediction invariance support reliability; robust optimization degradation remains in backup. Primary claim: `SUP-04`.
- `SLIDE-13` — **以决策价值约束预测模型选择**: The supported contribution is a decision-oriented, Validation-selected forecast-to-storage evaluation pipeline over 8 fixed heterogeneous offices. Primary claim: `CORE-05`.

## Innovation positioning

- **SUPPORTED** — Decision-oriented forecast evaluation: Supported as an internal project contribution; no external novelty priority claim.
- **SUPPORTED** — Validation-selected decision-oriented ensemble: Supported by frozen Validation selection and weights; not Test-selected.
- **SUPPORTED** — Forecast-to-decision integrated pipeline: Integrated evaluation pipeline, not end-to-end differentiable training or deployment.
- **PARTIALLY SUPPORTED** — Multi-building morphology-aware benchmark design: Train-only morphology and fixed heterogeneous offices are supported; generalization beyond the 8 buildings is not.
- **UNSUPPORTED** — External first/world-first/SOTA positioning: Requires a separate literature and comparable-system audit.

## Frozen limitations and forbidden wording

- `LIM-01` Safe: Multi-building evaluation across 8 pre-selected heterogeneous office buildings. Forbidden: Generalizes to all buildings.
- `LIM-02` Safe: Multi-building evaluation on fixed buildings. Forbidden: Unseen-building generalization; zero-shot transfer; transfer learning; domain adaptation.
- `LIM-03` Safe: Results on one fixed future Test month per building. Forbidden: Generalizes across seasons and years.
- `LIM-04` Safe: Test data were not used for model or ensemble selection. Forbidden: Pristine Test set; completely untouched Test set; never viewed.
- `LIM-05` Safe: Peak-demand reduction under the frozen battery protocol. Forbidden: Verified bill savings; electricity-cost savings; monetary regret.
- `LIM-06` Safe: No carbon outcome was evaluated. Forbidden: Verified carbon reduction.
- `LIM-07` Safe: The evaluated outcome is peak demand. Forbidden: Reduced building energy consumption.
- `LIM-08` Safe: The robust experiment is falsification/Q&A evidence and is not part of DOEF. Forbidden: Robust optimization improved Test performance.
- `LIM-09` Safe: State interval and unit semantics explicitly. Forbidden: kWh and kW are interchangeable.
- `LIM-10` Safe: The project's frozen BDG2 electricity table contains 1,578 building series. Forbidden: BDG2 has exactly 1,578 buildings.
- `LIM-11` Safe: Attach full method and aggregation labels. Forbidden: Peak reduction is one universal project number.
- `LIM-12` Safe: Supported internal contributions only. Forbidden: First; world-first; novel as external fact; state of the art; beats all methods.

## Structural validation

- JSON load: PASS
- CSV load: PASS
- Manifest IDs: PASS
- Claim → evidence: PASS
- Claim → metric: PASS
- Slide → claim/metric/figure: PASS
- Figure paths: PASS
- Phase 13.0A source hashes: PASS (0 drift)

## Delivery boundary

Phase 13.0B creates presentation metadata only. It does not replace or modify any upstream artifact. Future visual work must consume this frozen map and may redraw only from the registered frozen machine-readable values without changing aggregation, selection, or numbers. No PPT was created, and this phase does not enter the next stage.
