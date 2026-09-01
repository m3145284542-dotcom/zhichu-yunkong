# Phase 12 Frozen Prohibited Claims

Status: **FROZEN**  
Applies to: Phase 13 report and figures, Phase 14 PPT, oral defense, script and video.

Only wording approved in `claim_evidence_matrix.csv` or `innovation_claims_frozen.json` may be used. A safe alternative remains bounded by every caveat shown below.

| Prohibited or restricted wording | Decision | Why | Safe bounded alternative |
|---|---|---|---|
| “首次提出决策导向预测” | PROHIBITED | Value-oriented forecasting, predict-then-optimize and DFL predate DOEF. | “DOEF 将已有的价值导向思想具体适配为建筑储能削峰的 Validation regret 选权重机制。” |
| “首个 decision-focused ensemble” | PROHIBITED | L016 learns probabilistic linear-pool weights from downstream cost; L020 also uses task-aware weighting in a battery-forecast setting. | “DOEF 使用透明的确定性两模型凸融合，并由 Validation 储能 regret 选择权重。” |
| “全新的 DFL 算法” | PROHIBITED | DOEF is not a new theoretical learning objective. | “DOEF 是轻量、非端到端的 decision-oriented method adaptation。” |
| “端到端 decision-focused learning” | PROHIBITED | Components are not retrained through the optimizer. | “DOEF 在冻结基模型预测之后，以 held-out Validation regret 选择融合权重。” |
| “LightGBM 全面优于其他方法” | PROHIBITED | Winners vary by building and metric. | “LightGBM 是 DOEF 的一个冻结组件和主要比较基线。” |
| “预测越准调度一定越好” | PROHIBITED | The frozen rankings materially diverge. | “在本实验中，更优预测排名并不必然对应更优储能决策排名。” |
| “预测精度不重要” | PROHIBITED | DOEF also improves normalized MAE; accuracy remains relevant. | “预测精度必要但在本实验中不足以单独代表下游决策价值。” |
| “DOEF 在所有建筑都有效” | PROHIBITED | Scope is eight fixed office buildings, with ties and retained failures. | “在冻结的 8 栋办公建筑 Test 上，DOEF 相对 LightGBM 的 decision-regret 结果为 6 胜、2 平、0 负。” |
| “8 栋建筑证明了全体建筑泛化” | PROHIBITED | No population-wide inference is justified. | “8 栋建筑提供了冻结的多建筑稳健性评估证据。” |
| “实现 unseen-building transfer” | PROHIBITED | Models and weights are building-specific; no unseen-building transfer protocol exists. | “建筑在 Test 前固定，但不构成 unseen-building transfer。” |
| “所有建筑筛选完全只使用 Train” | PROHIBITED | Raw availability over predefined Validation/Test windows participates in eligibility. | “在固定 raw-coverage eligibility 后，代表性 morphology 与采样仅使用 Train，且不使用 Validation/Test 性能。” |
| “鲁棒优化提升了 Test” | PROHIBITED | The frozen Phase 5.7 robust strategy was worse. | “该鲁棒分支未通过 Test，作为 stopping-rule 负结果保留。” |
| “鲁棒优化普遍无效” | PROHIBITED | Phase 5.7 is one building, 30 days and one formulation. | “在 Phase 5.7 的冻结单建筑设置下，该鲁棒策略未优于确定性方案。” |
| “Peak-aware LightGBM 提升了结果” | PROHIBITED | Validation selected alpha=0 for 7/8 and the branch lost/tied on Test. | “Peak-aware 分支被冻结的 Validation 规则拒绝并作为负结果保留。” |
| “已经真实部署” | PROHIBITED | Results are simulated. | “完成了冻结多建筑数据上的模拟调度评估。” |
| “已证明降低真实电费” | PROHIBITED | No tariff/cost model or field trial exists. | “在冻结模拟协议下减少了最大功率峰值。” |
| “已证明降低碳排放” | PROHIBITED | No carbon model exists. | No replacement performance claim; state as future work only. |
| “已证明提高新能源消纳” | PROHIBITED | No renewable-consumption metric exists. | No replacement performance claim; state as future work only. |
| “6.44% 节能” | PROHIBITED | 6.44% is mean whole-window maximum-peak reduction, not energy reduction. | “平均 whole-window 峰值削减 6.44%（模拟）。” |
| “显著优于 LightGBM” | RESTRICTED | The building bootstrap supports a negative interval, but no separate hypothesis-test claim is frozen. | “building-level bootstrap 95% 区间为 [-0.00685, -0.00172]；仅作为 8 个建筑单位下的不确定性证据。” |
| “优于所有现有方法” | PROHIBITED | No exhaustive benchmark supports it. | “相对冻结基线 LightGBM，DOEF 的 mean normalized regret 下降 3.61%。” |
| “世界领先” | PROHIBITED | Unsupported superiority claim. | No replacement. |
| “填补国内外空白” | PROHIBITED | Contradicted by verified international prior art. | “提供一个具体、透明、可审计的建筑储能场景适配。” |
| “完整 fail-closed reproducibility 已解决” | PROHIBITED | A HIGH open Phase 7 clean-checkout loader/hash consistency defect remains. | “存在 machine-readable lineage 与审计机制，但仍保留一个已知 clean-checkout hash-consistency 风险。” |
| “Oracle 是可部署方法” | PROHIBITED | Oracle uses hindsight actual load. | “Oracle 是不可部署的 hindsight upper bound，用于定义 regret。” |
| “6/2/0 是 peak-reduction 胜平负” | PROHIBITED | The triplet is based on mean daily decision regret. | “decision-regret 胜/平/负为 6/2/0。” |
| “rank agreement 0.344 是相关系数” | PROHIBITED | It is an exact-rank agreement rate. | “32 个 building×method 条目的 exact rank agreement rate 为 0.344。” |

## Non-negotiable scope qualifiers

- Say **simulated** or **under the frozen dispatch protocol** for all storage outcomes.
- Distinguish normalized MAE, normalized decision regret and whole-window peak-reduction percentage.
- State whether a number is a mean, median, per-building value or macro-average.
- Treat Oracle as non-deployable and Test as evaluation-only.
- Keep the Phase 5.7 robust, Phase 9 peak-aware and CatBoost extreme negative outcomes visible when discussing evaluation integrity.
- Do not cite provisional Phase 12 pre-research wording unless the corresponding formal row is `APPROVED` or `APPROVED_WITH_SCOPE`.
