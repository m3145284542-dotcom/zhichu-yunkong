# Phase 12 Pre-Research — Literature Review & Provisional Innovation Positioning

> **PASS AS PHASE 12 PRE-RESEARCH / NOT FROZEN.** Evidence preparation only; final novelty claims are not frozen.

## 1. Executive Summary

DOEF v1.0 remains frozen and untouched. The strongest provisional positioning is: LEVEL B transparent Validation-only selection of a DayWeek–LightGBM ensemble by battery regret; LEVEL C multi-building evidence that forecast accuracy and decision value diverge; and LEVEL C Train-only building selection/Test-only evaluation rigor.

Direct prior art limits novelty. Werling et al. select building forecasts by PV-battery value; Stratigakos et al. learn forecast-pool weights by downstream cost. DOEF is not the first decision-focused ensemble and is not end-to-end DFL. Its defensible difference is a lightweight, deterministic, auditable adaptation to building battery peak shaving.

## 2. Frozen Algorithm Boundary

- Frozen baseline and initial HEAD: `549abc314e93e2862bfc22965db89622c22890e1`; initial branch `main`; no modified, staged or non-ignored untracked files.
- Phase 10 was found committed on `codex/phase10-deliverable-audit` at `12a204f7b48e5a603e94f1643f3903175f1a5d17`, with exactly three audit/roadmap additions. This Phase 12 pre-research branch inherits that head.
- No training, tuning, new model, prediction, dispatch or result generation occurred.
- Name: **Decision-Oriented Ensemble Forecasting**. Formula: `w_b*LightGBM+(1-w_b)*DayWeek`; `DayWeek=0.5*actual(t-24h)+0.5*actual(t-168h)`.
- Phase 10's open clean-checkout Phase 7 loader/hash defect remains an engineering risk and was not repaired.

## 3. Search Methodology

Queries covered building forecasting, seasonal/tree ensembles, forecast-driven BESS, predict-then-optimize, DFL/task/value-oriented learning, downstream-selected pooling/model selection and rigor. Publisher/original papers, arXiv originals, official datasets and strong reviews were prioritized; blogs/generated summaries were excluded.

Eighteen sources entered the provisional registry: 17 HIGH-quality and one MEDIUM row. Unknowns are `UNVERIFIED`. This is targeted pre-research, not a PRISMA systematic review; absence is not proof of non-existence.

## 4. Literature Taxonomy

### A. Building load forecasting

Commercial/multi-building forecasting, seasonal persistence, tree models and weighted ensembles are established (L001–L003). LightGBM, DayWeek, averaging and building count alone are not novel.

### B. Forecast-driven battery peak shaving

Forecast-to-ESS scheduling is established (L004–L007). DOEF's integrated pipeline is application/system value, not a first pipeline.

### C. Predict-then-optimize

SPO (L010) formalizes decision regret and why generic prediction loss may not preserve decision quality. This supports motivation, not firstness.

### D. DFL boundary

L009–L014 put optimization objectives/structure into training or loss. DOEF freezes predictors and uses Validation downstream metrics only for blend selection. Accurate term: `decision-oriented ensemble/model selection`, not `end-to-end DFL`.

### E. Downstream-selected ensembles

L016 is the closest ensemble concept: downstream-cost probabilistic pooling. L015 is the closest building-battery selection concept. DOEF differs in deterministic point forecasts, finite-grid transparency, peak-shaving regret and audit protocol.

### F. Experimental rigor

Multi-building evaluation is common. DOEF's contribution is Train-only morphology selection, Validation-only weights, fixed Test, causal purge, building bootstrap, retained failures and machine-readable lineage.

## 5. Closest Prior Work

Authoritative rows: `outputs/phase12_pre_research/closest_prior_work.csv`.

| Dimension | Closest prior work | DOEF |
| --- | --- | --- |
| Load forecasting | L015/L007/L008 | 24-hour building load |
| Ensemble | L016 probabilistic pool | deterministic DayWeek–LightGBM blend |
| Downstream optimization | yes | constrained battery peak shaving |
| Decision metric for selection | L015/L016 yes | Validation daily regret |
| End-to-end training | many DFL works yes | no |
| Multi-building | L015/L017 yes | eight selected offices |
| Main difference | broader concepts exist | simple audited point-forecast adaptation |

## 6. Candidate Contribution Audit

1. Accuracy ≠ decision value: empirical finding/motivation, LEVEL C, not scientific novelty.
2. Downstream metric for ensemble selection: LEVEL B, but neither first nor end-to-end DFL.
3. DayWeek + LightGBM: components/average not novel; selection and bounded application carry contribution.
4. Train-only multi-building protocol: LEVEL C evaluation rigor, not algorithmic innovation.
5. Forecast–optimization–evaluation chain: LEVEL D/E engineering/application value.
6. Phase 5.7 negative robust result: falsification/stop-rule evidence, never a performance gain.

## 7. Claim–Evidence Matrix Summary

`outputs/phase12_pre_research/claim_evidence_matrix.csv` contains nine claims with internal paths, literature, safe/prohibited wording and statuses. Performance statements are bounded to eight selected offices, one Test month and the frozen battery simulation.

## 8. Provisional Core Contributions

### Core 1 — LEVEL B

DOEF selects a per-building DayWeek–LightGBM weight on Validation storage decision regret, using a fixed grid/tie-breaks before Test-only evaluation. PPT: “让预测权重服从储能削峰决策价值，而不只服从 MAE。” It is simpler and more auditable than L016, but not first or DFL.

### Core 2 — LEVEL C

The project separates forecast accuracy from decision value: 6/8 forecast/decision weights differ; Phase 7 winner agreement is 2/8; rank agreement is 0.344. PPT: “预测更准，不等于储能削峰一定更好。” It replicates a known phenomenon in a frozen building-peak-shaving benchmark.

### Core 3 — LEVEL C

Eight offices were selected from 82 eligible candidates using Train morphology only, then evaluated uniformly with failures retained. PPT: “先按训练期形态选建筑，再统一验证预测与储能价值。” This is rigor, not unseen-building transfer.

## 9. Supporting Contributions

- LEVEL D: machine-readable lineage/config/prediction/dispatch/constraint/bootstrap chain; MEDIUM confidence due the loader hash defect.
- LEVEL E: AI forecast → constrained dispatch → realized peak-shaving simulation; no deployment, bill, carbon or renewable claim.

## 10. Negative Findings Worth Retaining

Phase 5.7's robust strategy was worse on Test; Phase 6 peak-aware LightGBM was rejected; CatBoost's extreme negative building was retained. These support stopping and anti-cherry-picking, not universal claims against complex methods.

## 11. Claims That Must Not Be Made

See `outputs/phase12_pre_research/prohibited_claims.md`: comprehensive LightGBM superiority; accuracy always implies value; robust optimization improved Test; new/end-to-end DFL; firstness; all-building success; deployment; bill/carbon/renewable guarantees; superiority to all methods.

## 12. Recommended Competition Narrative

Forecast accuracy → does not fully represent → storage decision value → DOEF selects a transparent blend by Validation battery regret → eight Train-selected buildings → reproducible forecast-to-dispatch evidence.

Keep visible: not end-to-end DFL; not unseen-building transfer; benefits are simulated under the frozen protocol.

## 13. Remaining Evidence Gaps

1. Citation chaining around L015/L016 and broader databases/synonyms.
2. Full-text split/leakage/dataset audit for L006–L008/L015/L016.
3. Resolve `UNVERIFIED` metadata and export publisher bibliography.
4. Choose final label among adaptation/integration/competition implementation; evidence favors adaptation/integration.
5. Separately authorize loader/hash repair before clean-checkout reproducibility claims.

## 14. Final Phase 12 Recommendation

Run an adversarial novelty review, broaden citations, verify closest-prior dimensions from full texts, resolve metadata, then freeze claims. Do not retrain, retune, add models or change results.

## 15. Verdict

**PASS AS PHASE 12 PRE-RESEARCH.** The final Phase 12 claim audit may proceed, but claims are **NOT FROZEN**. Provisional novelty is LEVEL B/C; no LEVEL A claim is supported.
