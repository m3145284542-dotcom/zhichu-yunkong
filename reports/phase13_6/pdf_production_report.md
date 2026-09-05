# Phase 13.6 — Submission PDF production

PHASE 13.6 — PASS

READY FOR NEXT PHASE — YES

## Canonical artifact and source

Submission artifact: technical_report_submission.pdf; 15 A4 pages, PDF 1.7, 1,096,823 bytes, SHA-256 73b1bea85272c26bae51b77308a9820fe47c8ccccb6453becdc90da6d28d6abb. This is searchable text and equations with embedded fonts, not a whole-page raster export.

The sole scientific body source remains reports/phase13_5/technical_report_final.md after the user-authorized reference correction. Current raw SHA-256: 9bf8dfa229202aa4719537136a5cf74c80f11f300fe087528d626adf159754bf. Size and Git blob are in qa/technical_audit.json. Pre-correction: 26,418 bytes; SHA-256 50b3c0b3c51166da2957dbdd4d7944d5ff48fc26d68487b73a6516d755a3d322; Git blob 2c39807f4d244c26abbdf907978beb6688dcd608.

## Authorized correction

The initial run stopped because reference [2] had incorrect authors. The user then authorized “处理错误”. The authors were corrected from Amasyali K / El-Gohary N M to Zhang L, Wen J, Li Y, Chen J, Ye Y, Fu Y, Livingood W. This is explicitly a bibliographic correction, not a layout-only edit. The DOI, title, year, journal, reference number and set are unchanged. The correction was synchronized to the Nature report and Phase 12 registry to prevent propagation from an upstream consumer.

reference_correction.json contains exact old/new text, all three paths and before/after hashes. Validation proves those files contain only the authorized author replacement relative to the Phase 13.5 baseline. Crossref and [Penn State's author record](https://pure.psu.edu/en/publications/a-review-of-machine-learning-in-building-load-prediction/) independently support the correction.

All 11 references were rechecked: 10 DOI records from Crossref and [9] from [official NeurIPS proceedings](https://proceedings.neurips.cc/paper/2017/hash/3fc2c60b5782f641f76bcefc39fb2392-Abstract.html). No additional author/title/year error was found. Existing abbreviated author lists and omitted volume/page fields remain unchanged; no bibliographic expansion was introduced.

Scientific semantic changes: 0. Bibliographic corrections: 1 entry across 3 synchronized files. New experiments, training, tuning, dispatch runs and statistical tests: 0.

## Official rules and implementation

The [official notice](https://www.aicomp.cn/notice/notice-3/4702.html), attachments 1/2 and [bylaws](https://www.aicomp.cn/bylaws) were reopened. Downloaded attachments, URLs and hashes are in qa/official_rules_manifest.json. The cover hierarchy, five major outline groups and specified typography follow the official PDF reference template. Instructional placeholders and the attachment label are omitted in the filled report.

A4; margins 28 mm left/right, 25 mm top/bottom. Chinese body: SimSun 12 pt, single spacing. References: 10.5 pt, 20 pt leading. English/numbers: Times New Roman; headings/code labels: Arial as appropriate; Chinese headings: SimHei. Mathematical fonts are embedded. Team 电协 was supplied by the user; date 2026-09-05. No school, instructor or member names were added.

All body paragraphs retain order and wording. Heading reparenting/renumbering is recorded in qa/heading_mapping.json. Contents and 22 bookmarks are generated automatically. The abstract's initially incorrect hyperlink anchor was fixed; all internal destinations now pass. All 15 pages then rendered pixel-identically to the individually inspected version (qa/final_render_comparison.json).

Tables and captions remain together; widths were improved. Figures/captions remain together at readable full width. Cover, abstract and final appendix naturally have open space. The main-result page has remaining space because the next full-width figure/caption cannot fit; this is intentional float-equivalent placement, not missing content. No unexpected blank pages exist.

Abstract count: 373 CJK characters; 402 words when Chinese characters count individually and Latin/numeric tokens count as words. The 550 non-whitespace-character count counts every Latin letter separately and is not used as a Chinese word count. No abstract text was shortened; the accepted word count is within 300–500.

## Frozen figures

Figures 1–3 reuse the Phase 13.5 Chinese PNGs directly; scientific lineage is Phase 13.1 and the frozen Phase 7/8/9 evidence. At 2,400 pixels across 154 mm, effective resolution is approximately 396 dpi. This preserves the accepted Chinese raster rendering.

Figure 4 uses a layout-only derivative of the frozen SVG. Exactly three edits extend height from 648 to 708, update the viewBox, and translate the legend group by (-350,145). The validator reverses these edits and recovers the entire original SVG exactly, proving all chart geometry, labels and values unchanged. Chrome rendered it at 2,400 pixels using Microsoft YaHei. The legend is now outside the data region. No frozen image was overwritten.

## Visual acceptance

All 15 pages were individually viewed, not just a contact sheet. Final renders are qa/final-page-01.png through final-page-15.png at 200 dpi. Initial 144 dpi views were supplemented by final high-resolution inspection of cover, abstract, contents, method/equation, DOEF, result and reference pages.

| Pages | Content | Result |
|---|---|---|
| 1–3 | Cover, abstract, automatic contents | PASS |
| 4–5 | Background, figure 1, units and data | PASS |
| 6 | Tables 1–2, MAE/RMSE/MAPE | PASS |
| 7–8 | Battery table, MILP, regret and DOEF | PASS |
| 9 | Weight table and repaired figure 4 | PASS |
| 10–12 | Main table, figures 2–3, negative results, reuse | PASS |
| 13–14 | Engineering boundaries, conclusion and references | PASS |
| 15 | Evidence appendix | PASS |

Clipping, overflow, overlapping, broken tables/equations, missing glyphs/images, unexpected font substitution, orphan headings, broken pagination and unexpected blank pages: none in the accepted version. Scientific images are neither stretched nor cropped. Formula signs, exponents, Greek letters and negative/percentage values were inspected.

## Semantic acceptance and scientific freeze

validate_pdf.py verifies 209 normalized prose/table segments, 69 distinct non-heading decimal tokens, 11 display equations and 21 inline equations. All are preserved. It checks exact weight-table entries, forecast-table MAE/RMSE/MAPE, reported improvements and intervals, battery configuration and negative robustness values against frozen artifacts. All 76 registered scientific files match baseline Git blobs and registered raw/LF hashes; protected scientific directories and source implementation have no changes.

claim_consistency_audit.md covers forecast ≠ decision, DOEF's fixed blend, Validation-only selection, Test evaluation-only role, frozen dispatch reuse, fixed-eight-building scope, regret, battery, failed experiments and limited engineering implications. Every claim remains supported within its original scope. No claim of field deployment, universal superiority, unseen-building transfer or cost/carbon savings was added.

## Reproduction and editing

Editable LaTeX: technical_report_layout.tex. Run XeLaTeX three times from this directory with -interaction=nonstopmode -halt-on-error -no-shell-escape, then save the compiled PDF as technical_report_submission.pdf with PyMuPDF garbage=4 and deflate=True, as shown in build_pdf.py. Run python reports/phase13_6/validate_pdf.py from the repository root and rerender for acceptance.

To regenerate TeX directly from canonical Markdown: python reports/phase13_6/build_pdf.py. This overwrites generated TeX, so preserve intentional direct TeX edits separately first. Python requires PyMuPDF; XeLaTeX needs fontspec/xeCJK and the recorded Windows fonts. The existing derivative/logo are included, so no browser is needed for ordinary rebuilds. layout_figure.mjs records the one-time SVG rendering method and this host's runtime paths.

## Git closure

Branch main. Starting HEAD, origin/main and frozen-baseline merge-base: 4a72c23d4b735e5679c900c6d06160faba2bc866. The final commit containing this report includes the PDF, TeX, build/QA sources, assets, audit evidence, authorized reference corrections and README navigation. Ending commit is the containing commit (not embedded here to avoid self-reference). Clean working tree is verified after commit. No push, upload or next-phase work is performed.

