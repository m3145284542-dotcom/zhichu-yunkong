# Phase 13.2 — Competition Presentation Storyboard & Slide Architecture

## A. Executive summary

**PHASE 13.2 scope:** organize the already approved scientific claims, selected evidence, and frozen Phase 13.1 visuals into one competition-defense narrative and freeze the page architecture for the next production phase.

This phase does **not** create a `.pptx`, design a master, choose fonts or colors, animate content, rerun an experiment, add a statistic, change a scientific claim, or modify a frozen scientific asset. The deliverable is a twelve-page main-deck architecture, an eleven-page appendix architecture, claim/asset/evidence mappings, and a repeatable metadata/integrity validator.

The official work title is still unknown in the frozen competition record. `DOEF：让负荷预测服务于储能削峰决策` is therefore a **presentation working title**, not a replacement for the future verified official title. The suggested subtitle is `面向储能决策的集成负荷预测方法`, which is the frozen Chinese display name of DOEF v1.0.

### Starting Git and frozen-state audit

- Branch: `main`
- Starting HEAD: `d36fcd18568b98a5980b101e213f714ddf332f12`
- Starting `git status --short`: empty; no pre-existing tracked modifications or untracked files
- Frozen algorithm baseline: `549abc314e93e2862bfc22965db89622c22890e1`
- Frozen baseline ancestry: PASS
- Baseline → Starting HEAD: ahead 10, behind 0
- Phase 7/8/9/9.1 registered artifacts: 76/76 PASS; LF-normalized drift 0
- Phase 13.0A registered sources: 88/88 PASS; LF-normalized drift 0
- Phase 13.0B registered artifacts: 8/8 PASS; LF-normalized drift 0
- Phase 13.1 frozen files (commit-created scope excluding the README progress file): 26/26 PASS; LF-normalized drift 0
- Phase 13.1 scientific visual outputs: 10/10 PASS; drift 0

The README is excluded from the Phase 13.1 immutable-file count because Phase 13.2 is explicitly permitted to append a minimal progress section. The validator separately protects every Phase 13.1 output, manifest, script, and report, and this report records that the pre-existing Phase 13.1 README section was inspected before the Phase 13.2 append.

## B. Audience assumptions

The audience may include AI specialists, electrical/energy engineers, and general technical judges. The communication job is:

> By the end, judges should understand why forecast-only model selection can miss storage-decision value, believe that DOEF addresses that mismatch under a frozen Validation/Test protocol, and remember the project-scoped engineering contribution without mistaking it for universal superiority or field deployment.

The main deck gives one-sentence explanations of normalized decision regret, the forecast-to-dispatch chain, Validation-only selection, and the difference between multi-building robustness and unseen-building transfer. Feature inventories, model parameters, full metric tables, battery equations, bootstrap details, units, and negative supporting experiments remain in the appendix.

The verified competition format is eight minutes of presentation plus five minutes of judge questions (`outputs/phase11/phase11_verdict.json`). The main deck therefore freezes twelve pages **including the title slide**. A Thank You/Q&A page is neither counted nor frozen. Slides use relative speaking priority—essential, important, compressible—rather than invented per-slide seconds.

## C. Core presentation thesis

For a downstream task such as battery peak shaving, prediction error is not the terminal engineering objective: forecast models should also be evaluated by the decisions they support. DOEF operationalizes that principle by freezing a per-building DayWeek–LightGBM ensemble weight on Validation battery regret and evaluating the unchanged pipeline on the fixed Test scope.

## D. Narrative arc

1. **Hook:** start with the frozen XGBoost/LightGBM rank reversal, not a dataset lecture.
2. **Problem:** show that a forecast becomes valuable only through the battery schedule and realized peak.
3. **Tension:** forecast-only selection and downstream-decision selection answer different questions.
4. **Solution:** define DOEF and expose the Validation-selection/Test-evaluation boundary.
5. **Evidence:** land the frozen aggregate result, then distinguish metric meaning.
6. **Breadth:** show every fixed building and the pre-result Train-only morphology rule.
7. **Credibility:** make Validation-only weight selection and no Test-time tuning explicit.
8. **Engineering value:** describe the repeatable next-day workflow while stating that no field deployment is evidenced.
9. **Contribution:** locate innovation in the decision-oriented, auditable framework—not LightGBM.
10. **Ending:** resolve the original tension with the single thesis; introduce no new result.

The sequence is cumulative. Removing the mismatch eliminates the need for DOEF; removing the pipeline leaves the metric choice unmotivated; removing the method prevents interpretation of the result; removing the all-building and Validation-only pages weakens credibility; removing the workflow and contribution pages obscures competition relevance.

## E. Frozen main-deck architecture

The authoritative machine-readable specification is `outputs/phase13_2/slide_architecture.json`. `SB-*` identifiers are organizational only and are not scientific claim IDs.

| Slide | Proposed headline | Unique role | Single takeaway | Primary visual | Claim support | Speaker intent / transition | Must not claim |
|---|---|---|---|---|---|---|---|
| SB-M01 | DOEF：让负荷预测服务于储能削峰决策 | Position the problem | Forecasting is an input to the battery decision, not the endpoint. | Minimal title; no scientific chart | CORE-01, CORE-05 | Set AI+energy frame → ask whether forecast metrics identify the best decision. | Official-title status, LightGBM novelty, cost/carbon/energy outcomes |
| SB-M02 | 更低的预测 RMSE，并未带来更低的储能决策 regret | Empirical hook | Frozen aggregate rankings reverse for XGBoost vs LightGBM. | SCI-01 | CORE-02 | Create tension → explain the engineering chain. | Forecast accuracy irrelevant; universal causality |
| SB-M03 | 预测只是中间环节，调度结果才是工程终点 | Engineering pipeline | Forecasts shape schedules evaluated on realized load. | CON-01 | CORE-01, SUP-06 | Give shared mental model → expose forecast-only selection limitation. | Conceptual visual as evidence; deployed controller |
| SB-M04 | 模型不只要预测得准，还要在 Validation 上支持更好的储能决策 | Selection contrast | Keep components fixed; change the selection criterion to Validation battery regret. | Native two-row process comparison | CORE-02, CORE-03 | Introduce DOEF response → show full frozen method. | Joint training, new base learner, replacement of all forecast checks |
| SB-M05 | DOEF 在 Validation 上按决策 regret 冻结权重，再进入 Test | Method | Per-building weights are Validation-selected and frozen before Test. | ARCH-01 | CORE-05, SUP-02, SUP-03, SUP-06 | Explain algorithm and boundary → ask whether it works. | Bilevel/online/RL; deployable Oracle; Test selection |
| SB-M06 | DOEF 同时降低预测误差与储能决策 regret | Main result | DOEF improves both frozen aggregate objectives versus LightGBM. | SCI-02 | CORE-06, CORE-07, CORE-08 | Land strongest evidence → explain metric meaning. | SOTA/universal performance, unseen scope, monetary regret |
| SB-M07 | RMSE 衡量预测误差；regret 衡量误差经过调度后的工程后果 | Metric interpretation | RMSE and regret answer different questions and need not rank methods identically. | Text-led metric-to-question comparison | CORE-02, SUP-06 | Resolve the hook without causal overreach → inspect buildings. | Proven universal error-location mechanism; useless forecast metrics |
| SB-M08 | 全部八栋固定建筑均被展示：六胜、两平、零负 | Multi-building robustness | Six regret wins and two ties are shown across every pre-selected building. | SCI-03 | CORE-04, CORE-07 | Rebut single-building/cherry-pick objection → verify selection boundary. | Unseen-building or universal generalization; Test-selected buildings |
| SB-M09 | 权重在 Validation 冻结，Test 不参与选择 | Credibility | The predeclared grid is selected on Validation and Test only evaluates. | SCI-04 | CORE-03, SUP-03 | Pre-empt Test-tuning objection → move to the frozen workflow. | Pristine never-viewed Test; Test optimization; universal weight effect |
| SB-M10 | 冻结流程明确了次日预测如何生成储能调度，但尚非现场部署 | Engineering workflow | The method defines a repeatable next-day process, not a field-deployed system. | ARCH-01 transparent process view | CORE-05, SUP-02, SUP-06 | Translate evaluation into an operating sequence → state contribution. | Field deployment, industrial real-time proof, future inputs |
| SB-M11 | 创新不在基础预测器，而在把模型选择对齐储能决策 | Innovation | Innovation is the auditable decision-oriented framework, not LightGBM. | CON-02 | CORE-02/03/04/05, SUP-03/06 | State three evidence-backed contributions under one thesis → close. | First/world-first/SOTA; base-model novelty; deployed end-to-end system |
| SB-M12 | 让预测评价与最终储能决策对齐 | Conclusion | Judge forecast models by both prediction error and supported engineering decisions. | Text-led close | CORE-01 through CORE-07 | Resolve the opening; stop without a new claim. | New result, universal scope, economic/carbon/energy/deployment value |

## F. Appendix architecture

These pages are intentionally outside the eight-minute narrative because they provide audit depth rather than advancing the core proof:

| Slide | Title / role | Why appendix |
|---|---|---|
| SB-A01 | 建筑范围在结果评估前冻结 — dataset and Train-only selection | Necessary for selection/cherry-picking Q&A; too detailed for the main arc |
| SB-A02 | 因果特征与时间切分共同约束信息边界 — chronological split | Leakage and prior Test-visibility detail |
| SB-A03 | 基础模型是对照与组件，不是被包装的创新点 — baselines/components | Prevents a model-family catalogue in the main deck |
| SB-A04 | 同一冻结电池约束保证方法间可比 — battery/optimizer/units | Physical and optimization detail for engineering judges |
| SB-A05 | 完整预测指标用于核查，不替代下游决策评价 — full forecast metrics | Dense audit table |
| SB-A06 | 决策指标必须连同范围与聚合口径一起解释 — full decision metrics | Dense table plus aggregation caveats and negative cases |
| SB-A07 | 冻结调度轨迹只用于说明流程，不代表普遍表现 — frozen dispatch reuse | Phase 13.1 explicitly marks SCI-05 backup-only |
| SB-A08 | 逐建筑权重来自预先声明的 Validation 搜索 — weight grid/details | Full grid and per-building weights are Q&A detail |
| SB-A09 | 冻结 bootstrap 支持固定八栋建筑范围内的差异 — uncertainty | Existing statistical evidence only; no new test |
| SB-A10 | 报告公式与冻结预测逐值一致 — lineage/reproducibility | Identity-audit detail |
| SB-A11 | 负结果被保留，但不用于 Test 后反向改选算法 — falsification | Supporting negative experiment, not a DOEF component |

### DO NOT PRESENT

The twelve Phase 13.0B rejected claim categories remain excluded from both the main deck and appendix as positive claims: unseen-building transfer, monetary savings, carbon reduction, energy-use reduction, broader building scope, broader temporal scope, pristine never-viewed Test, universal BDG2 count, one universal peak scalar, robust-optimization improvement, external first/novel/SOTA positioning, and universal superiority.

## G. Claim coverage audit

- Approved Phase 13.0B presentation-safe claims available: 21 (8 core, 8 supporting, 5 backup)
- Unique approved claims used in the main deck: 11
- Unique approved claims used in the appendix: 21
- Approved claims unused across the full architecture: 0
- Unsupported main-deck claims: 0
- Rejected claims promoted into the deck: 0
- Main-deck exact numbers without a traceability row: 0

The appendix's complete coverage is not a requirement to show every page; it is a Q&A routing architecture. Main-deck claims are deliberately narrower.

## H. Visual asset coverage

All eight Phase 13.1 canonical assets have an explicit assignment:

| Asset | Assignment | Reason |
|---|---|---|
| SCI-01 forecast/decision mismatch | SB-M02 MAIN | Central empirical hook |
| SCI-02 DOEF main results | SB-M06 MAIN | Strongest frozen aggregate evidence |
| SCI-03 eight-building regret | SB-M08 MAIN | Complete fixed-building view |
| SCI-04 Validation weight selection | SB-M09 MAIN; SB-A08 APPENDIX | Anti-leakage proof and detailed Q&A |
| SCI-05 frozen dispatch reuse | SB-A07 APPENDIX | Frozen manifest says representative and backup-only |
| ARCH-01 DOEF architecture | SB-M05, SB-M10 MAIN; SB-A02 APPENDIX | Method, workflow boundary, and split Q&A |
| CON-01 prediction/decision bridge | SB-M03 MAIN | Non-quantitative engineering explanation |
| CON-02 contribution overview | SB-M11 MAIN | Project-scoped contribution summary |

No scientific content may be modified. The next phase may scale assets, fit whitespace, crop only non-scientific outer areas, and add external titles/callouts that do not obscure labels. It may not redraw plots, change axes or values, reorder/delete buildings, remove interpretive annotations, or extract new numbers from images.

## I. Story consistency audit

1. Prediction accuracy and decision quality are explicitly distinguished on SB-M02, SB-M03, and SB-M07: PASS.
2. No slide claims DOEF has universally better forecast accuracy: PASS.
3. Validation-selected is never rewritten as Test-optimized; SB-M05/SB-M09 make the boundary explicit: PASS.
4. Eight-building evidence is called fixed-scope multi-building robustness, not universal generalization: PASS.
5. SB-M10 distinguishes a frozen/repeatable workflow from actual field deployment: PASS.
6. The observed mismatch is not upgraded to a fully proven causal mechanism: PASS.

## J. Storyboard stress test

| Judge question | Coverage | Frozen answer boundary |
|---|---|---|
| 1. Are you changing metrics because forecast accuracy was poor? | MAIN — SB-M02, SB-M04, SB-M06 | No. The deck retains forecast metrics and shows the frozen project-scoped mismatch; DOEF improves normalized MAE as well as regret versus LightGBM. |
| 2. How is DOEF different from an ordinary ensemble? | MAIN — SB-M04, SB-M05, SB-M11 | The weighted formula is simple; the contribution is Validation downstream-regret selection and the auditable forecast-to-dispatch evaluation loop. |
| 3. Were weights chosen after seeing Test? | MAIN — SB-M05, SB-M09; APPENDIX — SB-A02, SB-A08 | No Test-based selection. Test had historical visibility, so do not call it pristine. |
| 4. Why only eight buildings? | MAIN — SB-M08; APPENDIX — SB-A01 | Fixed quality filtering and Train-only morphology created a heterogeneous, auditable benchmark. Evidence beyond eight is unavailable. |
| 5. Were the eight favorable buildings cherry-picked? | MAIN — SB-M08; APPENDIX — SB-A01 | No Validation/Test performance selected the morphology representatives; raw coverage eligibility is disclosed separately. |
| 6. Is LightGBM the innovation? | MAIN — SB-M01, SB-M04, SB-M11; APPENDIX — SB-A03 | No. LightGBM is a frozen component/baseline. |
| 7. Why can lower MAE/RMSE produce worse storage performance? | MAIN — SB-M02, SB-M03, SB-M07; APPENDIX — SB-A07 | The metrics evaluate different endpoints. Only the observed mismatch and workflow interpretation are supported; a universal causal mechanism is not. |
| 8. Is your method best for every building? | MAIN — SB-M06, SB-M08; APPENDIX — SB-A06 | Against LightGBM regret it is 6/2/0 in the fixed set, but universal superiority across all methods/metrics is unsupported; a negative peak-reduction building is retained. |
| 9. Has it been deployed? | MAIN — SB-M10 | No. The evidence is an offline frozen evaluation and a deployment-oriented workflow, not field deployment. |
| 10. Are the battery parameters realistic? | MAIN — SB-M03/SB-M10 high-level; APPENDIX — SB-A04 | Parameters and physical constraints are frozen and consistently applied. Field realism across installations is **unsupported / cannot claim**. |
| 11. If forecasts are inaccurate, can the optimizer fail? | MAIN — SB-M03, SB-M07; APPENDIX — SB-A06, SB-A07 | Forecast-driven schedules can degrade realized peak outcomes, and negative cases are retained. A universal robustness guarantee is **unsupported / cannot claim**. |
| 12. What are the AI innovation and electrical-engineering value? | MAIN — SB-M11, SB-M12 | AI: decision-oriented Validation selection. Engineering: direct forecast-to-storage evaluation under shared battery constraints. No external novelty-priority claim. |

## K. Slide architecture quality audit

### One-slide-one-message

Every main slide has one string-valued `single_takeaway` and one `core_question`. SB-M11's three contribution statements are subordinate evidence for one message: innovation lies in framework alignment, not the base learner.

### Evidence density

- One dominant frozen visual per result/method page.
- No main-deck full table, feature inventory, parameter grid, formula derivation, or bootstrap interval.
- SB-M06 shows only the Phase 13.1 approved summary visual and its retained caveat.
- SB-M07 and SB-M12 are intentionally text-led to avoid redundant charts.

### Narrative dependency

Every slide records `transition_from` and `transition_to`. The order is deterministic in `main_deck_order`; the main slides are not intended to be permuted.

### Redundancy

- SB-M02 proves an observed rank reversal; SB-M07 explains that the metrics answer different questions. They are not interchangeable.
- SB-M05 defines the whole method; SB-M09 isolates the selection boundary and anti-Test-tuning evidence. They are not interchangeable.
- SB-M06 reports aggregate outcomes; SB-M08 shows every building and the pre-selection scope. They are not interchangeable.

### Time efficiency

The verified eight-minute presentation constraint is honored through relative priorities:

- Essential: SB-M02, SB-M05, SB-M06, SB-M08, SB-M09, SB-M12
- Important: SB-M01, SB-M03, SB-M04, SB-M10, SB-M11
- Compressible: SB-M07
- Appendix-only: SB-A01 through SB-A11

No per-slide duration is frozen in this architecture; pacing and rehearsal belong to presentation production.

## L. Freeze statement and next phase boundary

The narrative, main slide order, page roles, approved claim bindings, evidence bindings, asset allocation, caveats, and appendix routing are frozen by this phase. The only next allowed phase after a passing validation is **Phase 13.3 — Competition Presentation Production**.

Phase 13.2 only freezes the storyboard and slide architecture. No PPT was created.
