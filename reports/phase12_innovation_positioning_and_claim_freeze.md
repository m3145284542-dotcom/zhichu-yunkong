# Phase 12 — Innovation Positioning & Claim Freeze

Status: **PASS / CLAIMS AND KEY NUMBERS FROZEN**  
Date: 2026-09-01  
Branch: `codex/phase12-claim-freeze`  
Starting repository HEAD: `c0ffedf4e57482caf3175bcb2fa0ebde1784ee7c`  
Algorithm baseline: `549abc314e93e2862bfc22965db89622c22890e1`  

## 1. Executive Verdict

Phase 12 passes. Phase 13 may begin, but only under the handoff contract in Section 19.

The defensible competition position is deliberately narrower than the provisional pre-research position:

1. **CORE-1 — LEVEL B, MEDIUM-HIGH confidence.** DOEF is a specific, transparent and auditable adaptation of established value-oriented forecasting: per-building Validation battery regret selects a fixed deterministic DayWeek–LightGBM blend before Test.
2. **CORE-2 — LEVEL C, HIGH confidence.** The frozen experiment provides a clear forecast-to-decision mismatch result; it is not a first discovery.
3. **CORE-3 — LEVEL C, HIGH confidence.** The representative-building protocol and retained failures are evaluation-rigor contributions, not forecasting innovation or unseen-building transfer.

No LEVEL A claim is approved. The adversarial review found strong prior art for value-oriented model selection, decision-focused forecast pooling, task-specific battery-forecast errors and end-to-end energy-storage DFL. These works do not erase CORE-1's exact implementation difference, but they make any “first”, “entirely new” or “new DFL algorithm” wording indefensible.

## 2. Repository / Freeze Boundary

The read-only start audit found a clean `codex/phase12-pre-research` branch at `c0ffedf4e57482caf3175bcb2fa0ebde1784ee7c`. Formal work therefore continued on a new branch, `codex/phase12-claim-freeze`, with the same parent.

Phase 12 changed only narrative and evidence artifacts under `reports/phase12_*` and `outputs/phase12/`. It did not retrain, retune, change features, alter splits, change building selection, modify weights, run a new forecast, run a new dispatch, create a new bootstrap or modify Phase 7/8/9/9.1 canonical artifacts. Existing outputs were read and recomputed only for consistency checks.

The canonical source-to-consumer graph is:

```text
Phase 7/8/9/9.1 canonical evidence
        + Phase 10 delivery/lineage audit
        + Phase 11 verified competition context
        + verified primary prior art
                         ↓
        Phase 12 formal claims + number ledger
                         ↓
        Phase 13 report/figures → Phase 14 PPT/script/video
```

Phase 12 files are consumers of frozen sources; they do not replace or promote an upstream model, dataset, forecast or dispatch artifact.

## 3. Phase 11 Competition Context

The only permitted competition context is **算法主题赛（AI+能源）—科技创新组**. The frozen scoring structure is:

| Criterion | Points |
|---|---:|
| 问题聚焦与创新价值 | 20 |
| 需求洞察与背景分析 | 10 |
| 技术深度与框架构建 | 25 |
| 实验验证与结果分析 | 25 |
| 应用价值与推广潜力 | 10 |
| 反思局限与未来展望 | 10 |

The rubric for **算法创新赛—算法模型创新** must not be imported. This matters because the defensible strength is a method adaptation plus rigorous evidence, not a claim of new learning theory.

## 4. Pre-Research Inputs

The Phase 12 pre-research report, registry, closest-work table, provisional claim matrix, innovation JSON, source audit and prohibited-claims file were read as discovery inputs only. Their status was `PRE-RESEARCH / PROVISIONAL / NOT FROZEN`; no provisional conclusion was copied without renewed external and internal checks.

The formal audit corrected or strengthened several inputs:

- L005 author metadata is now verified.
- L015 and L016 were checked beyond titles and abstracts.
- L020, a 2021 task-specific battery-storage forecast-error paper, was elevated to closest prior art.
- L019, a 2025 data-centric task-oriented PV-BESS paper, and L021/L022 same-author/citation-chain work were added.
- Current 2026 storage DFL work L017/L018 was verified and used to police the end-to-end boundary.
- A 2026 tariff-aware controller paper, L023, is retained as partial evidence only because author metadata was not verified; it is not used to establish a core conclusion.

## 5. Adversarial Literature Method

The search objective was to falsify novelty, not to collect supportive citations. Searches combined:

- decision-oriented, decision-aware, decision-focused, task-oriented, value-oriented, value-driven and predict-then-optimize forecasting;
- downstream-selected, cost-aware, task-aware and value-based forecast combinations, pooling, ensemble weights and model selection;
- building/load forecasts with battery scheduling, BESS, peak shaving, demand charges and operational value;
- end-to-end DFL, differentiable optimization, SPO+, smart predict-then-optimize and energy storage.

Source priority was publisher/DOI, open primary manuscript, official institution, official code repository, dataset/project page, then high-quality review. Search snippets, blogs and secondary summaries were not used as core evidence.

For L015, the Springer chapter/KIT full text was checked for formulation, component forecast models, meta-learning selection, downstream cost, 300-building scope and split design. For L016, the open Elsevier article, institutional manuscript and official code repository were checked for the probabilistic linear pool, downstream expected-cost objective, gradient/performance-based weighting and the solar-trading/wind-scheduling cases.

Backward references, forward-citation results available at the search date, related work and same-author work were checked around L015/L016. This found L021 and L022 around the dispatchable-feeder line and confirmed L016's general mechanism was already a direct decision-focused combination method. No verified paper was found that simultaneously matched all six narrow elements: building load point forecasts, DayWeek/tree convex blend, constrained battery peak shaving, held-out Validation regret choosing the weight, Test evaluation only, and no end-to-end retraining. This is a bounded search finding, not proof that no such paper exists anywhere.

## 6. Closest Prior Art

### L015 — Werling et al. (2024)

`Automating Value-Oriented Forecast Model Selection by Meta-learning: Application on a Dispatchable Feeder`, DOI `10.1007/978-3-031-48649-4_6`.

Overlap: deterministic forecasts, building-level PV-battery operation, downstream forecast value, and model selection over 300 buildings.

Difference: L015 trains a meta-classifier to select one discrete forecast model for a building from metadata. DOEF directly evaluates a fixed grid of two-model convex blends on each building's chronological Validation battery regret. DOEF does not train a cross-building selector and makes no unseen-building transfer claim.

Implication: value-oriented model selection for building battery operation predates DOEF. CORE-1 cannot claim conceptual priority.

### L016 — Stratigakos et al. (2025)

`Decision-focused linear pooling for probabilistic forecast combination`, DOI `10.1016/j.ijforecast.2024.11.006`.

Overlap: forecast combination weights are chosen with downstream decision cost because forecast-score-optimal weights may not produce the best decisions.

Difference: L016 combines probabilistic densities and learns static or contextual pools through nested stochastic optimization, using differentiable and performance-based methods in solar trading and wind grid scheduling. DOEF is a deterministic two-point load forecast, finite weight grid and fixed building-battery peak-shaving optimizer, without end-to-end training.

Implication: “first decision-focused ensemble” is contradicted. The remaining distinction is an application/mechanism adaptation, hence LEVEL B at most.

### L020 — Singleton and Grindrod (2021)

`Forecasting for Battery Storage: Choosing the Error Metric`, DOI `10.3390/en14196274`.

Overlap: battery peak reduction, task-specific forecast evaluation, and optimized weights in a simple weighted historical-demand predictor.

Difference: L020 uses a surrogate time-series shape error derived for competition aims; it does not use the realized regret of the exact constrained optimizer to choose a frozen blend of pre-existing forecast models under a separate Validation/Test protocol.

Implication: broad “battery-aware forecasting” and “task-aware forecast weighting” claims are old. DOEF's defendable difference must name the optimizer-regret Validation mechanism.

### Additional strong boundaries

- L007/L008 directly show statistical forecast quality and storage value can diverge; CORE-2 is not a first discovery.
- L019 changes training data to maximize PV-BESS task value; L017/L018 train predictors with downstream battery objectives. DOEF must not be described as end-to-end DFL.
- L004–L006 establish forecast-driven battery peak-shaving pipelines; application integration alone is LEVEL E, not algorithm novelty.

## 7. DOEF vs Closest Prior Work

| Element | DOEF | L015 | L016 | L020 |
|---|---|---|---|---|
| Forecast target | Building load point forecast | Building prosumption point forecast | Solar/wind probabilistic forecast | Load point forecast |
| Combination | Two-model deterministic convex blend | Discrete model selection | Probabilistic linear pool | Weighted historical weeks plus regression |
| Downstream task | Constrained battery peak shaving | PV-battery dispatchable feeder cost | Solar trading / wind grid scheduling cost | Battery competition peak reduction |
| Selection signal | Realized daily regret vs Oracle | Forecast value label | Expected downstream cost/regret | Task-specific surrogate shape error |
| Selection data | Per-building chronological Validation | Cross-building meta-learning data | Training instances | Calibration/in-sample competition data |
| Test role | Evaluation only | New-building test evaluation | Out-of-sample evaluation | Held-out competition weeks |
| End-to-end retraining | No | Meta-classifier only | Yes for learned pool | Parameter fitting to custom metric |

The precise remaining innovation is not “decision-focused forecasting.” It is the simple, auditable packaging of optimizer-derived held-out regret as the selector for a deterministic per-building forecast blend under a strict Test boundary.

## 8. Final Contribution Hierarchy

| Contribution | Level | Confidence | Headline use |
|---|---|---|---|
| CORE-1: Validation battery regret selects the DayWeek–LightGBM weight | LEVEL B | MEDIUM-HIGH | Report, PPT, oral |
| CORE-2: frozen forecast-to-decision mismatch evidence | LEVEL C | HIGH | Report, PPT, oral |
| CORE-3: pre-Test morphology-based representative evaluation with retained failures | LEVEL C | HIGH | Report and oral; supporting PPT |
| Machine-readable semantics, audit and invariance | LEVEL D | MEDIUM | Supporting, with lineage caveat |
| Forecast-to-simulated-battery peak-shaving integration | LEVEL E | HIGH | Application value only |

## 9. Core Claim 1

**Approved wording:** DOEF applies value-oriented selection as a transparent per-building Validation mechanism: optimizer-derived peak-shaving regret selects a fixed convex blend of DayWeek and LightGBM before Test evaluation.

Why it matters: it aligns a lightweight forecast combination with the quantity the frozen storage scheduler actually exposes, while remaining easy to inspect and reproduce from saved Validation rows.

Boundary: this is LEVEL B adaptation, not a new DFL theory, not end-to-end learning, not the first decision-focused forecast combination and not the first task-aware battery forecast.

## 10. Core Claim 2

**Approved wording:** In the frozen eight-building experiment, forecast and decision rankings materially diverged: Validation forecast- and decision-optimal weights differed on 6/8 buildings, Phase 7 Test winners agreed on only 2/8, and the exact rank-agreement rate was 0.34375 (report as 0.344).

The three statistics have different semantics. The 6/8 figure comes from Validation blend-grid minimizers. The 2/8 and 0.34375 figures are descriptive Test comparisons of frozen Phase 7 methods and did not select DOEF. The rank statistic is an exact agreement rate, not a rank-correlation coefficient.

Boundary: accuracy is still important. The result only establishes non-equivalence in this frozen scope.

## 11. Core Claim 3

**Approved wording:** Of 296 office candidates, 82 passed fixed raw-availability and quality gates; eight were fixed before Test performance using an anchor plus deterministic farthest-point sampling on Train-period morphology, without forecast or decision scores.

Critical caveat: raw availability over predefined Validation and Test windows is part of eligibility. Therefore “all building selection used Train only” is false. The correct split is: eligibility uses fixed raw coverage across windows; morphology and representative sampling use Train only.

Boundary: this is evaluation rigor, not an unseen-building model, transfer experiment or proof of all-building generalization.

## 12. Supporting Contributions

LEVEL D support consists of saved claim/metric semantics, lineage records, configuration files, prediction invariance and explicit negative results. Its confidence is reduced by the open Phase 7 hash defect.

LEVEL E support consists of a lightweight integration from 24-hour-ahead load forecasting to constrained simulated battery peak shaving. No real deployment, price, tariff, carbon or renewable-consumption outcome was modeled.

## 13. Frozen Key Numbers

The sole Phase 13/14 number source is `outputs/phase12/key_number_ledger.csv`. Headline values are:

| Item | Frozen value | Correct semantic wording |
|---|---:|---|
| Candidate → eligible → selected | 296 → 82 → 8 | Office buildings; fixed quality gates then pre-Test morphology sampling |
| Horizon / Test | 24 h / 720 samples per building | Target dates 2017-12-02 to 2017-12-31 |
| Forecast-vs-decision blend mismatch | 6/8 | Validation minimizers differ |
| Phase 7 winner agreement | 2/8 | Test forecast winner equals decision winner |
| Exact rank agreement | 0.34375 | Report as 0.344; not correlation |
| DOEF mean normalized MAE | 0.1379695350 | 6.3585% lower than LightGBM |
| DOEF mean normalized regret | 0.1119291839 | 3.6147% lower than LightGBM |
| Regret wins/ties/losses vs LightGBM | 6/2/0 | Per-building mean daily regret |
| Building bootstrap difference | -0.0041976 | 95% interval [-0.0068502, -0.0017190] |
| DOEF whole-window peak reduction | mean 6.4423%; median 5.6291% | Maximum-power peak shaving under simulation |
| Constraint audit | 0 violations / 4488 daily solves | Simulation audit, not field certification |
| Prediction invariance | 5760 samples; max delta 0 | Definition match to frozen Phase 8 predictions |
| CPU efficiency | 0.187 s train; 2.34 ms inference; 499.2 KiB | Environment-specific protocol only |

Normalized MAE and normalized decision regret use frozen Phase 7 Train mean load. Peak reduction is a separate whole-window maximum-power statistic. Oracle is a non-deployable hindsight upper bound. None of the peak numbers is an energy, bill or carbon saving.

## 14. Negative Results & Anti-Cherry-Picking Evidence

- **Phase 5.7 robust strategy:** in the single-building frozen case, robust minus deterministic daily peak averaged +9.3361 kW, worst-10% peak changed by +9.5642 kW, and the paired count was 1/0/29 better/equal/worse. It was stopped; it is not evidence that robust optimization is generally ineffective.
- **Phase 6/9 peak-aware LightGBM:** Validation selected zero extra peak weight in 7/8 buildings. Test decision-regret comparisons were 0/7/1 against LightGBM and 0/2/6 against DOEF. The branch remains rejected.
- **CatBoost:** no building was removed and no outcome was winsorized. Its whole-window peak-reduction mean is -24.4824% while the median is 4.8209%, driven by a retained -245.9433% failure on `Hog_office_Lavon`.
- Unfavorable buildings and ties remain in the main counts. These outcomes support stopping rules and honest evaluation, not performance contributions.

## 15. Claim Boundaries

Every downstream deliverable must distinguish:

- forecast MAE/RMSE/MAPE from decision regret;
- regret from peak reduction;
- absolute kW from percentage reduction;
- building-specific values from macro means or medians;
- Validation selection from Test evaluation;
- deployable DOEF from non-deployable Oracle;
- hourly meter energy (`kWh per interval`) from interval-average dispatch power (`kW`), noting numerical equality only because the interval is one hour;
- simulated peak shaving from real deployment, energy saving, tariff saving or carbon reduction.

## 16. Prohibited Claims

The complete frozen list and safe alternatives are in `outputs/phase12/prohibited_claims.md`. The most important prohibitions are:

- first decision-oriented forecasting / first decision-focused ensemble;
- new or end-to-end DFL algorithm;
- accuracy is unimportant;
- DOEF works on all buildings or demonstrates unseen-building transfer;
- robust or peak-aware branches improved Test;
- real deployment, bill reduction, energy saving, carbon reduction or renewable-consumption improvement;
- superiority to all existing work, world-leading status or filling a domestic/international blank;
- complete clean-checkout fail-closed reproducibility.

## 17. Reproducibility / Lineage Caveat

Phase 10 records a **HIGH, OPEN** Phase 7 clean-checkout loader/hash lineage defect. The registered hashes for the Phase 7 report/manifest do not match the current clean-checkout files, and the discrepancy was not explained by a simple line-ending normalization check.

Phase 12 did not repair it, re-register hashes, change `src/final_algorithm.py` or modify any frozen artifact. The correct competition statement is:

> 存在 machine-readable lineage、metric semantics 与 prediction-invariance 审计机制，但当前仍保留一个已知 Phase 7 clean-checkout hash-consistency 风险。

The loader's fail-closed behavior may be described, but “complete fail-closed reproducibility is resolved” may not.

## 18. Competition Narrative

The frozen narrative is:

> 建筑储能真正消费的不是一个孤立预测分数，而是预测进入受约束调度后产生的决策价值。已有研究已经建立 value-oriented forecasting 与 decision-focused selection，DOEF 不主张发明这一思想。冻结的多建筑实验进一步显示：预测权重、方法 winner 与完整排名在预测指标和储能 regret 下并不等价。因此，DOEF 将这一思想具体化为一个轻量机制——在 Validation 上用实际储能削峰 decision regret 选择 DayWeek–LightGBM 融合权重，冻结后 Test 只评价。建筑样本在 Test 成绩前固定，失败案例不删除。最终贡献是一个面向建筑储能削峰的透明、可审计、非端到端 decision-oriented forecasting framework。

This sequence supports the technology-innovation rubric: a concrete energy problem, clear need, transparent framework, honest results, bounded application value and explicit limitations.

## 19. Phase 13 Handoff Contract

Phase 13 may use only:

1. claims whose formal matrix status is `APPROVED` or `APPROVED_WITH_SCOPE`;
2. values and rounding in `outputs/phase12/key_number_ledger.csv`;
3. metric and unit definitions in `outputs/phase9_1/metric_semantics.json` and `outputs/phase9_1/unit_semantics.json`;
4. the citations and verification states in `outputs/phase12/literature_registry_frozen.csv` and `outputs/phase12/prior_art_audit.csv`;
5. safe wording and caveats in the frozen innovation/prohibition files.

Phase 13 must not create a new innovation point, change a number, change a statistical definition, expand the population/deployment scope, revive provisional pre-research wording, or repackage LEVEL C/D/E as LEVEL A. If a later source materially changes the closest-prior-work conclusion, Phase 12 must be reopened rather than silently editing Phase 13 prose.

## 20. Final Verdict

**PASS.** The closest prior art was adversarially audited; L015/L016 received full-text-level checks; L020 and current battery DFL work narrowed the claim; every headline number is traceable to a canonical artifact; metric/unit semantics and rounding are frozen; negative results and the open lineage defect remain visible; and no algorithm or frozen result was changed.

The final position is credible precisely because it is bounded: **one LEVEL B method adaptation, two LEVEL C evidence/rigor contributions, plus LEVEL D/E support.** Phase 13 is authorized only under the frozen handoff contract.
