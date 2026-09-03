# Phase 13.3 — Submission-Grade Competition Presentation Acceptance

## Verdict

**PHASE 13.3 — PASS**

Phase 14 may be re-run. `READY TO SUBMIT` remains **NO** until Phase 14 completes.

## Audit basis

- Branch at start: `main`.
- Starting HEAD: `4f9a7c67e3a52b4ed508334378e3e2b45bbccc34`.
- Frozen baseline: `549abc314e93e2862bfc22965db89622c22890e1`; ancestry PASS.
- Start relative to `origin/main`: ahead 1, behind 0.
- Phase 14 checklist source: `reports/phase14_submission_readiness_audit.md`.
- Frozen narrative and evidence: Phase 13.2 storyboard, Phase 13.0B claim/evidence selection, and Phase 13.1 visual assets.

## Minimal repairs

1. All slides: changed presentation text declarations from unavailable `Noto Sans CJK SC` / `Aptos` to installed `Microsoft YaHei` / `Arial`. This removes the verified LibreOffice Chinese glyph collision without changing copy.
2. Slides 2, 3, 5, 6, 8, 9, 11, 13, 14, 16, 19, 20, 21, 22, and 23: replaced the reused mutable shadow object with a fresh shadow per card. All serialized shadow values are valid signed integers; the prior exponential growth and `Overflow_Int32` import failure are gone.
3. Slide 1: replaced `工作标题 · 正式赛题名称待核验` with `全球人工智能算法精英大赛 · AI+能源主题赛`. The DOEF project title and frozen subtitle are unchanged.
4. Slide 3: corrected the visible `hot/not` typo at the PPT layer. The frozen Phase 13.1 conceptual asset is unchanged.
5. Slide 19: replaced the source image's clipped explanatory caption at the PPT layer. The frozen curves, values, axes, labels, and source asset are unchanged.

## Acceptance results

| Check | Result |
| --- | --- |
| PPTX ZIP/CRC | PASS |
| XML parsed | 116/116 parts |
| Slides | 23/23 |
| Embedded notes | 23/23 |
| Embedded media | 10 files, CRC PASS |
| Standard artifact-tool import/render | 23/23 slides |
| LibreOffice 25.8 open/PDF export | 23/23 pages |
| Full-size visual inspection | 23/23 slides |
| Page size | 12192000 × 6858000 EMU, 16:9 |
| Overflow / out-of-bounds | 0 |
| Clipping | 0 |
| Unintended overlap | 0 |
| Broken/stretched/cropped images | 0 |
| Missing-font rendering defects | 0 in both tested renderers |
| External relationships | 0 |
| Missing relationship targets | 0 |
| Local absolute-path dependencies | 0 |
| Empty slide placeholders | 0 |
| Scientific claim mismatches | 0 |
| Storyboard/title mismatches | 0 |
| Forbidden/unresolved wording hits | 0 |
| Final result | PASS |

The bundled `render_slides.py` helper wrote all 23 expected PNGs but its child runtime returned a cleanup exit code after output completion. To avoid treating that wrapper behavior as deck evidence, acceptance used a direct `@oai/artifact-tool` import/inspect/render/export run that completed successfully, plus an independent LibreOffice open/export and Poppler rasterization. Every final slide was inspected at full size; the LibreOffice contact sheet was also checked for deck-wide consistency.

Microsoft PowerPoint and WPS were not available for automated rendering in this environment. The final package is nevertheless independently validated by OpenXML parsing, artifact-tool, and LibreOffice, with no external links or local-path dependencies.

## Scientific integrity

- New experiments: NO.
- Algorithm/model logic changes: NO.
- Prediction changes: NO.
- Ensemble/validation weight changes: NO.
- Battery configuration or dispatch changes: NO.
- Canonical Phase 7/8/9/9.1 artifacts modified: NO; integrity PASS.
- Phase 13.0A/13.0B/13.1 canonical artifacts modified: NO; integrity PASS.
- Phase 13.2 narrative order or scientific meaning changed: NO.

## Deliverables

- `outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx` — 1,884,529 bytes; SHA-256 `4ee40f3e2cd7b5a44b6dc4595a43165a89e230ff862d5a67ac3e2c12607e2028`.
- `outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pdf` — 2,157,018 bytes; SHA-256 `f30955a26ee5418314e7f6c9cd1658753d1e66f519296bec1e7359b96ebd3834`.
- `outputs/phase13_3/acceptance_report.json` — machine-readable package/render validation.
- `scripts/validate_phase13_3_presentation.py` — fail-closed acceptance validator.

No unresolved Phase 13.3 submission-critical issue remains.
