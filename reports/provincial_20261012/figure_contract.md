# 技术报告数据图约定

使用 Python/Matplotlib 读取冻结 CSV，输出可缩放 PDF、SVG 和 PNG 预览；不进行训练或调度实验。每幅图为单坐标轴，无多面板对齐需求。成图宽 154 mm，高 82–92 mm；字体 10 pt，白底，无展示卡片、标题口号或截图。

1. mismatch：LightGBM 与 XGBoost 的归一化 RMSE、决策后悔值分组柱图。八建筑等权均值，说明两指标排序不完全相同；从零起轴，显示六位小数，保留差距很小的事实。
2. weights：全部八建筑的验证集 MAE 与后悔值选权配对点图。权重为 LightGBM 占比，全部固定值，无误差线。
3. main_results：LightGBM 与 DOEF 的归一化 MAE、后悔值分组柱图。八建筑等权均值；本图仅作描述，已有建筑级 bootstrap 区间在正文报告，不将建筑均值视为多次训练。
4. buildings：全部八建筑的归一化后悔值配对点图；每点为 30 日后悔值均值除以该建筑训练期平均负荷。保留全部八建筑、固定顺序及持平值。

来源：outputs/phase9/final_benchmark.csv、outputs/phase8/selected_weights.csv、outputs/phase9_1/building_level_bootstrap.csv。源文件哈希和实际绘图数据另存 figures/source_manifest.json 及 CSV。无新增显著性检验、平滑、插值或样本筛选。无需新增 p 值或误差线。

总体架构为单独的流程示意图，由 build_architecture.py 生成 figures/architecture.pdf，说明训练、验证、冻结留出评价和只读展示关系，不产生实验数据。报告图号依次为 mismatch（图1）、architecture（图2）、weights（图3）、main_results（图4）、buildings（图5）。四张数据图的科学输入保持不变。
