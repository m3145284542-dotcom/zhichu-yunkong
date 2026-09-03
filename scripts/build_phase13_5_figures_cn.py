"""Render Phase 13.5 Chinese scientific figures from frozen canonical data.

This script changes labels and layout only. It does not train models, select
weights, run dispatch, or alter any Phase 7/8/9/9.1 artifact.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_5" / "figures_cn"
PNG_SIZE = (2400, 1350)

COLORS = {
    "ink": "#18212B",
    "muted": "#5C6873",
    "grid": "#D9E0E6",
    "doef": "#0072B2",
    "lightgbm": "#D55E00",
    "xgboost": "#009E73",
    "validation": "#6F4E9C",
    "warning": "#B35C00",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_style() -> str:
    candidates = ["Microsoft YaHei", "SimHei"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((name for name in candidates if name in installed), None)
    if chosen is None:
        raise RuntimeError("Microsoft YaHei and SimHei are both unavailable")
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [chosen, "Arial"],
            "axes.unicode_minus": False,
            "font.size": 16,
            "axes.titlesize": 24,
            "axes.labelsize": 17,
            "xtick.labelsize": 15,
            "ytick.labelsize": 15,
            "legend.fontsize": 15,
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "text.color": COLORS["ink"],
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.8,
            "grid.alpha": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "svg.hashsalt": "phase13_5_cn",
        }
    )
    return chosen


def save_pair(fig: plt.Figure, stem: str) -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{stem}.png"
    svg = OUT / f"{stem}.svg"
    fig.savefig(png, dpi=150, metadata={"Software": "Phase 13.5 Chinese renderer"})
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None})
    plt.close(fig)
    svg.write_text(
        "\n".join(line.rstrip() for line in buffer.getvalue().splitlines()) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return [png.relative_to(ROOT).as_posix(), svg.relative_to(ROOT).as_posix()]


def subtitle(fig: plt.Figure, text: str) -> None:
    fig.text(0.065, 0.895, text, fontsize=15, color=COLORS["muted"], ha="left", va="top")


def footer(fig: plt.Figure, text: str) -> None:
    fig.text(0.065, 0.025, text, fontsize=12.5, color=COLORS["muted"], ha="left", va="bottom")


def short_building(name: str) -> str:
    return name.replace("_office_", " · ")


def figure_mismatch() -> list[str]:
    source = ROOT / "outputs/phase9/final_benchmark.csv"
    frame = pd.read_csv(source).set_index("display_name")
    methods = ["LightGBM", "XGBoost"]
    metrics = [
        ("normalized_rmse_mean", "预测误差", "平均归一化 RMSE", "越低越好"),
        ("normalized_decision_regret_mean", "决策价值", "平均归一化决策后悔值", "越低越好"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={"wspace": 0.34})
    fig.suptitle("预测指标不能单独决定储能决策价值", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "冻结的八建筑测试集聚合结果 · 按建筑等权 · 以各建筑训练期平均负荷归一化")
    fig.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.16, wspace=0.34)
    values: dict[str, dict[str, float]] = {}
    for ax, (field, title, ylabel, direction) in zip(axes, metrics):
        vals = [float(frame.loc[m, field]) for m in methods]
        values[field] = dict(zip(methods, vals))
        x = np.arange(2)
        ax.plot(x, vals, color=COLORS["ink"], linewidth=2.3, zorder=1)
        ax.scatter(x, vals, s=260, c=[COLORS["lightgbm"], COLORS["xgboost"]], edgecolor="white", linewidth=2.2, zorder=3)
        for i, value in enumerate(vals):
            ax.annotate(f"{value:.6f}", (i, value), xytext=(0, 17), textcoords="offset points", ha="center", fontsize=16, fontweight="bold")
        ax.set_xticks(x, methods)
        ax.set_xlim(-0.45, 1.45)
        ax.set_ylim(0, max(vals) * 1.24)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{title}\n{direction}", loc="left", fontweight="bold")
        ax.grid(axis="x", visible=False)
    axes[0].annotate("XGBoost 略低", xy=(1, values[metrics[0][0]]["XGBoost"]), xytext=(-120, -85), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": COLORS["xgboost"], "lw": 2}, color=COLORS["xgboost"], fontsize=15)
    axes[1].annotate("但决策后悔值更高", xy=(1, values[metrics[1][0]]["XGBoost"]), xytext=(-145, 65), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": COLORS["warning"], "lw": 2}, color=COLORS["warning"], fontsize=15)
    footer(fig, "该结果只构成项目范围内的方向性反例；差距较小，不表示预测精度不重要。")
    return save_pair(fig, "sci_01_forecast_decision_mismatch_cn")


def figure_main_results() -> list[str]:
    source = ROOT / "outputs/phase9/final_benchmark.csv"
    frame = pd.read_csv(source).set_index("display_name")
    methods = ["LightGBM", "DOEF"]
    fields = [
        ("normalized_mae_mean", "预测层目标", "平均归一化 MAE", "降低 6.36%"),
        ("normalized_decision_regret_mean", "决策层目标", "平均归一化决策后悔值", "降低 3.61%"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={"wspace": 0.30})
    fig.suptitle("DOEF 在冻结的两层聚合指标上均有改善", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "冻结的八建筑测试集聚合结果 · 相对 LightGBM · 越低越好")
    fig.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.20, wspace=0.30)
    for ax, (field, title, ylabel, callout) in zip(axes, fields):
        vals = [float(frame.loc[m, field]) for m in methods]
        bars = ax.bar([0, 1], vals, width=0.55, color=[COLORS["lightgbm"], COLORS["doef"]], edgecolor=COLORS["ink"], linewidth=1.2, hatch=["//", ""])
        ax.set_xticks([0, 1], methods)
        ax.set_ylim(0, max(vals) * 1.30)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.grid(axis="x", visible=False)
        for bar, value in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, value + max(vals) * 0.035, f"{value:.6f}", ha="center", fontsize=16, fontweight="bold")
        ax.text(0.98, 0.92, callout, transform=ax.transAxes, ha="right", va="top", fontsize=20, color=COLORS["doef"], fontweight="bold")
    wins = int(float(frame.loc["DOEF", "decision_wins_vs_lightgbm"]))
    ties = int(float(frame.loc["DOEF", "decision_ties_vs_lightgbm"]))
    losses = int(float(frame.loc["DOEF", "decision_losses_vs_lightgbm"]))
    mean_peak = float(frame.loc["DOEF", "peak_reduction_mean_pct"])
    min_peak = float(frame.loc["DOEF", "peak_reduction_min_pct"])
    fig.text(0.5, 0.105, f"建筑级决策后悔值：{wins} 胜 · {ties} 平 · {losses} 负", ha="center", fontsize=19, fontweight="bold")
    footer(fig, f"削峰结果：平均 {mean_peak:.2f}%，最小 {min_peak:.2f}%（保留负值案例）。后悔值不表示经济损失。")
    return save_pair(fig, "sci_02_doef_main_results_cn")


def figure_multibuilding() -> list[str]:
    selected_path = ROOT / "outputs/phase7/selected_buildings.json"
    selected = json.loads(selected_path.read_text(encoding="utf-8"))["selected_buildings"]
    order = [row["building"] for row in selected]
    train = pd.read_csv(ROOT / "outputs/phase8/validation_weight_search.csv").groupby("building", sort=False)["train_mean_load"].first()
    decision = pd.read_csv(ROOT / "outputs/phase9/decision_metrics.csv")
    decision = decision[(decision["split"] == "test") & decision["method"].isin(["LightGBM", "Phase8_DOEF"])]
    pivot = decision.pivot(index="building", columns="method", values="mean_regret_vs_oracle")
    values = pd.DataFrame({"LightGBM": pivot["LightGBM"] / train, "DOEF": pivot["Phase8_DOEF"] / train}).loc[order]
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.suptitle("八栋固定建筑的决策价值比较", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "冻结测试集平均决策后悔值 · 以各建筑训练期平均负荷归一化 · 越低越好")
    fig.subplots_adjust(left=0.16, right=0.96, top=0.78, bottom=0.16)
    y = np.arange(len(values))
    for i, (_, row) in enumerate(values.iterrows()):
        ax.plot([row["LightGBM"], row["DOEF"]], [i, i], color=COLORS["grid"], linewidth=5, zorder=1)
    ax.scatter(values["LightGBM"], y, s=145, color=COLORS["lightgbm"], edgecolor="white", linewidth=1.5, marker="s", label="LightGBM", zorder=3)
    ax.scatter(values["DOEF"], y, s=175, color=COLORS["doef"], edgecolor="white", linewidth=1.5, marker="o", label="DOEF", zorder=4)
    for i, (_, row) in enumerate(values.iterrows()):
        outcome = "持平" if abs(row["DOEF"] - row["LightGBM"]) < 1e-12 else "DOEF 更低"
        ax.text(max(row) + values.to_numpy().max() * 0.025, i, outcome, va="center", fontsize=13.5, color=COLORS["muted"])
    ax.set_yticks(y, [short_building(x) for x in values.index])
    ax.invert_yaxis()
    ax.set_xlim(0, values.to_numpy().max() * 1.22)
    ax.set_xlabel("平均决策后悔值 / 训练期平均负荷")
    ax.legend(loc="lower right", frameon=False, ncol=2)
    ax.grid(axis="y", visible=False)
    ax.text(0.98, 1.025, "6 栋更低 · 2 栋持平 · 0 栋更高", transform=ax.transAxes, ha="right", fontsize=18, color=COLORS["doef"], fontweight="bold")
    footer(fig, "按冻结选择顺序展示全部八栋办公建筑。该结果表示多建筑稳健性，不表示对未见建筑的迁移能力。")
    return save_pair(fig, "sci_03_multibuilding_regret_cn")


def figure_weights() -> list[str]:
    source = ROOT / "outputs/phase8/selected_weights.csv"
    data = pd.read_csv(source)
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.suptitle("不同验证目标选择了不同融合权重", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "各建筑的 LightGBM 权重，其余权重分配给 DayWeek · 仅使用验证集选择")
    fig.subplots_adjust(left=0.16, right=0.96, top=0.78, bottom=0.16)
    y = np.arange(len(data))
    for i, row in data.iterrows():
        ax.plot([row.w_forecast, row.w_decision], [i, i], color=COLORS["grid"], linewidth=5, zorder=1)
    ax.scatter(data.w_forecast, y, s=145, color="white", edgecolor=COLORS["validation"], linewidth=2.5, marker="D", label="验证集 MAE 最小", zorder=3)
    ax.scatter(data.w_decision, y, s=175, color=COLORS["validation"], edgecolor="white", linewidth=1.5, marker="o", label="验证集决策后悔值最小（DOEF）", zorder=4)
    ax.set_yticks(y, [short_building(x) for x in data.building])
    ax.invert_yaxis()
    ax.set_xlim(-0.05, 1.05)
    ax.set_xticks(np.arange(0, 1.01, 0.2))
    ax.set_xlabel("LightGBM 融合权重 $w_b$")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="y", visible=False)
    ax.text(0.98, 1.025, "8 栋中有 6 栋的权重不同", transform=ax.transAxes, ha="right", fontsize=18, color=COLORS["validation"], fontweight="bold")
    footer(fig, "测试集不参与权重或平局规则选择。图中仅复用阶段 8 的冻结权重，未重新优化。")
    return save_pair(fig, "sci_04_validation_weight_selection_cn")


def main() -> None:
    font = configure_style()
    outputs: list[str] = []
    outputs.extend(figure_mismatch())
    outputs.extend(figure_main_results())
    outputs.extend(figure_multibuilding())
    outputs.extend(figure_weights())
    manifest = {
        "status": "PASS",
        "render_scope": "language_and_layout_only",
        "font": font,
        "formal_figure_count": 4,
        "source_artifacts": {
            path: sha256(ROOT / path)
            for path in [
                "outputs/phase9/final_benchmark.csv",
                "outputs/phase7/selected_buildings.json",
                "outputs/phase8/validation_weight_search.csv",
                "outputs/phase9/decision_metrics.csv",
                "outputs/phase8/selected_weights.csv",
            ]
        },
        "outputs": outputs,
    }
    (OUT.parent / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
