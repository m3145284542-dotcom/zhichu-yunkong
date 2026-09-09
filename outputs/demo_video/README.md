# 智储云控配音演示视频

正式视频：`DOEF_Demo_Narrated.mp4`。包含作品功能、实现流程、真实GUI八建筑巡演、实验效果与应用边界。

中文配音为 Microsoft Xiaoxiao 神经语音合成，保持原始语速；不使用真人声音克隆。字幕已烧录到视频，也提供独立 SRT 和完整讲解稿。视频使用现有冻结数据，没有重新训练或下发设备控制命令。

核验记录：`validation.json`。来源及正式状态：`manifest.json`。画面检查：`contact_sheet.jpg`。

重新制作：安装 `edge-tts imageio-ffmpeg playwright Pillow`，运行 `python -m playwright install ffmpeg`，然后在仓库根目录运行 `python scripts/build_demo_video.py` 和 `python scripts/validate_demo_video.py`。本机制作脚本使用 Windows 微软雅黑字体和已安装的 Edge；语音合成需要网络。重新生成后状态为 candidate，须完成画面检查再验收。临时录屏及逐段音频保存在 `tmp/demo_video/`。

旧的“待补视频”参赛材料包没有被覆盖。新打包会按视频 manifest 检查正式状态与哈希，再复制MP4。
