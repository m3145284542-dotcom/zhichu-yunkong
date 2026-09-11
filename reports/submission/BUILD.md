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

## 2026-09-09 作品名称统一

主标题：智储云控。副标题：基于决策导向预测融合的建筑储能削峰优化系统。当前报告、PPT、讲稿、GUI 和打包默认名使用此名称；DOEF 继续作为算法名称。视频内容已使用“智储云控”，保持不变；提交包中的视频按团队编号、赛题名称和作品名称统一命名，历史阶段和旧整理包保留原名。

## 2026-09-09 中文图与团队号收尾

团队编号为 AIC-2026-27833449。原有概念图由 `python reports/submission/render_figures_cn.py` 使用登记的中文词条复现；历史图不改。权重图复用报告中已验收的图外图例版。PPT 构建程序在候选文件内替换媒体，再执行结构、版面和导入校验。调度图使用 Phase 8 原始 PNG，曲线和坐标轴完整保留，中文标题与图例为原生文本框。新增文本及替换媒体由 figure_localization.json 校验；科研源、报告数值和备注校验继续保留。

## 2026-09-09 合规补充

主标题统一为智储云控，副标题不变。报告新增总体架构、实际 GUI 截图、历史日志支持的实验环境、模型参数和应用条件，登记在 compliance_supplements.json；原实验数值、表格、公式和参考文献继续独立校验。报告不预设固定页数，以正式 PDF 页数及 10 MB 上限检查。PPT 保留 23 页，第 12 页更新应用前景及对应讲者备注，备注登记在 presentation_supplements.json。

系统截图来自 capture_system.cjs 对离线 HTML 的真实操作，存于 assets/system_demo.png；使用已配置 RUNTIME_NODE_MODULES 的随附 Node.js 可重新截图。原始依赖与硬件信息未完整记录的部分在报告中明确说明，不用当前环境替代历史实验环境。

## 2026-09-11 应用闭环补充

报告第 1、9 节补充办公楼场景与典型流程，PPT 第 3 页以可编辑文本呈现应用闭环，第 10、12 页同步原型与试点口径。新增工程接入说明是现场设计基线，接口尚未实现。补充块、讲者备注和原型文案均单独登记；原实验数值、表格、公式、权重与科研文件保持冻结。报告段间距微调以避免附录出现少量跨页尾行。
