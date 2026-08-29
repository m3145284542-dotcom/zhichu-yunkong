# 智储云控

这是“基于人工智能负荷预测与优化调度的园区智能能源管理系统”的本科生竞赛项目仓库。当前已完成第二阶段数据接入与审计，以及第三阶段单建筑、24 小时超前负荷预测 baseline。

当前没有实现储能优化、强化学习、Web API 或前端。

## 环境

- Windows / Linux / macOS
- Python 3.11 或更高版本
- 当前最小依赖：pandas、numpy、matplotlib

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

在 PyCharm 中，可将项目解释器设为 `.venv\Scripts\python.exe`。若 `python` 命令未指向正常的 Python 3.11+，先在 PyCharm 中选择已安装解释器，再创建虚拟环境。

## 准备官方数据

只下载项目需要的三个 BDG2 官方文件：

```powershell
python scripts\download_bdg2.py
```

目标位置：

- `data/raw/metadata.csv`
- `data/raw/weather.csv`
- `data/raw/electricity_cleaned.csv`

大文件由 Git LFS 托管。如果脚本的一次下载失败，它会停止并打印三个官方文件页面，不会循环重试。可从页面手工下载并按上述文件名放入 `data/raw/`，然后直接继续。数据说明、论文、单位和署名要求见 `docs/DATASET.md`。

## 运行审计与预处理

```powershell
python scripts\run_data_pipeline.py
python scripts\validate_processed.py
python -m unittest discover -s tests -v
```

脚本会根据真实 metadata 自动识别 Education 建筑，对候选 site 的负荷完整性、共同覆盖、零值/负值和天气覆盖进行排名。园区聚合只在所选建筑全部有读数的小时求和；任何缺失都不会当作 0，也不执行插值。

## 输出

- `reports/data_audit.md`：三个源文件的实际数据审计
- `reports/site_selection.md`：教育类 site 排名、建筑明细与自动推荐
- `reports/processed_validation.md`：连续性、负荷异常标记、天气缺失和数据泄漏检查
- `data/processed/campus_hourly.csv`：负荷与站点天气的小时级精确时间对齐结果
- `data/processed/campus_hourly_manifest.json`：源文件哈希、建筑集合、单位和处理策略
- `reports/figures/`：五张基础数据理解图

`data/raw/` 中的大型数据被 `.gitignore` 忽略；下载脚本、文档、报告、小型处理结果和必要图表可纳入版本控制。所有项目路径均由 `pathlib` 相对项目根目录解析。

## 运行第三阶段 baseline

```powershell
python src\train_baseline.py
```

该入口校验原始电力 CSV 的 SHA-256，分块筛选一栋建筑，按 feature timestamp 固定切分 train / validation / test，训练两个朴素基线与 CPU LightGBM，并将指标、预测和图表写入 `outputs/phase3/`。原始 CSV 只读且不会被修改。
