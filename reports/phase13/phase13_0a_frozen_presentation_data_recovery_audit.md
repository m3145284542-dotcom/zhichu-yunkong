# Phase 13.0A — Frozen Presentation Data Recovery Audit

## Verdict

**PASS.** Phase 13.0B may proceed, using `outputs/phase13_0a/frozen_presentation_data_manifest.json` as the only numerical source. This audit did not train, predict, optimize, resample, or modify any Phase 7/8/9/9.1 canonical artifact.

## A. Repository integrity

- Repository: `D:/document/aic`
- Branch: `codex/phase13-visual-report-demo`
- Starting HEAD: `3d77272c36108fffcdcb4f73c240b52bbfc4de86`
- Frozen baseline: `549abc314e93e2862bfc22965db89622c22890e1`
- Ancestry: frozen baseline is an ancestor; ahead 5, behind 0.
- Frozen-to-starting-HEAD canonical Phase 7/8/9/9.1 changes: 0.
- Starting worktree canonical Phase 7/8/9/9.1 modifications: 0.
- Starting dirty state: two pre-existing untracked paths (`outputs/phase13/`, `reports/phase13_implementation_plan.md`), preserved and excluded from this phase.
- Phase 9.1 historical hash audit: PASS, 76 registered Phase 7–9 artifacts unchanged.
- Ending HEAD and commit are completed after validation and recorded in the closing commit; see Git history and `recovery_summary.json` for the immutable starting state.

## B. Recovery coverage

- Total candidate presentation items: 2623
- EXACT_RECOVERED: 2559
- DETERMINISTIC_DERIVED: 4
- FIGURE_REUSABLE_ONLY: 49
- TEXT_ONLY_EVIDENCE: 0
- AMBIGUOUS: 4
- UNRECOVERABLE: 7
- Numerical manifest items: 2545
- Hashed presentation sources: 88

The 17,544-hour figure is directly recovered from the processed-data manifest. The 1,578-building figure is a deterministic count of rows in the frozen Phase 3 building-selection table and is safe only when described as the project selection universe represented by that table. Phase 7 directly records 296 office candidates, 82 quality-pass candidates, and 8 fixed selected buildings.

## C. Critical story coverage

| Story area | Status | Qualification |
|---|---|---|
| Problem / dataset | READY |  |
| Forecast task | READY |  |
| Baselines | READY |  |
| LightGBM | READY |  |
| Forecast comparison | READY |  |
| Decision-oriented evaluation | READY |  |
| Battery optimization | PARTIAL | Frozen evidence exists but the scope/limitation must be shown. |
| Error propagation | READY |  |
| Robustness | READY |  |
| Multi-building generalization | PARTIAL | Frozen evidence exists but the scope/limitation must be shown. |
| Decision-oriented ensemble | READY |  |
| Final DOEF | READY |  |
| Final test evidence | PARTIAL | Frozen evidence exists but the scope/limitation must be shown. |
| Reproducibility | READY |  |


## D. Missing presentation evidence

- Unseen-building transfer or generalization beyond the eight fixed office buildings.
- Evidence beyond one fixed future Test month per building.
- A pristine, never-before-viewed Test set; Test was not used for selection, but historical Test results had already been viewed.
- Tariff, cost, monetary saving, carbon, and energy-use reduction outcomes.
- Any broader external BDG2 release count claim beyond the 1,578 series represented in this repository's frozen selection table.

These are `UNRECOVERABLE_WITHOUT_NEW_EXPERIMENT` or absent outcome models and must not be synthesized for presentation.

## E. Conflicts

Eight conflicts/scope hazards are registered in `conflict_register.csv`: multiple LightGBM protocol values; Phase 4 versus corrected Phase 4.5; unqualified peak-reduction scope; feature/target timestamp boundaries; kWh-versus-kW semantics; multi-building versus unseen-building terminology; held-out role versus prior Test visibility; and the negative Phase 5.7 robust Test result. All resolvable items require explicit scope labels; no silent value selection is allowed.

The Phase 5.7 negative result is presentation-relevant: the Validation-selected robust configuration (`lambda=0.5`) has Test mean regret 20.4635 kW versus 11.1274 kW for deterministic LightGBM. It is classified `NEGATIVE_RESULT_BUT_SCIENTIFICALLY_USEFUL` and must not be reframed as improvement.

## F. Existing reusable figures

- Audited figures: 49
- PPT_READY: 15
- PPT_REFORMAT_RECOMMENDED: 1

PPT-ready candidates:
- `outputs/phase7/figures/01_morphology_map.png` — 01 Morphology Map (1530×1020); source `outputs/phase7/building_candidate_statistics.csv`.
- `outputs/phase7/figures/02_normalized_forecast_comparison.png` — 02 Normalized Forecast Comparison (1530×1020); source `outputs/phase7/model_test_forecast_metrics.csv`.
- `outputs/phase7/figures/03_decision_comparison.png` — 03 Decision Comparison (1700×1020); source `outputs/phase7/model_test_decision_metrics.csv`.
- `outputs/phase8/figures/01_validation_weight_vs_mae.png` — 01 Validation Weight Vs Mae (1620×900); source `outputs/phase8/validation_weight_search.csv`.
- `outputs/phase8/figures/02_validation_weight_vs_regret.png` — 02 Validation Weight Vs Regret (1620×900); source `outputs/phase8/validation_weight_search.csv`.
- `outputs/phase8/figures/03_selected_weights.png` — 03 Selected Weights (1440×1080); source `outputs/phase8/selected_weights.csv`.
- `outputs/phase8/figures/04_test_decision_regret.png` — 04 Test Decision Regret (1620×900); source `outputs/phase8/test_daily_decision_metrics.csv`.
- `outputs/phase8/figures/05_forecast_vs_decision_effect.png` — 05 Forecast Vs Decision Effect (1440×1080); source `outputs/phase8/test_daily_decision_metrics.csv`.
- `outputs/phase8/figures/06_representative_dispatch.png` — 06 Representative Dispatch (1800×900); source `outputs/phase8/test_daily_decision_metrics.csv`.
- `outputs/phase9/figures/01_forecast_vs_decision.png` — 01 Forecast Vs Decision (1360×1020); source `outputs/phase9/final_benchmark.csv`.
- `outputs/phase9/figures/02_building_decision_comparison.png` — 02 Building Decision Comparison (1700×1020); source `outputs/phase7/model_test_decision_metrics.csv`.
- `outputs/phase9/figures/03_core_improvements.png` — 03 Core Improvements (1700×1020); source `outputs/phase9/final_benchmark.csv`.
- `outputs/phase9/figures/04_peak_quality_vs_decision.png` — 04 Peak Quality Vs Decision (1360×850); source `outputs/phase9/final_benchmark.csv`.
- `outputs/phase9/figures/05_efficiency.png` — 05 Efficiency (1870×680); source `outputs/phase9/efficiency_metrics.csv`.
- `outputs/phase9/figures/06_validation_search.png` — 06 Validation Search (1360×850); source `outputs/phase9/validation_search.csv`.

Reformat recommended:
- `outputs/phase7/figures/04_forecast_vs_decision_rank.png` — 04 Forecast Vs Decision Rank (1190×1020); source `outputs/phase7/paired_model_comparison.csv`.


No numerical result was recovered from pixels, axes, OCR, or visual estimation. Resolution-based legibility is provisional and requires human slide-size review.

## Canonical presentation record

- Numerical source: `outputs/phase13_0a/frozen_presentation_data_manifest.json`
- Claim/source matrix: `outputs/phase13_0a/presentation_claim_evidence_matrix.csv`
- Source hashes: `outputs/phase13_0a/presentation_source_hashes.csv`
- Figure audit: `outputs/phase13_0a/figure_inventory.csv`
- Conflict register: `outputs/phase13_0a/conflict_register.csv`
- Machine-readable audit summary: `outputs/phase13_0a/recovery_summary.json`

Downstream work must fail closed on missing/null values, retain each item's source hash and scope, and never replace a missing value with zero.
