# 最终报告与答辩材料

正式入口为 [current_submission.json](../current_submission.json)。

- [技术报告 PDF](../../outputs/provincial_20261012/DOEF_Technical_Report_Submission.pdf)：17 页。
- [答辩 PPTX](../../outputs/provincial_20261012/DOEF_Provincial_Submission.pptx)及 [PDF](../../outputs/provincial_20261012/DOEF_Provincial_Submission.pdf)：12 页，无附录。
- [报告正文](technical_report.md)、[逐页讲稿](speaker_notes.md)、[成果清单](manifest.json)。

本目录只保留当前材料、维护源码和验收依据。数值来自冻结实验，未新增训练或调度实验；研究范围及负向结果保留。

验证：`python scripts/validate_final_delivery.py`。2026-10-14 报告修订增加总体架构图、明确原实验与材料复核环境，并披露历史方法路线保留曾参考测试结果。数值结果、PPT 与视频保持原版本。修订来源和验证环境见 [修订记录](report_revision.json)。

日常验证不改写交付文件；validate_alignment.py 与 validate_deck.py 使用 --record 才保存检查记录，报告增加 --render 可生成临时页面图。finalize_delivery.py 会在正式登记前保存通过的检查记录。

报告维护：修改 technical_report.md，审核并更新 report_source.json 中正文散列，再按 render_report_figures.py → build_architecture.py → build_report.py → validate_alignment.py 执行；需 XeLaTeX 及宋体、黑体等字体。PDF 改动后应重新逐页检查并更新绑定 PDF 散列的 report_visual_qa.json。

PPT 维护：build_deck.mjs 以当前 PPT 作为主题模板，生成 12 页内容；依赖 Codex bundled Node、artifact-tool 和 presentations 技能。其他机器通过 CODEX_RUNTIME_DEPENDENCIES 与 CODEX_PRESENTATIONS_SKILL 指定路径。随后在装有 PowerPoint 的 Windows 上执行 export_deck.ps1，检查导出页并更新 deck_visual_qa.json，再执行 validate_deck.py。重建在独立副本中进行。

所有内容、视觉与视频检查通过后，执行 finalize_delivery.py 更新当前清单；再重新打包。视频构建见 [视频说明](../../outputs/demo_video/README.md)。旧版父文件身份保存在溯源字段与 Git 历史，不作为当前运行输入。
