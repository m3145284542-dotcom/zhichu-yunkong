"""Build Phase 13.1 presentation-ready visuals from frozen evidence only.

This module is a renderer, not an experiment runner. It fails closed when any
declared source differs from the LF-normalized inventory hash.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "phase13_1"
INVENTORY_PATH = OUT / "manifests" / "visual_asset_inventory.json"
MANIFEST_PATH = OUT / "manifests" / "visual_asset_manifest.json"
STYLE_PATH = OUT / "manifests" / "visual_style_guide.json"
PNG_SIZE = (2400, 1350)
SCRIPT_VERSION = "1.0.0"

COLORS = {
    "ink": "#18212B",
    "muted": "#5C6873",
    "grid": "#D9E0E6",
    "panel": "#F4F7F9",
    "doef": "#0072B2",
    "lightgbm": "#D55E00",
    "xgboost": "#009E73",
    "dayweek": "#CC79A7",
    "persistence": "#7A7A7A",
    "load": "#202020",
    "grid_load": "#0072B2",
    "charge": "#56B4E9",
    "discharge": "#E69F00",
    "validation": "#6F4E9C",
    "test": "#67727C",
    "positive": "#0072B2",
    "warning": "#B35C00",
}


def lf_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".txt", ".md", ".py", ".yml", ".yaml", ".toml"}:
        return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hash(rel: str) -> str:
    return sha256_bytes(lf_bytes(ROOT / rel))


def json_load(rel: str | Path) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
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
            "svg.hashsalt": "phase13_1",
        }
    )


def save_pair(fig: plt.Figure, directory: str, stem: str, transparent: bool = False) -> list[str]:
    target = OUT / directory
    target.mkdir(parents=True, exist_ok=True)
    png = target / f"{stem}.png"
    svg = target / f"{stem}.svg"
    fig.savefig(
        png,
        dpi=150,
        bbox_inches=None,
        transparent=transparent,
        metadata={"Software": f"Phase 13.1 renderer {SCRIPT_VERSION}"},
    )
    svg_buffer = io.StringIO()
    fig.savefig(svg_buffer, format="svg", bbox_inches=None, transparent=transparent, metadata={"Date": None})
    plt.close(fig)
    # Matplotlib emits harmless trailing spaces in multiline SVG path data.
    # Strip them deterministically so generated artifacts pass repository diff checks.
    svg_text = svg_buffer.getvalue()
    svg.write_text("\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n", encoding="utf-8", newline="\n")
    return [png.relative_to(ROOT).as_posix(), svg.relative_to(ROOT).as_posix()]


def subtitle(fig: plt.Figure, text: str) -> None:
    fig.text(0.065, 0.895, text, fontsize=15, color=COLORS["muted"], ha="left", va="top")


def footer(fig: plt.Figure, text: str) -> None:
    fig.text(0.065, 0.025, text, fontsize=12.5, color=COLORS["muted"], ha="left", va="bottom")


def values_checksum(rows: Any) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256_bytes(payload.encode("utf-8"))


def fig_mismatch() -> tuple[list[str], str]:
    frame = pd.read_csv(ROOT / "outputs/phase9/final_benchmark.csv").set_index("display_name")
    methods = ["LightGBM", "XGBoost"]
    metrics = [
        ("normalized_rmse_mean", "Forecast error", "Mean normalized RMSE", "Lower is better"),
        ("normalized_decision_regret_mean", "Decision value", "Mean normalized decision regret", "Lower is better"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={"wspace": 0.34})
    fig.suptitle("Forecast metrics alone do not determine decision value", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "Frozen eight-building Test aggregate · equal-building mean after Train-mean normalization")
    fig.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.16, wspace=0.34)
    plotted: dict[str, dict[str, float]] = {}
    for ax, (field, panel_title, ylabel, direction) in zip(axes, metrics):
        vals = [float(frame.loc[m, field]) for m in methods]
        plotted[field] = dict(zip(methods, vals))
        x = np.arange(2)
        ax.plot(x, vals, color=COLORS["ink"], linewidth=2.3, zorder=1)
        ax.scatter(x, vals, s=260, c=[COLORS["lightgbm"], COLORS["xgboost"]], edgecolor="white", linewidth=2.2, zorder=3)
        for i, (m, v) in enumerate(zip(methods, vals)):
            ax.annotate(f"{v:.6f}", (i, v), xytext=(0, 17), textcoords="offset points", ha="center", fontsize=16, fontweight="bold")
        ax.set_xticks(x, methods)
        ax.set_xlim(-0.45, 1.45)
        ax.set_ylim(0, max(vals) * 1.24)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{panel_title}\n{direction}", loc="left", fontweight="bold")
        ax.grid(axis="x", visible=False)
    axes[0].annotate("XGBoost is slightly lower", xy=(1, plotted[metrics[0][0]]["XGBoost"]), xytext=(-150, -85), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": COLORS["xgboost"], "lw": 2}, color=COLORS["xgboost"], fontsize=15)
    axes[1].annotate("…but regret is higher", xy=(1, plotted[metrics[1][0]]["XGBoost"]), xytext=(-145, 65), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": COLORS["warning"], "lw": 2}, color=COLORS["warning"], fontsize=15)
    footer(fig, "Directional counterexample only: the gap is small and project-scoped; it does not imply that forecast accuracy is unimportant.")
    return save_pair(fig, "figures", "sci_01_forecast_decision_mismatch"), values_checksum(plotted)


def fig_main_results() -> tuple[list[str], str]:
    frame = pd.read_csv(ROOT / "outputs/phase9/final_benchmark.csv").set_index("display_name")
    methods = ["LightGBM", "DOEF"]
    fields = [
        ("normalized_mae_mean", "Forecast objective", "Mean normalized MAE", "6.36% lower"),
        ("normalized_decision_regret_mean", "Decision objective", "Mean normalized regret", "3.61% lower"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={"wspace": 0.30})
    fig.suptitle("DOEF improves both frozen aggregate objectives", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "Frozen eight-building Test aggregate · comparison against LightGBM · lower is better")
    fig.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.20, wspace=0.30)
    plotted: dict[str, Any] = {}
    for ax, (field, title, ylabel, callout) in zip(axes, fields):
        vals = [float(frame.loc[m, field]) for m in methods]
        plotted[field] = dict(zip(methods, vals))
        bars = ax.bar([0, 1], vals, width=0.55, color=[COLORS["lightgbm"], COLORS["doef"]], edgecolor=COLORS["ink"], linewidth=1.2, hatch=["//", ""])
        ax.set_xticks([0, 1], methods)
        ax.set_ylim(0, max(vals) * 1.30)
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.grid(axis="x", visible=False)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.035, f"{v:.6f}", ha="center", fontsize=16, fontweight="bold")
        ax.text(0.98, 0.92, callout, transform=ax.transAxes, ha="right", va="top", fontsize=20, color=COLORS["doef"], fontweight="bold")
    wins = int(float(frame.loc["DOEF", "decision_wins_vs_lightgbm"]))
    ties = int(float(frame.loc["DOEF", "decision_ties_vs_lightgbm"]))
    losses = int(float(frame.loc["DOEF", "decision_losses_vs_lightgbm"]))
    mean_peak = float(frame.loc["DOEF", "peak_reduction_mean_pct"])
    min_peak = float(frame.loc["DOEF", "peak_reduction_min_pct"])
    plotted["decision_wtl"] = [wins, ties, losses]
    plotted["peak_reduction_mean_min_pct"] = [mean_peak, min_peak]
    fig.text(0.5, 0.105, f"Building-level decision regret:  {wins} wins  ·  {ties} ties  ·  {losses} losses", ha="center", fontsize=19, fontweight="bold", color=COLORS["ink"])
    footer(fig, f"Peak-shaving context: mean {mean_peak:.2f}%; minimum {min_peak:.2f}% (negative case retained). Oracle-relative regret is not monetary regret.")
    return save_pair(fig, "figures", "sci_02_doef_main_results"), values_checksum(plotted)


def short_building(name: str) -> str:
    return name.replace("_office_", " · ")


def fig_multibuilding() -> tuple[list[str], str]:
    selected = json_load("outputs/phase7/selected_buildings.json")["selected_buildings"]
    order = [row["building"] for row in selected]
    train = pd.read_csv(ROOT / "outputs/phase8/validation_weight_search.csv").groupby("building", sort=False)["train_mean_load"].first()
    decision = pd.read_csv(ROOT / "outputs/phase9/decision_metrics.csv")
    decision = decision[(decision["split"] == "test") & decision["method"].isin(["LightGBM", "Phase8_DOEF"])]
    pivot = decision.pivot(index="building", columns="method", values="mean_regret_vs_oracle")
    values = pd.DataFrame({"LightGBM": pivot["LightGBM"] / train, "DOEF": pivot["Phase8_DOEF"] / train}).loc[order]
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.suptitle("Decision value across all eight fixed buildings", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "Frozen Test mean decision regret normalized by each building's frozen Train mean load · lower is better")
    fig.subplots_adjust(left=0.16, right=0.96, top=0.78, bottom=0.16)
    y = np.arange(len(values))
    for i, (_, row) in enumerate(values.iterrows()):
        ax.plot([row["LightGBM"], row["DOEF"]], [i, i], color=COLORS["grid"], linewidth=5, zorder=1)
    ax.scatter(values["LightGBM"], y, s=145, color=COLORS["lightgbm"], edgecolor="white", linewidth=1.5, marker="s", label="LightGBM", zorder=3)
    ax.scatter(values["DOEF"], y, s=175, color=COLORS["doef"], edgecolor="white", linewidth=1.5, marker="o", label="DOEF", zorder=4)
    for i, (_, row) in enumerate(values.iterrows()):
        outcome = "tie" if abs(row["DOEF"] - row["LightGBM"]) < 1e-12 else "DOEF lower"
        ax.text(max(row) + values.to_numpy().max() * 0.025, i, outcome, va="center", fontsize=13.5, color=COLORS["muted"])
    ax.set_yticks(y, [short_building(x) for x in values.index])
    ax.invert_yaxis()
    ax.set_xlim(0, values.to_numpy().max() * 1.22)
    ax.set_xlabel("Mean decision regret / Train mean load")
    ax.legend(loc="lower right", frameon=False, ncol=2)
    ax.grid(axis="y", visible=False)
    ax.text(0.98, 1.025, "6 lower · 2 ties · 0 higher", transform=ax.transAxes, ha="right", fontsize=18, color=COLORS["doef"], fontweight="bold")
    footer(fig, "All eight preselected offices are shown in frozen selection order. This is multi-building robustness, not unseen-building transfer.")
    rows = [{"building": b, "LightGBM": float(values.loc[b, "LightGBM"]), "DOEF": float(values.loc[b, "DOEF"])} for b in order]
    return save_pair(fig, "figures", "sci_03_multibuilding_regret"), values_checksum(rows)


def fig_weights() -> tuple[list[str], str]:
    data = pd.read_csv(ROOT / "outputs/phase8/selected_weights.csv")
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.suptitle("Validation objectives select different ensemble weights", x=0.065, y=0.975, ha="left", fontweight="bold", fontsize=27)
    subtitle(fig, "Per-building LightGBM weight; remaining weight is DayWeek · selection uses Validation only")
    fig.subplots_adjust(left=0.16, right=0.96, top=0.78, bottom=0.16)
    y = np.arange(len(data))
    for i, row in data.iterrows():
        ax.plot([row.w_forecast, row.w_decision], [i, i], color=COLORS["grid"], linewidth=5, zorder=1)
    ax.scatter(data.w_forecast, y, s=145, color="white", edgecolor=COLORS["validation"], linewidth=2.5, marker="D", label="Min Validation MAE", zorder=3)
    ax.scatter(data.w_decision, y, s=175, color=COLORS["validation"], edgecolor="white", linewidth=1.5, marker="o", label="Min Validation regret (DOEF)", zorder=4)
    ax.set_yticks(y, [short_building(x) for x in data.building])
    ax.invert_yaxis()
    ax.set_xlim(-0.05, 1.05)
    ax.set_xticks(np.arange(0, 1.01, 0.2))
    ax.set_xlabel("LightGBM ensemble weight $w_b$")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="y", visible=False)
    ax.text(0.98, 1.025, "Different for 6 of 8 buildings", transform=ax.transAxes, ha="right", fontsize=18, color=COLORS["validation"], fontweight="bold")
    footer(fig, "Test is excluded from weight and tie-break selection. Points show frozen Phase 8 weights; no optimization was rerun.")
    rows = data[["building", "w_forecast", "w_decision", "weights_differ"]].to_dict(orient="records")
    return save_pair(fig, "figures", "sci_04_validation_weight_selection"), values_checksum(rows)


def fig_dispatch_reuse() -> tuple[list[str], str]:
    source = ROOT / "outputs/phase8/figures/06_representative_dispatch.png"
    image = plt.imread(source)
    fig = plt.figure(figsize=(16, 9))
    fig.suptitle("Frozen representative forecast-to-dispatch trace", x=0.045, y=0.975, ha="left", fontweight="bold", fontsize=27)
    fig.text(0.045, 0.895, "Phase 8 pre-frozen Test case · unchanged raster evidence · presentation frame only", fontsize=15, color=COLORS["muted"], ha="left")
    ax = fig.add_axes([0.035, 0.13, 0.93, 0.71])
    ax.imshow(image)
    ax.axis("off")
    fig.text(0.045, 0.055, "Read as a mechanism trace, not a universal performance claim. The representative case was frozen upstream; no values were extracted and no case was reselected.", fontsize=13.5, color=COLORS["muted"], ha="left")
    return save_pair(fig, "figures", "sci_05_storage_dispatch_frozen"), sha256_bytes(source.read_bytes())


def box(ax: plt.Axes, xy: tuple[float, float], wh: tuple[float, float], title: str, body: str, color: str, lw: float = 1.8) -> None:
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018", fc="white", ec=color, lw=lw)
    ax.add_patch(patch)
    title_lines = title.count("\n") + 1
    ax.text(x + 0.018, y + h - 0.027, title, fontsize=13.5, fontweight="bold", color=color, va="top", linespacing=1.05)
    ax.text(x + 0.018, y + h - 0.073 - 0.030 * (title_lines - 1), body, fontsize=10.6, color=COLORS["ink"], va="top", linespacing=1.18)


def arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str = COLORS["ink"], style: str = "-", rad: float = 0.0) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14, lw=1.8, color=color, linestyle=style, connectionstyle=f"arc3,rad={rad}"))


def architecture() -> tuple[list[str], str]:
    spec = json_load("outputs/phase13_0b/doef_pipeline_spec.json")
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.suptitle("DOEF v1.0 — frozen causal architecture", x=0.045, y=0.975, ha="left", fontweight="bold", fontsize=27)
    fig.text(0.045, 0.895, "Prediction serves the storage decision · Validation selects · Test evaluates only", fontsize=16, color=COLORS["muted"], ha="left")

    # Split lanes
    lanes = [(0.66, "TRAIN", "Fit component model", COLORS["doef"]), (0.39, "VALIDATION", "Select and freeze $w_b$", COLORS["validation"]), (0.12, "TEST", "Final reporting only", COLORS["test"])]
    for y, label, role, color in lanes:
        ax.add_patch(FancyBboxPatch((0.035, y), 0.93, 0.20, boxstyle="round,pad=0.008,rounding_size=0.012", fc=COLORS["panel"], ec="none"))
        ax.text(0.05, y + 0.17, label, fontsize=13, fontweight="bold", color=color)
        ax.text(0.05, y + 0.135, role, fontsize=10.5, color=COLORS["muted"])

    box(ax, (0.16, 0.69), (0.17, 0.13), "Frozen hourly load", "8 fixed offices\npredefined time windows", COLORS["doef"])
    box(ax, (0.38, 0.69), (0.18, 0.13), "Causal features", "positive lags + shifted history\n24 h target horizon · no weather", COLORS["doef"])
    box(ax, (0.61, 0.69), (0.16, 0.13), "LightGBM", "per-building fit\nfrozen configuration", COLORS["lightgbm"])
    box(ax, (0.80, 0.69), (0.14, 0.13), "DayWeek", "0.5 y(t−24)\n+ 0.5 y(t−168)", COLORS["dayweek"])
    arrow(ax, (0.33, 0.755), (0.38, 0.755))
    arrow(ax, (0.56, 0.755), (0.61, 0.755))
    arrow(ax, (0.29, 0.82), (0.84, 0.82), COLORS["dayweek"], rad=-0.18)

    box(ax, (0.16, 0.405), (0.17, 0.155), "Validation window", "component forecasts\nrealized validation load", COLORS["validation"])
    box(ax, (0.38, 0.405), (0.19, 0.155), "Frozen battery\noptimizer", "same constraints\n+ daily reset", COLORS["validation"])
    box(ax, (0.62, 0.405), (0.20, 0.155), "Decision-oriented\nselection", "min mean daily regret\nvs non-deployable Oracle", COLORS["validation"])
    box(ax, (0.85, 0.405), (0.10, 0.155), "FREEZE", "$w_b$ per\nbuilding", COLORS["validation"], lw=2.6)
    arrow(ax, (0.33, 0.4825), (0.38, 0.4825), COLORS["validation"])
    arrow(ax, (0.57, 0.4825), (0.62, 0.4825), COLORS["validation"])
    arrow(ax, (0.82, 0.4825), (0.85, 0.4825), COLORS["validation"])
    arrow(ax, (0.69, 0.69), (0.51, 0.56), COLORS["validation"], "--")
    arrow(ax, (0.87, 0.69), (0.53, 0.56), COLORS["validation"], "--")

    box(ax, (0.16, 0.15), (0.15, 0.13), "Test inputs", "past-known load +\ncalendar state", COLORS["test"])
    box(ax, (0.35, 0.15), (0.18, 0.13), "DOEF forecast", "$w_b$ LightGBM +\n(1−$w_b$) DayWeek", COLORS["doef"], lw=2.6)
    box(ax, (0.57, 0.15), (0.17, 0.13), "Battery schedule", "24 h charge/discharge\nfrom frozen optimizer", COLORS["doef"])
    box(ax, (0.78, 0.15), (0.17, 0.13), "Final evaluation", "MAE / RMSE / MAPE\npeak + Oracle regret", COLORS["test"], lw=2.2)
    arrow(ax, (0.31, 0.215), (0.35, 0.215), COLORS["test"])
    arrow(ax, (0.53, 0.215), (0.57, 0.215), COLORS["doef"])
    arrow(ax, (0.74, 0.215), (0.78, 0.215), COLORS["doef"])
    arrow(ax, (0.90, 0.405), (0.47, 0.28), COLORS["validation"])
    ax.text(0.67, 0.31, "frozen weight transfer", fontsize=10.5, color=COLORS["validation"], rotation=-13)
    arrow(ax, (0.44, 0.15), (0.86, 0.15), COLORS["test"], "--", rad=0.22)
    ax.text(0.65, 0.115, "direct forecast-metric path", fontsize=9.8, color=COLORS["test"], ha="center")
    ax.text(0.79, 0.045, "NO Test feedback to training, features, weights, or selection", fontsize=12, color=COLORS["warning"], ha="center", fontweight="bold")
    fig.text(0.045, 0.025, "ALGORITHM FROZEN · deterministic ensemble and constrained optimization · not joint training, bilevel optimization, online learning, or a deployable Oracle.", fontsize=12.5, color=COLORS["muted"], ha="left")
    modules = [{k: m.get(k) for k in ("module_id", "name", "selection_criterion", "frozen_parameter")} for m in spec["modules"]]
    outputs = save_pair(fig, "architecture", "doef_architecture_master")

    # Transparent PNG is an explicit additional deliverable; SVG is already vector.
    svg = ROOT / outputs[1]
    transparent = OUT / "architecture" / "doef_architecture_master_transparent.png"
    # Re-rendering a transparent variant is deterministic and uses the same artists before closure only,
    # so create it from the opaque PNG with exact-white alpha removal.
    rgba = Image.open(ROOT / outputs[0]).convert("RGBA")
    arr = np.array(rgba)
    white = np.all(arr[:, :, :3] >= 250, axis=2)
    arr[white, 3] = 0
    Image.fromarray(arr).save(transparent)
    outputs.append(transparent.relative_to(ROOT).as_posix())
    return outputs, values_checksum(modules)


def conceptual_bridge() -> tuple[list[str], str]:
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.suptitle("Prediction is an input to the decision — not the endpoint", x=0.055, y=0.95, ha="left", fontweight="bold", fontsize=27)
    items = [
        (0.07, "24 h load forecast", "error timing + shape", COLORS["lightgbm"]),
        (0.30, "Battery optimization", "charge / discharge schedule", COLORS["validation"]),
        (0.54, "Realized grid load", "actual load + battery action", COLORS["doef"]),
        (0.77, "Decision outcome", "post-storage peak + regret", COLORS["ink"]),
    ]
    for x, title, body, color in items:
        box(ax, (x, 0.39), (0.17, 0.20), title, body, color, 2.3)
    for x in [0.24, 0.47, 0.71]:
        arrow(ax, (x, 0.49), (x + 0.05, 0.49), COLORS["ink"])
    ax.text(0.5, 0.70, "The same scalar forecast score can hide different errors at decision-critical hours", ha="center", fontsize=19, color=COLORS["muted"])
    ax.text(0.5, 0.25, "Evaluate both forecast quality and downstream storage value", ha="center", fontsize=23, color=COLORS["doef"], fontweight="bold")
    fig.text(0.055, 0.05, "CONCEPTUAL / EXPLANATORY · no experimental values encoded · no cost, carbon, or energy-savings claim", fontsize=13, color=COLORS["muted"])
    return save_pair(fig, "presentation_assets", "con_01_prediction_decision_bridge"), values_checksum([x[1] for x in items])


def conceptual_contributions() -> tuple[list[str], str]:
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.suptitle("Four verified contribution pillars", x=0.055, y=0.95, ha="left", fontweight="bold", fontsize=27)
    pillars = [
        (0.07, 0.53, "01  Causal forecasting", "24 h horizon\npositive lags + shifted history\nno future-target leakage", COLORS["lightgbm"]),
        (0.53, 0.53, "02  Decision-oriented ensemble", "Validation regret selects $w_b$\nLightGBM + DayWeek\nTest excluded from selection", COLORS["validation"]),
        (0.07, 0.20, "03  Multi-building robustness", "8 fixed heterogeneous offices\nTrain-only morphology sampling\nnot unseen-building transfer", COLORS["xgboost"]),
        (0.53, 0.20, "04  Storage decision evaluation", "same constrained optimizer\nrealized peaks + Oracle regret\nalongside forecast metrics", COLORS["doef"]),
    ]
    for x, y, title, body, color in pillars:
        box(ax, (x, y), (0.40, 0.23), title, body, color, 2.2)
    fig.text(0.055, 0.055, "CONCEPTUAL / EXPLANATORY · contribution is project-scoped; no first / SOTA / end-to-end claim", fontsize=13, color=COLORS["muted"])
    return save_pair(fig, "presentation_assets", "con_02_contribution_overview"), values_checksum([p[2] for p in pillars])


def style_guide() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "Phase 13.1 scientific presentation visual system",
        "font_family": "DejaVu Sans (cross-platform)",
        "canvas": {"aspect_ratio": "16:9", "png_pixels": list(PNG_SIZE), "figure_inches": [16, 9], "dpi": 150},
        "minimum_core_text_pt_at_asset_scale": 12,
        "palette": COLORS,
        "identity": {
            "DOEF": {"color": COLORS["doef"], "marker": "circle", "line": "solid"},
            "LightGBM": {"color": COLORS["lightgbm"], "marker": "square", "line": "solid", "hatch": "//"},
            "XGBoost": {"color": COLORS["xgboost"], "marker": "circle", "line": "solid"},
            "DayWeek": {"color": COLORS["dayweek"], "marker": "diamond", "line": "dashed"},
            "Persistence": {"color": COLORS["persistence"], "marker": "triangle", "line": "dotted"},
            "original_load": {"color": COLORS["load"], "line": "solid"},
            "post_storage_grid_load": {"color": COLORS["grid_load"], "line": "solid"},
            "charge": {"color": COLORS["charge"], "fill": "positive"},
            "discharge": {"color": COLORS["discharge"], "fill": "negative"},
        },
        "rules": [
            "Never use jet/rainbow, 3D, dual axes, or color as the sole category channel.",
            "Use zero baselines for bar charts and independent axes for incompatible metrics.",
            "State split, aggregation, direction, normalization, and material caveats on-figure.",
            "Conceptual assets must be explicitly labeled and must not encode experimental values.",
        ],
    }


def write_preview(manifest_assets: list[dict[str, Any]]) -> list[str]:
    preview_dir = OUT / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    thumbs: list[tuple[dict[str, Any], Image.Image]] = []
    for asset in manifest_assets:
        png = next((ROOT / p for p in asset["output_files"] if p.endswith(".png") and not p.endswith("transparent.png")), None)
        if png:
            im = Image.open(png).convert("RGB")
            im.thumbnail((620, 350), Image.Resampling.LANCZOS)
            thumbs.append((asset, im.copy()))
    width = 1600
    row_h = 420
    sheet = Image.new("RGB", (width, 90 + row_h * len(thumbs)), "white")
    draw = ImageDraw.Draw(sheet)
    font_path = Path(mpl.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
    bold_path = Path(mpl.get_data_path()) / "fonts" / "ttf" / "DejaVuSans-Bold.ttf"
    title_font = ImageFont.truetype(str(bold_path), 30)
    label_font = ImageFont.truetype(str(bold_path), 22)
    body_font = ImageFont.truetype(str(font_path), 17)
    draw.text((40, 25), "Phase 13.1 core assets preview — review aid, not a slide deck", fill=COLORS["ink"], font=title_font)
    for i, (asset, im) in enumerate(thumbs):
        y = 90 + i * row_h
        sheet.paste(im, (40, y + 25))
        x = 710
        draw.text((x, y + 35), asset["asset_id"], fill=COLORS["doef"], font=label_font)
        draw.text((x, y + 78), asset["title"], fill=COLORS["ink"], font=label_font)
        label = asset["scientific_or_conceptual"]
        draw.text((x, y + 125), label, fill=COLORS["muted"], font=body_font)
        message = asset["intended_message"]
        words = message.split()
        lines, current = [], []
        for word in words:
            if len(" ".join(current + [word])) > 70:
                lines.append(" ".join(current)); current = [word]
            else:
                current.append(word)
        if current: lines.append(" ".join(current))
        draw.multiline_text((x, y + 165), "\n".join(lines[:5]), fill=COLORS["ink"], font=body_font, spacing=7)
        draw.line((40, y + row_h - 2, width - 40, y + row_h - 2), fill=COLORS["grid"], width=2)
    png_path = preview_dir / "phase13_1_core_assets_preview.png"
    sheet.save(png_path)

    cards = []
    for asset, _ in thumbs:
        png = next(p for p in asset["output_files"] if p.endswith(".png") and not p.endswith("transparent.png"))
        rel = Path(png).relative_to("outputs/phase13_1").as_posix()
        cards.append(f'<article><img src="../{rel}" alt="{asset["asset_id"]}"><div><strong>{asset["asset_id"]}</strong><h2>{asset["title"]}</h2><p class="tag">{asset["scientific_or_conceptual"]}</p><p>{asset["intended_message"]}</p></div></article>')
    html = """<!doctype html><meta charset="utf-8"><title>Phase 13.1 core assets preview</title>
<style>body{font:16px Arial,sans-serif;color:#18212B;max-width:1500px;margin:28px auto}h1{font-size:30px}article{display:grid;grid-template-columns:46% 1fr;gap:28px;padding:24px 0;border-top:1px solid #D9E0E6}img{width:100%;border:1px solid #D9E0E6}.tag{color:#5C6873;letter-spacing:.04em}strong{color:#0072B2}</style>
<h1>Phase 13.1 core assets preview</h1><p>Review aid only — not a presentation deck.</p>""" + "".join(cards)
    html_path = preview_dir / "phase13_1_core_assets_preview.html"
    html_path.write_text(html, encoding="utf-8", newline="\n")
    return [png_path.relative_to(ROOT).as_posix(), html_path.relative_to(ROOT).as_posix()]


def main() -> None:
    configure_style()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    for item in inventory["assets"]:
        for rel, expected in item["source_hashes"].items():
            actual = source_hash(rel)
            if actual != expected:
                raise RuntimeError(f"Frozen source drift for {rel}: expected {expected}, got {actual}")

    builders = {
        "SCI-01-forecast-decision-mismatch": fig_mismatch,
        "SCI-02-doef-main-results": fig_main_results,
        "SCI-03-multibuilding-regret": fig_multibuilding,
        "SCI-04-validation-weight-selection": fig_weights,
        "SCI-05-storage-dispatch-frozen": fig_dispatch_reuse,
        "ARCH-01-doef-architecture-master": architecture,
        "CON-01-prediction-decision-bridge": conceptual_bridge,
        "CON-02-contribution-overview": conceptual_contributions,
    }
    caveats = {
        "SCI-01-forecast-decision-mismatch": "The directional gap is small and project-scoped; forecast accuracy remains necessary but is insufficient alone.",
        "SCI-02-doef-main-results": "Eight fixed offices and one fixed future Test month per building; Oracle-relative regret is not monetary regret.",
        "SCI-03-multibuilding-regret": "Multi-building robustness only, not unseen-building transfer; equal-building reporting scope.",
        "SCI-04-validation-weight-selection": "Weights are Validation-selected; differing weights do not by themselves prove universal downstream superiority.",
        "SCI-05-storage-dispatch-frozen": "Pre-frozen representative case and backup-only evidence; not a universal performance claim.",
        "ARCH-01-doef-architecture-master": "Deterministic frozen pipeline; not end-to-end differentiable, jointly trained, online, or bilevel.",
        "CON-01-prediction-decision-bridge": "Conceptual only; does not quantify causal effect, cost, carbon, or energy savings.",
        "CON-02-contribution-overview": "Project-scoped contribution summary; no external novelty or SOTA claim.",
    }
    unsupported = {
        "SCI-01-forecast-decision-mismatch": "Forecast accuracy is irrelevant; all accurate forecasts make poor decisions; causal or universal claims.",
        "SCI-02-doef-main-results": "SOTA, universal superiority, unseen-building generalization, significance, cost, carbon, or energy savings.",
        "SCI-03-multibuilding-regret": "Transfer to unseen buildings or performance outside the fixed eight-building scope.",
        "SCI-04-validation-weight-selection": "Test-selected weights, joint training, bilevel optimization, or statistical significance.",
        "SCI-05-storage-dispatch-frozen": "Universal dispatch behavior, new numerical values, or a newly selected representative case.",
        "ARCH-01-doef-architecture-master": "Neural, transformer, RL, online learning, uncertainty, digital twin, agent, or LLM modules.",
        "CON-01-prediction-decision-bridge": "Experimental evidence or quantified outcomes.",
        "CON-02-contribution-overview": "Experimental evidence, first/world-first, or state-of-the-art positioning.",
    }
    assets: list[dict[str, Any]] = []
    for planned in inventory["assets"]:
        outputs, checksum = builders[planned["asset_id"]]()
        item = {
            "asset_id": planned["asset_id"],
            "title": planned["title"],
            "asset_type": planned["asset_type"],
            "scientific_or_conceptual": planned["scientific_or_conceptual"],
            "claim_id": planned["linked_claim_id"],
            "evidence_id": planned["linked_evidence_id"],
            "intended_message": planned["intended_message"],
            "source_phase": planned["source_phase"],
            "source_files": planned["canonical_source_files"],
            "source_hashes": planned["source_hashes"],
            "source_fields": planned["source_fields"],
            "deterministic_transform": planned["deterministic_transform"],
            "chart_type": planned["chart_type"],
            "output_files": outputs,
            "output_hashes": {p: sha256_bytes((ROOT / p).read_bytes()) for p in outputs},
            "plotted_values_checksum": checksum,
            "generation_script": "scripts/build_phase13_1_visual_assets.py",
            "generation_script_version": SCRIPT_VERSION,
            "slide_role": planned["presentation_role"],
            "priority": planned["priority"],
            "supports_claim": planned["intended_message"],
            "does_not_support": unsupported[planned["asset_id"]],
            "required_caveat": caveats[planned["asset_id"]],
            "truthfulness_status": "PENDING_VALIDATION",
            "presentation_suitability": "PENDING_VALIDATION",
            "reproducibility_status": "PENDING_VALIDATION",
            "status": "candidate",
        }
        assets.append(item)

    STYLE_PATH.write_text(json.dumps(style_guide(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    preview_files = write_preview(assets)
    manifest = {
        "schema_version": 1,
        "phase": "13.1",
        "status": "candidate",
        "logical_role": "presentation-ready visual assets derived from frozen approved evidence",
        "producer": "scripts/build_phase13_1_visual_assets.py",
        "producer_version": SCRIPT_VERSION,
        "starting_head": inventory["starting_head"],
        "branch_at_start": inventory["branch"],
        "hash_contract": inventory["hash_contract"],
        "scientific_freeze": inventory["scientific_freeze"],
        "asset_count": len(assets),
        "scientific_asset_count": sum(a["scientific_or_conceptual"] == "SCIENTIFIC" for a in assets),
        "conceptual_asset_count": sum(a["scientific_or_conceptual"] != "SCIENTIFIC" for a in assets),
        "style_guide": STYLE_PATH.relative_to(ROOT).as_posix(),
        "preview_files": preview_files,
        "assets": assets,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
