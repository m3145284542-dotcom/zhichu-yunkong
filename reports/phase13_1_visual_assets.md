# Phase 13.1 — Scientific Figures, DOEF Architecture, and Presentation Visual Assets

## 1. Phase status

**PHASE 13.1 — PASS.** Eight presentation-ready assets were created exclusively from the Phase 13.0B approved evidence selection: five scientific assets, one frozen DOEF architecture asset, and two explicitly conceptual explanatory assets. The algorithm, predictions, decision results, experiments, estimators, building set, and claim/evidence selection were not changed.

## 2. Git integrity

- Starting HEAD: `062a3ceb02a293bbb78c7c7c4fe1d35fc9ae3999`
- Starting branch: `main`
- HF1 starting HEAD is an ancestor: PASS
- Starting tracked/untracked status: clean
- Existing ignored scopes recorded before writes: `.venv/`, `.mplconfig/`, `data/raw/`, and Python `__pycache__/` directories
- Frozen Phase 7/8/9/9.1, Phase 13.0A, and Phase 13.0B paths have no working-tree modifications: PASS

## 3. Evidence integrity

The Phase 13.1 contract is **LF-normalized SHA-256 for text** and raw SHA-256 for binary files. Frozen Git committed bytes arbitrate legacy registries. This prevents Windows `core.autocrlf=true` checkout bytes from being misclassified as evidence drift.

Some historical Phase 7/8/9 and Phase 13.0A text hashes were recorded from CRLF checkout bytes. Those registries were not rewritten. The validator instead compares LF-normalized current bytes with the corresponding frozen committed blobs. The Phase 13.0B HF1 registry is compared directly under its LF-normalized contract.

| Scope | Registered | Validated | Real drift | Status |
| --- | ---: | ---: | ---: | --- |
| Phase 7/8/9/9.1 canonical artifacts | 76 | 76 | 0 | PASS |
| Phase 13.0A registered sources | 88 | 88 | 0 | PASS |
| Phase 13.0B registered files | 8 | 8 | 0 | PASS |

Phase 13.0B claim/evidence semantic changes: **NONE**. New experiments or statistical tests: **NO**.

## 4. Visual design system

The visual system is recorded in `outputs/phase13_1/manifests/visual_style_guide.json`. It uses a 16:9 canvas, 2400×1350 PNG output, DejaVu Sans, a colorblind-friendly high-contrast palette, and redundant marker/hatch/line encodings. DOEF is blue, LightGBM orange with square/hatch encoding, XGBoost green, DayWeek magenta, and neutral Test boundaries gray. Bar charts use zero baselines; incompatible metrics use separate panels; jet/rainbow, 3D, dual axes, decorative gradients, and heavy shadows are prohibited.

## 5. Scientific figures

### SCI-01 — Forecast/decision mismatch

- Purpose: show the frozen project-scoped counterexample that forecast rank and storage-decision rank need not agree.
- Claim: `CORE-02`; evidence: `CLM-2482`, `CLM-2472`, `CLM-2484`, `CLM-2474`.
- Source: `outputs/phase9/final_benchmark.csv`, rows `LightGBM` and `XGBoost`; fields `normalized_rmse_mean` and `normalized_decision_regret_mean`.
- Transform: two independent, zero-based paired comparisons; no recomputation.
- Caveat: the differences are small and directional; the figure does not claim forecast accuracy is unimportant.
- Output: `outputs/phase13_1/figures/sci_01_forecast_decision_mismatch.{svg,png}`.

### SCI-02 — DOEF main results

- Purpose: present the strongest frozen final-scope result without mixing metric units.
- Claims: `CORE-06`, `CORE-07`, `CORE-08`.
- Source: `outputs/phase9/final_benchmark.csv` and `outputs/phase9_1/final_reporting_summary.json`.
- Transform: separate zero-based normalized-MAE and normalized-regret panels; annotations reproduce frozen relative improvements and win/tie/loss counts.
- Caveat: eight fixed offices, one fixed Test month per building, Oracle-relative regret is not monetary regret, and the minimum negative peak-reduction result remains visible.
- Output: `outputs/phase13_1/figures/sci_02_doef_main_results.{svg,png}`.

### SCI-03 — Multi-building decision regret

- Purpose: show all eight fixed buildings, including ties and the full variation.
- Claim: `CORE-07`.
- Sources: frozen selection order in `outputs/phase7/selected_buildings.json`; frozen Train mean loads in `outputs/phase8/validation_weight_search.csv`; frozen Test regret in `outputs/phase9/decision_metrics.csv`.
- Transform: `mean_regret_vs_oracle / train_mean_load` per building, using the already-established Phase 9.1 metric definition; no building sorting, deletion, or Test reselection.
- Caveat: multi-building robustness, not unseen-building transfer.
- Output: `outputs/phase13_1/figures/sci_03_multibuilding_regret.{svg,png}`.

### SCI-04 — Validation weight selection

- Purpose: show that forecast-error and decision-regret objectives select different frozen ensemble weights for six of eight buildings.
- Claims: `CORE-03`, `CORE-05`.
- Source: `outputs/phase8/selected_weights.csv`, fields `building`, `w_forecast`, `w_decision`, and `weights_differ`.
- Transform: paired dumbbells in frozen source order; Test data are not used.
- Caveat: differing selected weights do not establish universal downstream superiority.
- Output: `outputs/phase13_1/figures/sci_04_validation_weight_selection.{svg,png}`.

### SCI-05 — Frozen representative dispatch

- Purpose: provide the approved backup mechanism trace linking forecasting to realized grid-load schedules.
- Claims: `CORE-01`, `SUP-06`; evidence: `CLM-0021`.
- Source: `outputs/phase8/figures/06_representative_dispatch.png`.
- Transform: the frozen raster is embedded unchanged in a readable frame. No value extraction, case reselection, dispatch rerun, or claim expansion occurs.
- Caveat: representative backup case only, not a universal performance claim.
- Output: `outputs/phase13_1/figures/sci_05_storage_dispatch_frozen.{svg,png}`.

## 6. DOEF architecture

`ARCH-01-doef-architecture-master` is grounded in `outputs/phase13_0b/doef_pipeline_spec.json`, `outputs/phase9/final_algorithm.json`, `outputs/phase9_1/final_reporting_summary.json`, and `outputs/phase8/selected_weights.csv`.

- M1: frozen hourly load data and predefined Train/Validation/Test windows.
- M2: causal positive lags and shifted history, 24-hour target horizon, no weather.
- M3: DayWeek component, `0.5*y(t-24) + 0.5*y(t-168)`.
- M4: per-building LightGBM with frozen configuration.
- M5: `w_b*LightGBM + (1-w_b)*DayWeek`, with `w_b` selected by Validation mean daily Oracle-relative regret.
- M6: the same frozen capacity, power, efficiency, SOC, daily-reset, and throughput-constrained battery optimizer.
- M7: final forecast metrics plus realized peak and Oracle-relative decision-regret evaluation.

The diagram explicitly says `ALGORITHM FROZEN` and excludes joint training, bilevel optimization, online learning, and deployable-Oracle interpretations. Outputs: SVG master, 2400×1350 light PNG, and 2400×1350 transparent PNG.

## 7. Train/Validation/Test leakage audit

- Train fits the LightGBM component and supplies causal history.
- Validation produces component forecasts, runs the frozen battery decision comparison, selects the per-building regret-minimizing weight, and freezes it.
- Test receives only frozen components and frozen weights. It supplies past-known inputs for forecasting and realized load for terminal reporting.
- There is no Test arrow to training, features, component selection, weight selection, or tie-breaking.
- Forecast metrics have a direct terminal path; decision metrics pass through the frozen battery schedule and realized-load evaluation.

Leakage audit: **PASS**.

## 8. Conceptual presentation assets

- `CON-01-prediction-decision-bridge`: forecast → battery schedule → realized grid load → decision outcome. It is labeled `CONCEPTUAL / EXPLANATORY` and encodes no experimental values.
- `CON-02-contribution-overview`: causal forecasting, Validation-based decision selection, multi-building robustness evaluation, and storage-decision metrics. It is labeled `CONCEPTUAL / EXPLANATORY` and makes no novelty-priority or SOTA claim.

## 9. Visual truthfulness audit

- Axis: bar and paired-value plots use zero baselines; no misleading truncation or dual axis.
- Units: normalized metrics are named; kW/kWh are not conflated; Oracle-relative regret is not presented as money.
- Selection: all eight frozen buildings remain; no Test-based ordering, deletion, or representative-case selection was introduced.
- Aggregation: equal-building mean and per-building views are distinguished; incompatible metrics are separated.
- Claims: titles use the Phase 13.0B contract and avoid significance, causation, universality, SOTA, and unseen-building claims.
- Dataset split: Train/Validation/Test roles are explicit in architecture and method evidence.

Truthfulness audit: **PASS**.

## 10. Presentation readability audit

All generated PNG assets are 2400×1350. Core titles, axis labels, method names, legends, and central annotations remain readable at 50%–75% of a 1920×1080 slide width. A full-size and contact-sheet visual inspection found and corrected first-pass title collisions and architecture routing congestion. Final thumbnail/readability audit: **PASS**.

## 11. Reproducibility

Run:

```powershell
.\.venv\Scripts\python.exe scripts\build_phase13_1_visual_assets.py
.\.venv\Scripts\python.exe scripts\validate_phase13_1_visual_assets.py
```

The builder fails closed on source hash drift. The validator rebuilds the asset set and compares output hashes, validates manifest fields and linkage, verifies every source/output, parses SVG, reads PNG, enforces minimum dimensions and non-empty images, and rechecks all frozen integrity scopes. Deterministic rebuild: **PASS**.

The repository regression suite also passes: **122/122 tests**. The local ignored environment initially lacked the already-pinned XGBoost and CatBoost packages; installing those declared dependencies resolved the environment-only import failures without changing tracked source or frozen artifacts.

## 12. Manifest

The planned source chain is recorded before rendering in `outputs/phase13_1/manifests/visual_asset_inventory.json`. The promoted canonical delivery manifest is `outputs/phase13_1/manifests/visual_asset_manifest.json`; it records claim/evidence IDs, exact source fields, normalized source hashes, deterministic transforms, plotted-value checksums, outputs, limitations, and validation status. Machine-readable validation evidence is `outputs/phase13_1/manifests/validation_results.json`.

## 13. Files created / modified

- Created `scripts/build_phase13_1_visual_assets.py`.
- Created `scripts/validate_phase13_1_visual_assets.py`.
- Created `outputs/phase13_1/` with scientific figures, architecture, conceptual assets, manifests, and preview aids.
- Created this report.
- Updated `README.md` with the Phase 13.1 artifact locations and reproduction commands.
- No Phase 7/8/9/9.1, Phase 13.0A, or Phase 13.0B file was modified.
- No `.pptx`, slide deck, animation, speaker note, or defense script was created.

## 14. Canonical integrity

Frozen algorithm untouched: PASS. Frozen predictions untouched: PASS. Frozen decision results untouched: PASS. Canonical 76 drift: 0. Phase 13.0A 88 drift: 0. Phase 13.0B 8 drift: 0. Claim/evidence semantic drift: NONE.

## 15. Remaining presentation gaps

- SCI-05 remains a frozen raster reuse because Phase 13.0B prohibits mining it for new values and no approved frozen trace table was selected for reconstruction.
- The project does not support unseen-building transfer, cost/savings, carbon, energy-reduction, external-first, or SOTA visuals.
- Storyboard, slide architecture, defense sequencing, and speaker notes remain intentionally deferred.

## 16. Recommendation for next phase

Proceed only to **PRESENTATION STORYBOARD PHASE**, using the canonical manifest as the visual source of truth. Do not change evidence selection or regenerate experimental results. No PPT was created in Phase 13.1.
