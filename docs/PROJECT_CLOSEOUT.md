# 项目收尾记录

日期：2026-09-09。项目进入交付维护阶段；当前报告、答辩文件、演示与验收入口见根目录 README 和 `reports/submission/manifest.json`。

## 成果与验证

- 保存团队编号及中文图表的最终修订、生成程序和验收记录。
- 重新导出便携 GUI，HTML 内容不变，修正标题调整后过期的实现哈希。135 项代码回归测试通过。
- 视频录制时的 GUI 输入从提交 `0443a73` 恢复到 `outputs/demo_video/recording_sources/`，逐项匹配录制清单中的原始哈希。视频本体不变，当前 GUI 与历史视频来源分别登记。
- 当前报告和 PPT 通过材料验证；无模型重训、参数调整或科研数据改写。
- 最终本地材料包由 `scripts/package_competition_submission.py` 从本次提交生成，包内记录来源提交和逐文件哈希。

## 清理与保留

- 临时渲染、软件缓存和旧材料包移入本地 `.local-archive/`，当前交付目录只保留重新生成的最终包。归档可恢复，不计为释放磁盘空间。
- 根目录审计日志与临时维护脚本一并转存本地 `.local-archive/`，不进入 Git 或提交源码包。批量删除被自动审批审查拒绝，因此采用归档整理。
- 承诺书、签名及原始图片保留在本地 `output/latex-pledge/`，已加入忽略规则；打包时承诺书独立放在报名附件目录。
- 原始数据、Python 环境、冻结实验、历史阶段材料和正式 QA 记录保留，以支持复现。
- 未合并审计分支 `codex/competition-project-audit` 转存本地标签 `archive/competition-project-audit-20260909`，保留其独有提交，不将未经本次验收的改动混入交付。
- 两个旧 Codex 工作树含未跟踪的 `AGENTS.md`，保留原位；已合并的 `codex/012skill` 仍由旧工作树占用。

## GitHub 与后续事项

收尾检查时远端仅有 `main`，没有打开的 PR 或 Issue；已补充仓库简介。保留已关闭 PR 和成功 CI 历史作为项目记录。新增 `submission.yml`，后续交付材料改动自动运行材料一致性检查。

仍需人工完成百度网盘分享和报名系统提交，详见 `SUBMISSION_CHECKLIST.md`。本次项目整理不代表完成网上提交。
