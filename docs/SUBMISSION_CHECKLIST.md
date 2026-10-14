# 最终参赛材料提交说明

团队编号：AIC-2026-27833449；作品名称：智储云控；AI+能源科技创新组。

| 栏目 | 当前正式文件 | 规格 |
| --- | --- | --- |
| 技术报告 | outputs/provincial_20261012/DOEF_Technical_Report_Submission.pdf | 17 页，低于 10 MB |
| 答辩 PPT | outputs/provincial_20261012/DOEF_Provincial_Submission.pdf | 12 页 PDF；同名 PPTX 为可编辑备份 |
| 演示视频 | outputs/demo_video/DOEF_Demo_Narrated.mp4 | 296.14 秒，1080p，约 11.70 MB |
| 其他材料 | 整理包中的“百度网盘材料” | 最终材料、离线 HTML、源码与实验依据、部署说明 |

要求依据为仓库保存的 [官方材料规范](competition_rules/2026-07_AI+能源竞赛规则及作品提交要求-科技创新组.pdf)。实际报名栏目及省赛截止时间以报名系统为准。

验证：`python scripts/validate_final_delivery.py`。

重新打包：`python scripts/package_competition_submission.py --team-id AIC-2026-27833449 --revision submit-ready-20261014`。包位于 outputs/competition_delivery/；当前本地入口为 reports/current_delivery.json，重复名称不会覆盖。源码 ZIP 仅收录当前公开文件与验收清单，不含旧稿、私密附件或缓存。原始大数据通过 [数据获取说明](DATASET.md) 提供。

只分享“百度网盘材料”目录，设置永久链接与提取码，再在报名系统分别上传报告、答辩 PDF、视频。报名附件中的签字承诺书含身份信息，仅供报名系统对应栏目，不进入 GitHub 或公开源码包。完整外层 ZIP 含该私密附件，仅用于本人备份。

本机签字附件源为 output/pdf/pledge-signed.pdf；公开克隆中不含该文件，打包会明确记录待补。GitHub 推送不等于网盘上传或赛事提交；这两步尚需单独完成。
