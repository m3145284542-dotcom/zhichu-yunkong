# Phase 13.4 — Competition Artifact Index

| Artifact | Phase | Path | Purpose | Canonical status | Downstream use |
| --- | --- | --- | --- | --- | --- |
| Algorithm freeze | 9/9.1 | `outputs/phase9/final_algorithm.json; outputs/phase9_1/final_reporting_summary.json` | Canonical algorithm definition and reporting semantics | CANONICAL | All submission claims |
| Scientific canonical artifacts | 7/8/9/9.1 | `outputs/phase9_1/artifact_hash_audit.json` | 76-file frozen integrity registry | CANONICAL | Integrity gate |
| Multi-building evidence | 7/9/9.1 | `outputs/phase7/selected_buildings.json; outputs/phase9/per_building_metrics.csv` | Fixed building selection and outcomes | CANONICAL | Breadth/generalization wording |
| Negative-result evidence | 5.7/9 | `outputs/phase5_7/summary.json; outputs/phase9/competition_summary.json` | Retained falsification evidence | CANONICAL | Honest limitations |
| Scientific figures | 13.1 | `outputs/phase13_1/manifests/visual_asset_manifest.json` | Five scientific figures plus architecture/conceptual assets | CANONICAL | PPT visuals |
| Storyboard | 13.2 | `outputs/phase13_2/slide_architecture.json` | 12-slide main + 11-slide appendix narrative | FROZEN | PPT narrative |
| Competition presentation | 13.3 | `outputs/phase13_3/Phase13_3_DOEF_Competition_Presentation.pptx` | Accepted 23-slide deck; Phase 13.4 read-only audit object | FROZEN_WITH_FOLLOW_UP | Phase 14 presentation audit |
| Master Project Record | 13.4 | `reports/phase13_4/master_project_record.md` | Human-readable master evidence entry | CANONICAL_AUDIT_ENTRY | Phase 14 |
| Claim registry | 13.4 | `outputs/phase13_4/claim_registry.csv` | Allowed/prohibited claim control | CANONICAL_AUDIT_ENTRY | Claim audit |
| Numeric registry | 13.4 | `outputs/phase13_4/numeric_evidence_registry.csv` | Number-to-source map | CANONICAL_AUDIT_ENTRY | Number audit |
| Figure registry | 13.4 | `outputs/phase13_4/figure_registry.csv` | Figure provenance and limits | CANONICAL_AUDIT_ENTRY | Figure audit |
| Presentation evidence map | 13.4 | `outputs/phase13_4/presentation_evidence_map.csv` | Page-by-page evidence map | CANONICAL_AUDIT_ENTRY | Presentation audit |
| Terminology standard | 13.4 | `reports/phase13_4/terminology_and_naming_standard.md` | Naming, metric and unit semantics | CANONICAL_AUDIT_ENTRY | Submission consistency |

## Phase 14 entry requirements

1. Start from `reports/phase13_4/master_project_record.md` and `outputs/phase13_4/master_evidence_manifest.json`.
2. Recheck the frozen baseline ancestry and the 76 registered scientific artifacts.
3. Reconcile the open remote/PPT identity discrepancies without changing scientific content.
4. Treat machine-readable canonical evidence as superior to PPT wording and earlier narrative reports.
5. Preserve Validation/Test roles and all negative results; run no algorithm selection on Test.
