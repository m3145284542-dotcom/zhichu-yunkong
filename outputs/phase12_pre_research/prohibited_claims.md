# Phase 12 Pre-Research Prohibited Claims

Status: **DRAFT / NOT FROZEN**. These are already unsafe under current internal and external evidence.

| Claim | Verdict | Why | Safe replacement |
| --- | --- | --- | --- |
| LightGBM 预测精度全面最好 | REJECTED | Phase 3 Test MAE trails persistence; Phase 7 winners vary. | LightGBM is a strong frozen component and comparator. |
| 预测越准，调度一定越好 | REJECTED | 6/8 ensemble weights differ; external BESS studies report mismatch. | Accuracy does not fully represent downstream value in this evaluated setting. |
| 鲁棒优化提升了 Test 性能 | REJECTED | Phase 5.7 robust strategy is worse on mean and tail metrics. | The negative result was retained and triggered a stop rule. |
| DOEF 是全新的 Decision-Focused Learning 算法 | REJECTED | It does not backpropagate or train on the optimizer; DFL and storage DFL predate it. | DOEF is decision-oriented validation/model-selection, adjacent to but distinct from end-to-end DFL. |
| 首次提出 / first / first-ever / 国内首个 / 国际首个 | REJECTED | Direct prior work exists for value-based model selection and decision-focused forecast pooling. | To our knowledge is also withheld until Phase 12 systematic search. |
| 在所有建筑上均有效 | REJECTED | Eight selected offices, one Test month; no unseen-building transfer. | 6/2/0 vs LightGBM on the frozen eight-building regret comparison. |
| 达到工业部署水平 | REJECTED | Offline simulation; no API/front end/field deployment. | Competition-oriented reproducible simulation pipeline. |
| 证明实际电费一定降低 | REJECTED | No tariff or bill model. | Simulated maximum-power/decision-regret improvement under the frozen protocol. |
| 证明新能源消纳效果 | REJECTED | No renewable generation or curtailment model. | Potential demand-side flexibility relevance only. |
| 优于所有现有方法 | REJECTED | No exhaustive benchmark; direct related methods use different tasks/data. | Outperformed frozen LightGBM on the stated internal comparison. |
| DayWeek + LightGBM ensemble itself is novel | REJECTED | Seasonal baselines, tree models and weighted ensembles are established. | Contribution is the transparent downstream-regret selection/evaluation in this application. |
| Multi-building selection is an algorithmic innovation | REJECTED | It is evaluation methodology and rigor. | Train-only anti-cherry-picking design (LEVEL C). |
| DOEF universally improves battery scheduling | REJECTED | Limited buildings, month and optimizer. | Improvement is bounded to the frozen experiment. |
