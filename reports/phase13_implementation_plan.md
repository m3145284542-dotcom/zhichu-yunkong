# Phase 13.0 输入冻结与实施设计

状态：HOLD
日期：2026-09-02
工作分支：codex/phase13-visual-report-demo
起始 HEAD：3d77272c36108fffcdcb4f73c240b52bbfc4de86
算法冻结基线：549abc314e93e2862bfc22965db89622c22890e1

## 1. 结论与成功标准

Phase 10、11、12 的正式链路、Phase 9.1 semantics 以及 Phase 7/8/9 图表源均已完成只读核验。Phase 12 的 CORE-1 LEVEL B、CORE-2/3 LEVEL C、headline number ledger、prior-art 边界和 prohibited claims 可以完整继承。

本阶段不能判 PASS，也不能进入 Phase 13.1。阻塞原因不是算法或结论异常，而是展示数据缺口：冻结仓库没有可供 Figure 6 和 GUI Tab 2/3 使用的多建筑逐小时预测与逐小时调度表。Phase 8 在运行时生成 dispatch DataFrame 并绘制 representative PNG，但只保存 aggregate、per-building、daily 指标和 PNG，没有保存 actual、forecast、charge、discharge、SOC、realized grid load 的逐小时机器可读行。outputs/phase7/ensemble_test_results.csv 已注册但为 0 行。

验收判断：Source-of-Truth Contract、报告结构、Figure Plan、GUI Spec 和 GUI Data Map 均已完成；F01–F05 以及解释/统计类 supporting figures 有正式数据源；F06 和 GUI 两个时序页面不满足“不重算 + canonical machine-readable source”的核心条件，因此总 verdict 为 HOLD。

## 2. Git 与隔离审计

- 只读起始目录：D:/document/aic。
- 起始分支：main。
- 起始 HEAD：3d77272c36108fffcdcb4f73c240b52bbfc4de86，正好等于声明的 Phase 12 freeze commit。
- 起始工作区：clean；modified、staged、untracked 均为 0。
- 算法冻结基线是 Phase 12 freeze 的祖先；Phase 12 相对算法基线 ahead 5、behind 0。
- Phase 12 freeze 与起始 HEAD ahead 0、behind 0。
- 在确认目标分支不存在且工作区干净后，从 Phase 12 freeze 创建 codex/phase13-visual-report-demo；未 reset、未覆盖用户修改。

## 3. 上游正式状态核验

### Phase 10

正式报告、deliverable gap matrix 和 delivery roadmap 均存在并可解析。Phase 10 定义的 Phase 13/14/15 顺序与当前任务一致。其 HIGH / OPEN canonical-loader 缺陷继续成立：Phase 7 report/manifest 的 clean-checkout bytes 与已注册 parent hashes 不一致。该缺陷不代表预测或结果改变，但阻止宣称 clean-checkout loader 已完整解决。

### Phase 11

正式报告、5 个机器可读规则输出以及 docs/competition_rules 下 6 份官方 PDF 均存在。6 份 PDF 已完整抽取文本；AI+能源报告大纲 4 页和科技创新组提交规则 3 页另做了逐页渲染核验。

核验后的选定赛道为算法主题赛（AI+能源）—科技创新组。适用评分为：问题聚焦与创新价值 20；需求洞察与背景分析 10；技术深度与框架构建 25；实验验证与结果分析 25；应用价值与推广潜力 10；反思局限与未来展望 10。算法模型创新组 rubric 不适用。

技术报告必须为 PDF 且不超过 10 MB；摘要 300–500 字；正文小四号宋体、单倍行距；参考文献五号宋体、20 磅行距。技术报告页数与总字数仍为 UNKNOWN。答辩/PPT 必须提交 PDF。演示视频必须为 MP4、严格 3–5 分钟且不超过 300 MB。GUI/Web/App 不是硬性要求；应用展示和视频中的功能/流程/效果展示是要求。匿名材料不得出现学校、参赛者或指导教师身份信息。初赛提交/报名截止为 2026-10-15 20:00，截止后不得修改。

仍未解决的主要 UNKNOWN：PPT 页数/大小/模板，独立 live-demo 时段，视频分辨率/方向/字幕/出镜规则，归档格式和总大小，承诺书模板，队伍编号，复赛/决赛精确时间地点，AI 工具专项披露细则与运行硬件限制。

### Phase 12

正式分支和 freeze commit 与用户声明一致。CORE-1 固定为 LEVEL B / MEDIUM-HIGH：DOEF uses optimizer-derived Validation peak-shaving regret to select a fixed DayWeek–LightGBM blend before Test evaluation。CORE-2 和 CORE-3 均为 LEVEL C / HIGH；它们分别是冻结 mismatch evidence 与 pre-Test representative evaluation rigor，不得升级为算法原创贡献。

所有 headline number 的唯一正式入口是 outputs/phase12/key_number_ledger.csv。旧报告、旧 JSON 或图中即使出现相同数字，也只能作为 provenance/support，不能直接成为 Phase 13 KPI。必须同时从 ledger 取得 key_id、value、unit、scope、rounding、allowed wording 和 caveat。

### Phase 9.1 与 Phase 7/8/9

Phase 9.1 final reporting summary、metric semantics、unit semantics、data lineage、building-level bootstrap、methodology audit、prediction invariance 和 artifact hash audit 均存在。正式语义为：raw meter 是 kWh per hourly interval；dispatch 是 interval-average kW；capacity/SOC 是 kWh；decision regret 是 forecast-driven realized daily peak 减 Oracle daily peak；normalized regret 与 MAE 使用 Phase 7 Train mean load；whole-window peak reduction 是单独的最大功率指标；Oracle 是不可部署的 hindsight upper bound。

Phase 7/8/9 的 selection、weight grid、per-building metrics、daily outcomes、bootstrap 与 efficiency 数据足够支持架构、机制、不一致证据、DOEF vs LightGBM、多建筑结果、负结果和效率图。但没有保存 Phase 8 逐小时 presentation data。

## 4. Source-of-Truth Contract

outputs/phase13/source_of_truth_contract.json 按七类来源登记 path、role、canonical status、allowed/prohibited use、SHA-256 和 upstream phase：Competition rules、Claim、Number、Metric semantics、Unit semantics、Prior art、Raw figure data。所有可用 source path 均真实存在，hash 来自当前 clean checkout。

数据消费规则：只读、hash 白名单、schema 验证、fail-closed、无 fallback。GUI 可以绕开当前有缺陷的 final_algorithm loader 直接读取 contract 白名单输出，但这只是 presentation/data-consumption path，不是修复 canonical-loader defect。

## 5. 技术报告设计

报告不按 Phase 1 → Phase 12 写开发日志，而采用以下评分导向叙事：

建筑能源问题 → 24 h 建筑负荷预测 → 预测精度与储能决策价值不完全一致 → Validation regret 选择固定融合权重 → Test 只评价 → 多建筑预测/决策结果 → 模拟削峰 → 应用价值 → 负面结果、局限与未来工作。

正式 21 节结构及每节的 rubric mapping、evidence、figures、ledger key IDs、allowed/prohibited claims、importance 和 PPT suitability 已写入 outputs/phase13/report_outline.json。章节为：项目概述/摘要；AI+能源背景；相关工作；问题定义；数据集与实验设计；系统架构；DOEF；储能优化与决策评价；实验设置；预测结果；决策结果；Forecast ≠ Decision；多建筑稳健性；负面结果与停止规则；创新点；应用价值与推广潜力；局限、伦理与风险；未来工作；结论；参考文献；可选附录。

## 6. 科研视觉叙事

### 六张核心视觉

1. F01 系统总体架构与价值链：回答数据、两种基模型、Validation selector、冻结 Test、调度和 regret 如何连接；来源为 Phase 7 selection、Phase 8 weights、Phase 9 algorithm metadata 与 Phase 9.1 semantics。
2. F02 DOEF 核心机制：并排展示 MAE 选权重与 optimizer-derived regret 选权重；来源为 Phase 8 Validation weight search 和 selected weights。必须标注 Test 只评价，且 DOEF 不是新神经网络。
3. F03 Forecast ≠ Decision 三层证据：6/8 Validation weight mismatch、2/8 Test winner agreement、0.344 exact-rank agreement；headline 值通过 ledger，底层行来自 Phase 7/8。
4. F04 DOEF vs LightGBM：分面展示 normalized MAE 与 normalized decision regret，分别标注 ledger 冻结的相对改善；避免双轴混淆。
5. F05 多建筑 decision result：逐栋建筑展示 DOEF 与 LightGBM，并保留 6/2/0 ties；来源为 Phase 9 per-building metrics 和 Phase 9.1 building rows。
6. F06 储能削峰案例：计划使用 anchor building，再选择 DOEF daily regret 最接近该建筑中位数的最早日期作为 deterministic rule。该规则尚未执行；缺少冻结 hourly raw data，状态 BLOCKED，不能用更漂亮或最优日替代。

### Supporting / appendix / defense backup

- F07 296 → 82 → 8：主文或 PPT。
- F08 morphology map：附录/支持；重制需把 PCA 限定为 frozen morphology 的展示变换。
- F09 weight-search heatmap：主文 supporting、PPT/GUI 核心解释。
- F10 building-level bootstrap：附录或主文 supporting；不得换用 Phase 9 building-day CI。
- F11 negative results：主文一节、PPT/答辩 backup。
- F12 efficiency：附录/答辩 backup；仅为环境特定协议。

outputs/phase13/figure_plan.csv 还逐张审计了 Phase 7/8/9 的 20 张现有图，分类为 KEEP、REWORK、REPLACE、SUPPORTING ONLY 或 DO NOT USE。总体结论：最接近可复用主图的是 Phase 9 eight-building decision comparison，但仍需移除 rejected peak-aware headline、改名为 DOEF、加入 6/2/0 并统一视觉；Phase 8 selected weights 概念强但需重制；Phase 7 success case 与 Phase 8 representative dispatch 因 outcome-extreme 选例和无 raw rows 不能作为主文案例。

## 7. 轻量 GUI 设计

技术栈冻结为 Python + Streamlit。四个 Tab 为：项目总览、负荷预测、储能削峰、为什么预测最准 ≠ 决策最好。

T1 和 T4 的数据接口已经闭合：所有 KPI 从 key ledger 以 key_id 读取；weight curves 来自 Phase 8 Validation search；building list 来自 frozen selected_buildings。T2 和 T3 保持设计但标记 BLOCKED，不允许 aggregate metrics 或旧图 fallback 冒充 hourly data。

计划数据层接口为 load_source_contract、validate_frozen_sources、load_key_numbers、load_project_summary、load_buildings、load_forecast_timeseries、load_dispatch_timeseries、load_validation_weight_search 和 load_multibuilding_results。前五项及后两项 aggregate/Validation 接口有正式来源；两个 hourly loader 因数据缺口必须抛出 FrozenSourceMissingError，不提供空图或旧输出 fallback。

outputs/phase13/gui_spec.json 定义了 expected schema、验证顺序、错误类型、read-only roots、禁止调用的训练/预测/调度入口和 Phase 13.1 entry gate。outputs/phase13/gui_data_map.csv 为每个组件登记 source file/field、transformation、unit、rounding、frozen source、fallback_allowed=NO 和 availability。

本阶段没有创建 demo/data_loader.py。原因不是省略实现，而是两个必需 interface 当前无合法 source；创建表面可调用但只能报错的 skeleton 不增加验证价值。

## 8. 风险与阻塞项

1. OPEN HIGH lineage defect：继续记录，不修复、不改 manifest/hash，不把 presentation whitelist 描述为 loader repair。
2. 报告规则 UNKNOWN：页数、总字数、PPT 约束等继续 UNKNOWN，不能自行补值。
3. GUI data gap：无多建筑逐小时 frozen forecast，因此 Tab 2 不可实现。
4. GUI/Figure data gap：无 Phase 8 hourly dispatch/SOC，因此 Tab 3 与 F06 不可实现。
5. Unsupported claims：任何 first/new DFL/end-to-end/真实部署/节能/电费/碳排/新能源消纳/未知建筑泛化表述均禁止。
6. Static figure risk：Phase 7/8 的案例图由极端差异选例且无机器可读行，仅可作为历史/defense backup，不能作为 auditable representative main figure。

## 9. 进入下一阶段的解除条件

当前不得进入 Phase 13.1。需要单独授权一个不改变实验的展示数据冻结步骤：从已有、可证明完全一致的保存状态取得逐小时 forecast 与 dispatch rows，形成 immutable/hash-registered presentation artifacts；不能重新训练、重新生成 Test prediction、重新运行 optimizer，不能修改 Phase 7/8/9/9.1 canonical outputs。如果无法证明这些 rows 已存在于可恢复状态，则应正式缩减 GUI 为 aggregate/static scope，并重新批准 Figure 6 的证据标准。

## 10. 冻结完整性

本阶段未运行训练、调参、模型拟合、预测生成、battery dispatch、bootstrap 或实验选择入口。未修改算法源码、frozen weights、building selection、split、forecast、dispatch、Phase 7/8/9/9.1 artifact 或 Phase 12 claim/number files。只创建本阶段六个规划/contract 文件；未创建 GUI 成品、PDF、PPT 或视频。

## 11. 验证记录

- JSON：source_of_truth_contract.json、report_outline.json、gui_spec.json 均通过解析。
- CSV：figure_plan.csv 32 行、gui_data_map.csv 23 行，均通过 header/row 解析。
- Contract：42 个登记 source 全部存在且 SHA-256 与当前 checkout 匹配。
- Ledger：28 个 frozen key_id 唯一；报告 outline 和 GUI 中引用的 key_id 全部可回溯。
- Figures：6 张核心图均有明确来源记录；F06 的来源明确记录为 daily/static-only 且状态 BLOCKED，没有用假路径冒充 hourly raw source。20 张 Phase 7/8/9 现有图均完成分类。
- GUI：23 个组件映射全部 fallback_allowed=NO；AVAILABLE/PARTIAL 行的 source path 均存在；两个 hourly chart 明确 BLOCKED。
- Prohibited-claim grep：命中只出现在 prohibited/不得声称的约束语境，没有作为结果或贡献陈述。
- Frozen diff：相对起始 HEAD，src、scripts、tests、outputs/phase7、outputs/phase8、outputs/phase9、outputs/phase9_1、outputs/phase12 和 Phase 12 正式报告均无变化。
- 轻量测试：系统 Python 运行 python -m unittest tests.test_phase9_1 -v，10/10 PASS。Bundled Python 首次尝试因缺少 matplotlib 未进入测试逻辑；未安装依赖，改用仓库现有系统环境后通过。
- git diff --check：PASS。由于 HOLD 产物保持 untracked，普通 git diff --stat 为空；最终清单以 git status --short 和 untracked inventory 为准。

按用户策略，只有全部 PASS 才提交。当前 verdict 为 HOLD，因此没有 stage、commit 或 push。
