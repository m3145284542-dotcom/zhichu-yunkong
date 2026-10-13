# 最终报告与答辩索引

- [技术报告](../outputs/provincial_20261012/DOEF_Technical_Report_Submission.pdf)：16 页；[可维护正文](../reports/provincial_20261012/technical_report.md)。
- [答辩 PPTX](../outputs/provincial_20261012/DOEF_Provincial_Submission.pptx)与 [PDF](../outputs/provincial_20261012/DOEF_Provincial_Submission.pdf)：12 页，无附录。
- [逐页讲稿](../reports/provincial_20261012/speaker_notes.md)、[配音视频](../outputs/demo_video/DOEF_Demo_Narrated.mp4)、[提交说明](SUBMISSION_CHECKLIST.md)。

核心方法：在验证集上，以相同电池优化器下的实际日调度后悔值，选择逐建筑 DayWeek–LightGBM 融合权重；测试期固定权重。贡献属于应用方法改进。

| 比较基线 | DOEF 结果 | 对应内容 |
| --- | --- | --- |
| LightGBM | 归一化 MAE 降低 6.36%，归一化后悔值降低 3.61%；6 胜 2 平 | PPT 7；报告 3.3.2 |
| 逐楼 MAE 选权 | 归一化后悔值降低 12.48%；5 胜 2 平 1 负 | PPT 8；报告 3.3.4 |
| 全局决策选权 | 归一化后悔值降低 3.17% | PPT 8；报告 3.3.4 |

留一建筑汇总保持模型和权重不变，收益范围 3.41%–14.22%，不属于新增外部验证。平均整段削峰率 6.4423%，最小值 −1.0170%；日案例与整月负削峰是不同事实。跨月份、电池敏感性和现场控制尚未完成，不作为已实现成果。

当前 GUI 与视频均为离线实验回放。演示视频 296.14 秒。网盘和报名系统提交需单独完成；GitHub 推送状态以仓库提交为准。
