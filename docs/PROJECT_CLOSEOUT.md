# 最终交付审查

2026-10-13：核对最终 16 页报告、12 页 PPT、讲稿、视频、GUI 与冻结实验代码。所有关键指标按各自比较基线核对，保留负向案例和离线仿真边界。

当前仅保留一套报告/PPT/视频及其维护源码、素材、验证记录。移出旧 submission 版本、phase10–14 演示制作过程、旧视频、重复候选文件和过期续作检查点；phase3–9.1 的研究数据与源码仍是最终方法和负结果的必要复现依据。

批量删除被自动审批阻止，因此冗余文件移入 Git 忽略的 .local-archive/ 可恢复目录，不属于交付内容；GitHub 当前文件树同步移除旧稿，已有提交历史保留。

GitHub CI 统一验证 reports/current_submission.json 指定的最终材料，并运行视频校验和代码回归。机器检查不自动声称完成视觉审查；视觉记录绑定实际检查过的 PDF 散列。

本机含原始数据时 130 项回归测试全部通过；独立公开副本为 129 项通过、1 项因未附原始大数据而跳过。Git 明确保留冻结文件的已登记换行格式，避免跨平台克隆破坏严格字节哈希；6 个混合换行旧记录原样存储，未改变其内容。旧阶段训练 CI 已移除，只保留最终交付验证流程。

复核入口：`python scripts/validate_final_delivery.py`、`python scripts/validate_demo_video.py`、`python -m unittest discover -s tests -v`。详细结果见 reports/final_consistency_audit.json。完整模型训练和调度流水线本轮未重跑。

报名签字附件及完整本地整理包不上传 GitHub。网盘分享与赛事报名系统提交仍需单独完成。
