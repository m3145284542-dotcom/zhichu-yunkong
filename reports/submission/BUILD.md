# 参赛材料生成与验证

当前报告和答辩文件由本目录的 `manifest.json` 登记。报告沿用原版大纲、公式、数据表和参考文献，修改记录在 `editorial_changes.json`；PPT 在原版基础上修改文字，记录在 `presentation_changes.json`。旧阶段文件保留，可用于逐项比较。

## 检查现有文件

在仓库根目录执行，Python 需要安装 PyMuPDF：

```sh
python -m pip install PyMuPDF
python reports/submission/validate_submission.py
```

脚本检查报告与修改记录一致、所有正文数值和公式保持不变、PDF 正文完整、PPT 文字替换生效、图像及讲者备注正文保留、科研文件哈希及本地链接有效。结果写入 `qa/validation.json`。它不训练模型、不调整权重，也不运行储能实验。

## 重建报告

需要 Python、PyMuPDF、XeLaTeX，以及 SimSun、SimHei、Times New Roman、Arial 字体。在仓库根目录执行：

```sh
python reports/submission/build_pdf.py
```

程序核对 Markdown 的 LF 归一化 SHA-256，生成 LaTeX，编译三次以更新目录，再输出正式 PDF。图 1 至 3 使用原中文图，图 4 使用原报告已验收的图例位置调整版。重建会覆盖本目录的 PDF 和排版源，编译日志保留在本地。

## 重建演示文稿

需要 Codex 随附的 Node.js、`@oai/artifact-tool` 与 presentations 技能工具。将 `RUNTIME_NODE_MODULES`、`RUNTIME_PYTHON` 和 `PPT_SKILL_DIR` 设置为本机运行环境对应的绝对路径，然后用随附 Node.js 执行：

```sh
node reports/submission/build_presentation.mjs
```

生成程序从原 PPT 导入，通过检查记录定位现有文本框，逐段替换以保留字体样式，并在导出前确认所有替换确实生效。临时文件写入 `tmp/competition_style/`；文件结构和版面尺寸检查通过后更新 `outputs/submission/DOEF_Competition_Presentation.pptx`。原版数据表由可编辑文本框和形状构成，本版沿用这一结构。

Windows 上安装了 PowerPoint 时，可生成配套 PDF 与逐页预览：

```powershell
./reports/submission/export_presentation.ps1
```

脚本仅关闭它打开的演示文件。如果 PowerPoint 原先已有打开的演示文稿，会保留应用。逐页 PNG 位于 `tmp/competition_style/final_slides/`，用于检查文字换行、图表和遮挡。

重建后应重新运行验证并逐页检查导出文件，最后更新 `manifest.json` 中的文件哈希与验收状态。生成时间和软件版本可能改变 PDF/PPTX 的字节哈希，正文、数值、公式及图像的一致性由验证脚本另行核对。
