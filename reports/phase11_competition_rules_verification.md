# Phase 11 Competition Rules & Submission Specification Verification

## 1. Executive Verdict

- **PHASE 11 — PASS**
- **READY FOR PHASE 12 — YES**
- Official competition identity: **VERIFIED**.
- Actual project track: **VERIFIED by the user's 2026-09-01 project confirmation** as **算法主题赛（AI+能源）—科技创新组**; the corresponding official track and submission rules are verified.
- Rules baseline for Phase 12-15: only the AI+能源科技创新组 rules and its `20/10/25/25/10/10` rubric. The separately checked 算法创新赛—算法模型创新 rules are retained only as identity-disambiguation evidence and are **NOT APPLICABLE**.
- Material unresolved items remain explicit. None blocks Phase 12; several must be rechecked before Phase 14 or Phase 15 acceptance.

This phase verified and structured rules only. It did not alter DOEF v1.0, run models, recalculate results, write the final competition report, create a deck/video/GUI/demo, or repair the known canonical loader defect.

## 2. Repository State

| Item | Verified value |
| --- | --- |
| Repository | `D:/document/aic` |
| Starting branch | `codex/phase12-pre-research` |
| Starting HEAD | `70abbf7d617d7f35fbc86a30efa60ef9dcd144a6` |
| Git state at start | clean |
| Frozen algorithm baseline | `549abc314e93e2862bfc22965db89622c22890e1` |
| Frozen baseline relationship | ancestor of starting HEAD |
| Phase 10 branch commit in history | `12a204f` (`codex/phase10-deliverable-audit`) |
| Phase 10 report | present and read in full |
| Phase 10 machine outputs | `deliverable_gap_matrix.csv` and `delivery_roadmap.json` present and read |

The current branch name is ahead of the permitted sequence and already contained Phase 12 pre-research files before this task. They were not created, edited, interpreted as accepted Phase 12 output, or used to bypass Phase 11. Phase 10 was not rerun merely because the checkout was not on its named branch.

The known `src/final_algorithm.py` parent-hash/lineage delivery defect remains recorded only. No repair, hash registration, model execution, or frozen-artifact edit was performed.

## 3. Competition Identity Verification

| Field | Verified identity |
| --- | --- |
| Chinese name | 全球校园人工智能算法精英大赛 |
| User shorthand | “全球人工智能算法精英大赛” (missing the official word “校园”) |
| English name | Global Campus Artificial Intelligence Algorithm Elite Competition |
| Acronym | AIC |
| Edition/year | 8th edition, 2026 |
| Competition period | 2026-04 through 2026-12 |
| Highest decision body | 全球校园人工智能算法精英大赛组委会 |
| Secretariat | 江苏省人工智能学会 |
| Official website | <https://www.aicomp.cn/> |
| Official registration platform | <https://reg.aicomp.cn/> |
| Actual track | 算法主题赛（AI+能源） |
| Group | 科技创新组 |
| Problem type | Open/self-defined topic within AI+energy, not a fixed dataset leaderboard task |
| Project fit | Official examples include energy-storage intelligent management/optimal dispatch and load forecasting |
| Current stage as of 2026-09-01 | registration and preliminary-submission preparation |

Identity evidence comes from the [eighth-edition notice](https://www.aicomp.cn/wp-content/uploads/2026/04/%E5%85%B3%E4%BA%8E%E4%B8%BE%E5%8A%9E%E7%AC%AC%E5%85%AB%E5%B1%8AAIC%E7%AE%97%E6%B3%95%E5%A4%A7%E8%B5%9B%E7%9A%84%E9%80%9A%E7%9F%A5-2.pdf), the [2026 charter](https://www.aicomp.cn/bylaws), and the [AI+energy official track page](https://www.aicomp.cn/tracks/4726.html). The user's explicit track confirmation is project-state evidence; the organizer's page is the authority for the selected track's rules.

## 4. Official Source Hierarchy

Only Tier 1 sources are used for verified requirements:

1. 2026 official organizer notice and current charter.
2. Official AI+energy track notice, submission-rule attachment, and technical-report outline.
3. Official live competition/registration pages.

Search-result snippets, 2025 final guides, provincial schedules from earlier editions, university news, and reposts were used only to locate current official pages. No historical source has been promoted to a 2026 rule.

Downloaded official PDFs are immutable source copies under `docs/competition_rules/`; their URLs, dates, versions, page counts, and SHA-256 values are in `outputs/phase11/source_manifest.json`.

## 5. Track and Eligibility

For AI+能源科技创新组:

- Eligible: enrolled graduate, undergraduate, and junior-college/vocational-college students in domestic or overseas universities/research institutes.
- Ineligible: enterprise personnel or people without current student status.
- Team: 1-3 students; one captain.
- Cross-school teams: prohibited, including branch-campus cross-school grouping.
- Advisors: 0-2; the rule says “最多” and does not make an advisor mandatory.
- Membership: within the same group, each participant may join only one team.
- After registration closes, member/advisor information cannot be changed.
- Year-of-study limits and nationality restrictions beyond enrolled-student status: no authoritative rule found.
- Identity review document details for this track: not yet published. The general charter requires progressive information review; exact documents remain UNKNOWN.

## 6. Competition Timeline

| Event | Absolute date/status |
| --- | --- |
| General registration opened | 2026-04-28 |
| AI+energy registration deadline | **2026-10-15 20:00** |
| AI+energy preliminary work deadline | **2026-10-15 20:00** |
| Modification after preliminary deadline | prohibited |
| Preliminary review | after 2026-10-15; exact date UNKNOWN |
| Semifinal | online; completed no later than **2026-10-31**; exact date UNKNOWN |
| Final | offline; completed no later than **2026-11-30**; exact date/location UNKNOWN |
| Final defense | 8-minute presentation + 5-minute judge Q&A |
| Result announcement | official website, but exact date UNKNOWN |
| Supplementary-material deadline | UNKNOWN |

The source says “10月底前” and “11月底前”; this report normalizes those latest dates to 2026-10-31 and 2026-11-30 without inventing exact event days.

## 7. Deliverable Requirements

The selected group requires:

- runnable code, model, or system prototype, with data and detailed deployment instructions;
- technical report in PDF;
- defense/presentation deck submitted as PDF;
- MP4 demonstration video;
- a permanent Baidu Netdisk link for code/model/system-prototype and other large files;
- commitment letter under the general charter (template/signing method not yet found).

The selected project is code-based, so the reproducibility clauses make the full runnable code package mandatory in practice. The rules do not specifically mandate `requirements.txt`, `environment.yml`, Docker, notebook, separate training/inference scripts, model-weight file format, README filename, or executable binary. They require the functions those artifacts would serve: runnable code, complete package, data/access method, detailed environment configuration, deployment instructions, and reproducible core results.

## 8. Report Requirements

**REPORT REQUIREMENT — VERIFIED / REQUIRED**

| Attribute | Requirement |
| --- | --- |
| Official name | AI+能源技术报告 / 技术报告 |
| Format | PDF |
| Maximum size | 10 MB |
| Official template/outline | yes; official Attachment 2 downloaded and hashed |
| Page limit | UNKNOWN |
| Total word limit | UNKNOWN |
| Abstract | 300-500 Chinese characters |
| Main text | 小四号宋体, single spacing |
| References | 五号宋体, 20 pt spacing |
| Cover | work name, group=科技创新组, team name, date |
| Anonymous boundary | no school, participant identity, or advisor identity in anonymous materials; team name is present in the official cover template |
| File naming | upload/file naming ultimately depends on team number and work name |

Required content is the union of the submission-rule attachment and outline:

- abstract and keywords;
- introduction/background, energy-industry pain point, AI application value, project objective;
- related work / literature and technology review;
- overall architecture, core algorithm/model, training/optimization, data processing, system-function implementation;
- experiment environment, metrics, comparisons/ablations/simulation as applicable, results and analysis;
- innovation points and application prospects/expected value;
- limitations, AI ethics risks and mitigations, future work;
- conclusion, references, and optional appendix with core code/deployment/data tables.

The outline says interface screenshots “可配以”; screenshots are not mandatory.

## 9. PPT / Defense Requirements

**PPT REQUIREMENT — VERIFIED / REQUIRED**

- A presentation/defense deck is required.
- The submitted deck must be PDF.
- It must cover work information, background, core technology, innovation, and application prospects.
- No official page limit, file-size limit, or PPT template was found.
- Final: offline, 8-minute presentation + 5-minute Q&A.
- General charter: team members should all attend; a no-show team is treated as withdrawn.
- Specified lead speaker, per-member speaking duties, and video-play allowance are UNKNOWN.

## 10. GUI / Demo / Video Requirements

### GUI/DEMO REQUIREMENT VERDICT

| Item | Verdict | Official basis |
| --- | --- | --- |
| GUI/Web/App | **NOT REQUIRED** | Code/model/system prototype are alternative implementation carriers; interface screenshots are optional (“可配以”). |
| Application demonstration | **REQUIRED** | System completeness includes application display, and the mandatory video must demonstrate functions, implementation flow, and application effects. |
| Separate live interactive demo | **UNKNOWN** | No dedicated live-demo segment or time is specified. |
| Demonstration video | **REQUIRED** | MP4, strictly 3-5 minutes, no more than 300 MB. |

The notice body says “5 minutes以内”; the more specific submission attachment says “3-5 minutes”. These are compatible, and the stricter attachment range controls. Resolution, orientation, narration, subtitles, editing, on-camera presenter, and public video-hosting requirements are UNKNOWN.

Phase 11 did not build a GUI, system prototype, demo, or video.

## 11. Code / Model / Reproduction Requirements

**SOURCE CODE REQUIREMENT — VERIFIED / REQUIRED**  
**REPRODUCIBILITY REQUIREMENT — VERIFIED / REQUIRED**

The official attachment states that code must run and experiment results must be reproducible. It further requires a complete code package, dataset or acquisition method, and detailed environment configuration so judges can reproduce core results.

No official CPU/GPU, network, run-time, OS, container, archive-size, or package-format restriction was found. A low-cost/offline reproduction path remains prudent engineering but is not represented as an official hardware rule.

The Phase 10 canonical loader defect is directly relevant to the later reproducibility gate. It remains open and unmodified; Phase 11 neither repairs nor conceals it.

## 12. Dataset / External Data Policy

**DATASET POLICY — VERIFIED**

- Open-source algorithms and third-party data are allowed conditionally.
- Their source must be clearly identified and use must comply with the applicable authorization/license.
- The submission must provide the dataset or an acquisition method.
- The report must explain data source, processing/feature engineering, and evaluation metrics.
- The rules do not require self-collected data and do not prohibit public datasets.
- BDG2 is not named. It is therefore allowed only under the general third-party/public-data conditions; its citation, license, download route, and redistribution boundary must be verified in Phase 15.
- Internet-data limits are not specified.
- Data privacy protection and applicable standards are required, but no named privacy standard is supplied.

## 13. AI-Assisted Development Policy

**AI ASSISTANCE POLICY — PARTIAL**

An unusual positive rule is explicit: in the AI+energy student group, showing use of an AI toolchain to improve development efficiency and simulate a “one-person-led” full-stack workflow can be an evaluation bonus.

However, no current authoritative source was found that:

- names ChatGPT, Codex, Copilot, or equivalent tools;
- defines permitted or prohibited generated-code scope;
- specifies an AI-use disclosure template;
- specifies generated-code attribution or percentage limits.

The general originality, truthfulness, non-plagiarism, and IP clauses still apply. The result is not “AI tools are unrestricted”; it is `PARTIAL / NO AUTHORITATIVE TOOL-SPECIFIC RULE FOUND`. This does not block Phase 12, but it must be resolved or transparently disclosed before final integrity/submission acceptance.

## 14. Open Source / IP / License Requirements

**OPEN SOURCE REQUIREMENT — NOT REQUIRED**

- No GitHub/Gitee or public-repository requirement exists.
- Submission of full source through a permanent private material link is required; this is not the same as public open source.
- Use of open-source algorithms is allowed if cited and license-compliant.
- No mandatory repository `LICENSE`, dependency-license list, software copyright certificate, or patent was found.
- The work's copyright belongs to the team; organizers retain rights to display, publish, distribute, and use the work in public-interest science activities under the charter.
- Third-party patent, copyright, trademark, likeness, reputation, and privacy rights must not be infringed.
- Rules on public release after the competition and effect on later academic publication are UNKNOWN.

## 15. Scoring Rubric

**SCORING RUBRIC VERIFIED — YES, for AI+能源科技创新组**

| Official scoring dimension | Points | Weight |
| --- | ---: | ---: |
| 问题聚焦与创新价值 | 20 | 20% |
| 需求洞察与背景分析 | 10 | 10% |
| 技术深度与框架构建 | 25 | 25% |
| 实验验证与结果分析 | 25 | 25% |
| 应用价值与推广潜力 | 10 | 10% |
| 反思局限与未来展望 | 10 | 10% |
| **Total** | **100** | **100%** |

Important scoring implications, without entering Phase 12:

- 50% is technical depth plus experimental validation.
- Innovation is assessed together with accurate energy-problem focus and originality.
- Background points explicitly include literature/technology review and trustworthy data.
- Application value asks for practical and economic value, but frozen evidence does not support fabricated cost/energy/emissions claims.
- Limitations, ethics, and future directions are a full 10%, not optional defensive prose.

The 算法模型创新 rubric (`20/20/20/20/15/5`) is not applicable and must never be blended with this table.

## 16. Submission Package Specification

| Element | Verified requirement |
| --- | --- |
| Platform | AIC registration system, <https://reg.aicomp.cn/> |
| Preliminary deadline | 2026-10-15 20:00 |
| Report | PDF, ≤10 MB |
| Deck | PDF; page and size limit UNKNOWN |
| Video | MP4, 3-5 minutes, ≤300 MB |
| Code/model/prototype | permanent Baidu Netdisk link, with extraction code |
| Data/environment/deployment | dataset or access method; detailed environment and deployment instructions |
| Root/file naming | `参赛团队编号-赛题名称-作品名称-XX（材料名称）` |
| Anonymous content | no school, participant, or advisor identifying information |
| Commitment letter | required by charter; template/signature process UNKNOWN |
| After deadline | no modification |

Unknown: archive format, total package size, exact file count, PPT size, whether repeated overwrite is supported before deadline, team number, commitment-letter template, and any later final-round upload deadline.

## 17. Rule Conflicts

No direct conflict between authoritative current-edition sources was found.

- General notice versus AI+energy notice: track-specific dates supersede the general planning window for this track.
- AI+energy notice “≤5 minutes” versus submission attachment “3-5 minutes”: compatible; use the more specific 3-5-minute rule.
- Algorithm-model-innovation versus AI+energy scoring: different tracks, not a conflict. The user confirmed AI+energy; the other rubric is excluded.
- The AI+energy notice PDF's document date is 2026-07-10, its URL filename contains `260711`, and the website published it on 2026-07-13. All three version signals are preserved in the source manifest rather than silently collapsed.

## 18. Unknown / Not Yet Published Requirements

### BLOCKING

None for entry to Phase 12.

### NON-BLOCKING

- Team number (needed for final naming).
- ChatGPT/Codex/Copilot-specific disclosure and generated-code policy (must be resolved before final integrity acceptance).
- Exact semifinal date; exact final date/location; detailed final notice.
- PPT page/size/template, live-demo allocation, lead-speaker rule, and venue network/equipment.
- Video resolution/orientation/narration/subtitle/editing/on-camera rules.
- Archive format, total size/file count, pre-deadline overwrite behavior, commitment-letter template.
- CPU/GPU/network/runtime limits.
- Public-release and later-publication policy.

## 19. Phase 12-15 Constraint Mapping

### Phase 12 Input Constraints

- Position only for **算法主题赛（AI+能源）—科技创新组**.
- Frame the problem around energy storage management/optimal dispatch, load forecasting, and energy-side engineering value.
- Use the official score priorities: innovation/problem focus 20; background/literature/data 10; technical depth 25; experiments 25; application 10; limitations/ethics/future 10.
- Separate algorithmic contribution, engineering integration, and application value; do not claim base algorithms as novel.
- Literature comparison must support problem positioning, technical alternatives, and baselines; public/third-party data provenance must be explicit.
- Do not use the excluded algorithm-model-innovation rubric.

### Phase 13 Input Constraints

- Produce the official AI+energy **technical report**, PDF ≤10 MB.
- Use the downloaded official outline: 300-500-character abstract; main text 小四宋体/single spacing; references 五号宋体/20 pt.
- Include the union of required sections: abstract, introduction/background, related work, method, data, architecture, experiments/results, innovation/application, limitations/ethics/future, conclusion, references.
- Include clear diagrams and data charts; GUI screenshots are optional.
- Maintain anonymous identity boundaries.
- Page count and total word count remain UNKNOWN.

### Phase 14 Input Constraints

- Required deck, submitted as PDF; design for an 8-minute presentation plus 5-minute Q&A.
- Final is offline and team members should all attend.
- Required MP4 demonstration video, 3-5 minutes and ≤300 MB.
- Video must show functions, implementation flow, and application effects.
- GUI is not required; a separate live interactive demo is UNKNOWN.
- Keep video/deck offline-capable until venue/network rules are published; this is risk management, not an official rule.

### Phase 15 Input Constraints

- Deadline: 2026-10-15 20:00 for registration and preliminary package; no modification afterward.
- Submit through the AIC registration system; use a permanent Baidu Netdisk material link.
- Use team-number/track/work-name naming after the team number is known.
- Include runnable full code, data or access route, detailed environment/deployment configuration, and reproducible core results.
- Recheck/report the frozen canonical loader defect; repair only with separate authorization.
- Open-source publication is not required, but third-party algorithm/data licenses and citations are mandatory.
- Enforce anonymous materials and obtain the official commitment-letter template.
- Recheck unknown portal file/size/overwrite fields near packaging time.

This mapping freezes inputs only; no Phase 12-15 deliverable was produced.

## 20. Phase 11 Final Verdict

| Key verdict | Result |
| --- | --- |
| TRACK_VERIFIED | VERIFIED |
| ELIGIBILITY_VERIFIED | VERIFIED |
| REPORT_REQUIREMENT | VERIFIED |
| PPT_REQUIREMENT | VERIFIED |
| DEFENSE_REQUIREMENT | VERIFIED |
| GUI_REQUIREMENT | NOT REQUIRED |
| DEMO_REQUIREMENT | PARTIAL (recorded application demo required; separate live demo UNKNOWN) |
| VIDEO_REQUIREMENT | VERIFIED |
| SOURCE_CODE_REQUIREMENT | VERIFIED |
| OPEN_SOURCE_REQUIREMENT | NOT REQUIRED |
| REPRODUCIBILITY_REQUIREMENT | VERIFIED |
| DATASET_POLICY | VERIFIED |
| AI_ASSISTANCE_POLICY | PARTIAL |
| SUBMISSION_PACKAGE_REQUIREMENT | PARTIAL |
| SCORING_RUBRIC_VERIFIED | VERIFIED |

**PHASE 11 — PASS**  
**READY FOR PHASE 12 — YES**

The only permitted next phase is **Phase 12 — Innovation Positioning & Claim Freeze**.
