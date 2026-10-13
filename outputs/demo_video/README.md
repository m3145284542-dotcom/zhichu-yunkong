# 最终答辩演示视频

`DOEF_Demo_Narrated.mp4`：296.14 秒，1920×1080，中文 Microsoft Huihui 合成配音，同步字幕，12 页正式 PPT 与真实离线 GUI 回放。

字幕、讲解稿、时间轴及校验记录分别为 DOEF_Demo_Narrated.srt、narration.md、timeline.json、manifest.json 和 validation.json。sources/ 只保留重建所需的 12 张幻灯片、逐句音频及无损 GUI 片段，旧视频整片和重复成片已移出交付。

安装 `requirements-delivery.txt` 后，运行 `python scripts/validate_demo_video.py` 检查整片解码、音量、字幕、画面与来源散列。

使用保存的素材重建：`python scripts/build_ppt_video_20261013.py`，候选结果写入 tmp/video_candidate/；再运行 `python scripts/validate_ppt_video_20261013.py --directory tmp/video_candidate --record`。日常复核不带 --record，不改写已验收文件。更新配音可在 Windows PowerShell 执行 scripts/synthesize_ppt_video.ps1。修改内容后须同步脚本、speech_input.json、幻灯片来源和来源清单。

候选视频经人工画面/听感验收后，将成片、字幕、讲解稿、时间轴、manifest.json、validation.json 与 contact_sheet.jpg 同步到本目录，更新 manifest 中 artifact 路径及 canonical 状态，再运行报告目录的 finalize_delivery.py。直接构建不会覆盖已验收成片。GUI 展示已保存仿真实验，不是现场设备控制。
