# Phase 13.6 official-rule audit and compliance checklist

Audit date: 2026-09-05. Phase gate: **PASS**.

## Sources and precedence

1. [Official current AI+能源 notice and linked attachments 1/2](https://www.aicomp.cn/notice/notice-3/4702.html), dated 2026-07-10. Attachment 1 is the 科技创新组竞赛规则及作品提交要求; Attachment 2 is the 科技创新组技术报告参考大纲. Both were reopened online for this phase.
2. [General competition bylaws](https://www.aicomp.cn/bylaws). Track-specific attachment requirements take precedence.

Downloaded official PDFs, URLs and SHA-256 values are recorded in `qa/official_rules_manifest.json`.

| Item | Official requirement / finding | Final status |
|---|---|---|
| Template | Attachment 2 supplies cover, reference outline and typography | Applied to cover, five major groups and heading hierarchy |
| Format | Technical report PDF required | PASS — PDF 1.7 |
| File size | At most 10 MB | PASS — 1,096,777 bytes |
| Page count | No explicit maximum found | PASS — 15 A4 pages |
| Font / size / spacing | Body/abstract 小四号宋体, single spacing; references 五号宋体, 20 磅行距 | PASS — SimSun body 12 pt; references 10.5 pt with 20 pt leading |
| Margins / paper | No numerical margin requirement stated; official attachment is A4 | PASS — A4, 28 mm sides and 25 mm top/bottom |
| Cover | Competition, track, report, work title, group, team and date fields | PASS — team 电协 and date 2026-09-05 |
| Work title | Fill work title; no track-specific length limit found | PASS — frozen title retained |
| Anonymous review | School and instructor information prohibited in submitted materials | PASS — no school, instructor or member names added |
| Contents | No explicit requirement | PASS — automatic clickable contents and PDF bookmarks |
| Abstract | 300–500 字 | PASS — 402 words using Chinese-character and Latin/numeric-token count; 373 CJK characters also recorded |
| Keywords | Supplied in template | PASS — frozen keywords retained |
| References | Necessary references; 五号宋体, 20 磅行距 | PASS — 11 frozen entries; [2] metadata corrected and independently verified |
| Figures / tables | Clear and standardized | PASS — all figures/tables visually inspected and source values preserved |
| Commitment letter | No report attachment requirement found | PASS — no unrequested attachment invented |
| External links / QR | No report-specific ban found | PASS — no QR or unrequested external submission link |
| Filename | Network-drive material naming format is stated; no distinct direct-upload technical-report filename rule found | PASS — canonical filename `technical_report_submission.pdf`; platform-specific prefix remains a human check |
| Other submission materials | PPT PDF, 3–5 minute MP4 <=300 MB, code/model/prototype links | PASS for this PDF phase — these separate materials are outside scope |

## Gate checklist

- [x] Official rules rechecked
- [x] Official template requirement checked
- [x] Canonical Markdown hash recorded
- [x] Scientific freeze preserved
- [x] Final PDF generated
- [x] PDF opens successfully
- [x] Page count checked
- [x] File size checked
- [x] PDF naming checked
- [x] Fonts checked — all listed fonts embedded
- [x] Chinese glyphs checked on every rendered page
- [x] Every page visually inspected
- [x] Tables inspected
- [x] Figures inspected
- [x] Equations inspected
- [x] References inspected
- [x] Key numeric values cross-checked
- [x] PDF text extraction checked
- [x] No missing pages
- [x] No unexpected blank pages
- [x] No local-path leakage
- [x] No comments or annotations
- [x] No tracked changes
- [x] Official submission constraints satisfied for this report artifact
- [x] Git working tree clean after the Phase 13.6 commit

All items are checked. The only remaining actions are platform-side human submission steps listed in the final report.
