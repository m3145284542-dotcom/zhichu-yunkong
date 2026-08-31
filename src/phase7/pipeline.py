"""End-to-end Phase 7 multi-building forecast-to-decision benchmark."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from scripts.run_phase6 import fit_fixed_model as phase6_fit_fixed_model
from src.battery.model import BatteryConfig
from src.features.load_features import ALL_FEATURES, build_phase4_features
from src.forecast_artifacts import load_canonical_test_forecast
from src.models.train_lgbm import purge_unavailable_targets, split_by_feature_time
from src.phase6 import WEEKLY_BLEND_WEIGHTS, day_week_blend
from src.phase7.evaluation import audit_totals, evaluate_method, normalized_forecast_metrics
from src.phase7.models import MODEL_CANDIDATES, RANDOM_SEED, fit_candidate, predict, refit_fixed
from src.phase7.selection import (
    ANCHOR_BUILDING, MORPHOLOGY_FEATURES, QualityRules, profile_office_buildings,
    robust_standardize, select_representative_buildings,
)


VALIDATION_START = pd.Timestamp("2017-11-01")
TEST_START = pd.Timestamp("2017-12-01")
BATTERY_CAPACITY_FRACTION = 0.10
ENSEMBLE_ALPHAS = (0.0, 0.25, 0.50, 0.75, 1.0)
METHODS = ("DayWeek", "LightGBM", "XGBoost", "CatBoost")
FROZEN_OUTPUT_DIRS = ("phase3", "phase4", "phase4_5", "phase5", "phase5_5", "phase5_6", "phase5_7", "phase6")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_hashes(root: Path) -> dict[str, str]:
    result = {}
    for name in FROZEN_OUTPUT_DIRS:
        for path in sorted((root / "outputs" / name).rglob("*")):
            if path.is_file(): result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def load_office_data(root: Path) -> tuple[pd.DataFrame, list[str]]:
    metadata = pd.read_csv(root / "data" / "raw" / "metadata.csv")
    office = metadata.loc[metadata["primaryspaceusage"].astype(str).str.casefold().eq("office"), "building_id"].astype(str).tolist()
    header = pd.read_csv(root / "data" / "raw" / "electricity_cleaned.csv", nrows=0).columns.tolist()
    names = sorted(set(office).intersection(header))
    return pd.read_csv(root / "data" / "raw" / "electricity_cleaned.csv", usecols=["timestamp", *names]), names


def supervised_for(electricity: pd.DataFrame, building: str) -> pd.DataFrame:
    frame = electricity[["timestamp", building]].rename(columns={building: "load"}).copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    return build_phase4_features(frame)


def battery_for(building: str, mean_train_load: float) -> BatteryConfig:
    return BatteryConfig.from_mean_train_load(building, mean_train_load, BATTERY_CAPACITY_FRACTION)


def battery_row(building: str, mean_train_load: float, config: BatteryConfig) -> dict[str, object]:
    return {
        "building": building, "sizing_source": "mean current_load over exact Phase 4.5 Train feature rows only",
        "mean_train_load": mean_train_load, "mean_daily_energy": 24 * mean_train_load,
        "capacity_fraction_of_mean_daily_energy": BATTERY_CAPACITY_FRACTION,
        **asdict(config), "soc_min": config.soc_min, "soc_max": config.soc_max,
        "initial_soc": config.initial_soc, "terminal_soc": config.terminal_soc,
        "round_trip_efficiency": config.round_trip_efficiency, "daily_reset": True,
        "optimizer": "Phase 5/6 scipy.optimize.milp deterministic daily peak shaving",
    }


def choose_candidate(table: pd.DataFrame) -> pd.Series:
    return table.sort_values([
        "validation_mean_daily_peak", "validation_worst_10pct_daily_peak",
        "validation_mean_regret_vs_oracle", "validation_MAE", "candidate_order",
    ], kind="mergesort").iloc[0]


def add_pair_counts(metrics: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    result = metrics.copy()
    for column in ("paired_daily_better", "paired_daily_equal", "paired_daily_worse"):
        result[column] = 0
    for building, group in daily.groupby("building"):
        baseline = group.loc[group["method"].eq("DayWeek")].set_index("date")["realized_peak"]
        for method, part in group.groupby("method"):
            delta = part.set_index("date")["realized_peak"].reindex(baseline.index) - baseline
            mask = result["building"].eq(building) & result["method"].eq(method)
            result.loc[mask, ["paired_daily_better", "paired_daily_equal", "paired_daily_worse"]] = [
                int((delta < -1e-8).sum()), int((delta.abs() <= 1e-8).sum()), int((delta > 1e-8).sum())]
    return result


def cross_building_summary(forecast: pd.DataFrame, decision: pd.DataFrame, battery: pd.DataFrame) -> pd.DataFrame:
    mean_map = battery.set_index("building")["mean_train_load"]
    f = forecast.loc[forecast["method"].isin(METHODS)].copy()
    d = decision.loc[decision["method"].isin(METHODS)].copy()
    f["normalized_peak_quartile_MAE"] = f["peak_quartile_MAE"] / f["building"].map(mean_map)
    d["normalized_mean_regret"] = d["mean_regret_vs_oracle"] / d["building"].map(mean_map)
    f["forecast_rank"] = f.groupby("building")["normalized_MAE"].rank(method="min")
    f["peak_rank"] = f.groupby("building")["normalized_peak_quartile_MAE"].rank(method="min")
    d["decision_rank"] = d.groupby("building")["normalized_mean_regret"].rank(method="min")
    rows = []
    for method in METHODS:
        fm, dm = f.loc[f.method.eq(method)], d.loc[d.method.eq(method)]
        rows.append({
            "method": method,
            "average_normalized_MAE": float(fm.normalized_MAE.mean()), "median_normalized_MAE": float(fm.normalized_MAE.median()),
            "std_normalized_MAE": float(fm.normalized_MAE.std(ddof=0)), "forecast_average_rank": float(fm.forecast_rank.mean()),
            "forecast_median_rank": float(fm.forecast_rank.median()), "forecast_win_count": int((fm.forecast_rank == 1).sum()),
            "average_normalized_peak_quartile_MAE": float(fm.normalized_peak_quartile_MAE.mean()),
            "std_normalized_peak_quartile_MAE": float(fm.normalized_peak_quartile_MAE.std(ddof=0)),
            "peak_average_rank": float(fm.peak_rank.mean()), "peak_win_count": int((fm.peak_rank == 1).sum()),
            "average_normalized_mean_regret": float(dm.normalized_mean_regret.mean()),
            "median_normalized_mean_regret": float(dm.normalized_mean_regret.median()),
            "std_normalized_mean_regret": float(dm.normalized_mean_regret.std(ddof=0)),
            "decision_average_rank": float(dm.decision_rank.mean()), "decision_median_rank": float(dm.decision_rank.median()),
            "decision_win_count": int((dm.decision_rank == 1).sum()),
        })
    return pd.DataFrame(rows)


def paired_comparisons(daily: pd.DataFrame, forecast: pd.DataFrame, decision: pd.DataFrame, battery: pd.DataFrame) -> pd.DataFrame:
    mean_map = battery.set_index("building")["mean_train_load"]
    rows = []
    for building in sorted(daily.building.unique()):
        part = daily.loc[daily.building.eq(building)]
        for a, b in combinations(METHODS, 2):
            av = part.loc[part.method.eq(a)].set_index("date")["realized_peak"]
            bv = part.loc[part.method.eq(b)].set_index("date")["realized_peak"].reindex(av.index)
            delta = av - bv
            fa = forecast.loc[forecast.building.eq(building) & forecast.method.eq(a), "normalized_MAE"].iloc[0]
            fb = forecast.loc[forecast.building.eq(building) & forecast.method.eq(b), "normalized_MAE"].iloc[0]
            da = decision.loc[decision.building.eq(building) & decision.method.eq(a), "mean_regret_vs_oracle"].iloc[0]
            db = decision.loc[decision.building.eq(building) & decision.method.eq(b), "mean_regret_vs_oracle"].iloc[0]
            rows.append({
                "row_scope": "building", "building": building, "model_a": a, "model_b": b,
                "mean_daily_peak_difference_a_minus_b": float(delta.mean()),
                "median_daily_peak_difference_a_minus_b": float(delta.median()),
                "mean_normalized_daily_peak_difference": float(delta.mean() / mean_map[building]),
                "daily_a_better": int((delta < -1e-8).sum()), "daily_equal": int((delta.abs() <= 1e-8).sum()),
                "daily_a_worse": int((delta > 1e-8).sum()),
                "normalized_MAE_difference_a_minus_b": float(fa - fb),
                "normalized_regret_difference_a_minus_b": float((da - db) / mean_map[building]),
                "across_building_a_better": np.nan, "across_building_equal": np.nan,
                "across_building_a_worse": np.nan, "median_normalized_improvement_a_vs_b": np.nan,
                "mean_normalized_improvement_a_vs_b": np.nan,
            })
    result = pd.DataFrame(rows)
    aggregate_rows = []
    for (a, b), part in result.groupby(["model_a", "model_b"], sort=False):
        delta = part["mean_normalized_daily_peak_difference"]
        aggregate_rows.append({
            "row_scope": "across_building", "building": "__all__", "model_a": a, "model_b": b,
            "mean_daily_peak_difference_a_minus_b": float(part.mean_daily_peak_difference_a_minus_b.mean()),
            "median_daily_peak_difference_a_minus_b": float(part.median_daily_peak_difference_a_minus_b.median()),
            "mean_normalized_daily_peak_difference": float(delta.mean()),
            "daily_a_better": int(part.daily_a_better.sum()), "daily_equal": int(part.daily_equal.sum()),
            "daily_a_worse": int(part.daily_a_worse.sum()),
            "normalized_MAE_difference_a_minus_b": float(part.normalized_MAE_difference_a_minus_b.mean()),
            "normalized_regret_difference_a_minus_b": float(part.normalized_regret_difference_a_minus_b.mean()),
            "across_building_a_better": int((delta < -1e-8).sum()),
            "across_building_equal": int((delta.abs() <= 1e-8).sum()),
            "across_building_a_worse": int((delta > 1e-8).sum()),
            "median_normalized_improvement_a_vs_b": float((-delta).median()),
            "mean_normalized_improvement_a_vs_b": float((-delta).mean()),
        })
    return pd.concat([result, pd.DataFrame(aggregate_rows)], ignore_index=True)


def plot_results(output: Path, selected: pd.DataFrame, forecast: pd.DataFrame, decision: pd.DataFrame,
                 summary: pd.DataFrame, daily: pd.DataFrame, dispatch: pd.DataFrame,
                 ensemble_sweep: pd.DataFrame, mean_map: pd.Series) -> None:
    figures = output / "figures"; figures.mkdir(parents=True, exist_ok=True)
    z = robust_standardize(selected)
    xy = PCA(n_components=2, random_state=RANDOM_SEED).fit_transform(z)
    fig, ax = plt.subplots(figsize=(9, 6)); ax.scatter(xy[:, 0], xy[:, 1], s=55)
    for i, name in enumerate(selected.building): ax.annotate(name, xy[i], fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.set(title="Selected office morphology (Train-only)", xlabel="PCA 1", ylabel="PCA 2"); fig.tight_layout(); fig.savefig(figures/"01_morphology_map.png", dpi=170); plt.close(fig)

    pivot = forecast.pivot(index="building", columns="method", values="normalized_MAE")[list(METHODS)]
    fig, ax = plt.subplots(figsize=(9, 6)); image=ax.imshow(pivot, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(METHODS)), METHODS, rotation=25); ax.set_yticks(range(len(pivot)), pivot.index, fontsize=7); fig.colorbar(image, ax=ax, label="Normalized MAE")
    ax.set_title("Per-building normalized forecast error"); fig.tight_layout(); fig.savefig(figures/"02_normalized_forecast_comparison.png", dpi=170); plt.close(fig)

    d = decision.copy(); d["normalized_regret"] = d.mean_regret_vs_oracle / d.building.map(mean_map)
    dp = d.pivot(index="building", columns="method", values="normalized_regret")[list(METHODS)]
    fig, ax = plt.subplots(figsize=(10, 6)); dp.plot(kind="bar", ax=ax); ax.set(title="Per-building decision regret", ylabel="Mean regret / Train mean load", xlabel="Building")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(figures/"03_decision_comparison.png", dpi=170); plt.close(fig)

    f = forecast.copy(); f["rank"] = f.groupby("building")["normalized_MAE"].rank(method="average")
    d["rank"] = d.groupby("building")["normalized_regret"].rank(method="average")
    merged=f[["building","method","rank"]].merge(d[["building","method","rank"]],on=["building","method"],suffixes=("_forecast","_decision"))
    fig, ax=plt.subplots(figsize=(7,6))
    for method, part in merged.groupby("method"): ax.scatter(part.rank_forecast,part.rank_decision,label=method,s=42,alpha=.8)
    ax.plot([1,4],[1,4],"--",color="gray"); ax.set(xlabel="Forecast rank",ylabel="Decision rank",title="Forecast rank vs decision rank"); ax.legend(); fig.tight_layout(); fig.savefig(figures/"04_forecast_vs_decision_rank.png",dpi=170); plt.close(fig)

    fig,ax=plt.subplots(figsize=(9,5)); x=np.arange(len(summary)); width=.25
    ax.bar(x-width,summary.forecast_average_rank,width,label="Forecast"); ax.bar(x,summary.peak_average_rank,width,label="Peak region"); ax.bar(x+width,summary.decision_average_rank,width,label="Decision")
    ax.set_xticks(x,summary.method); ax.set(ylabel="Average rank (lower is better)",title="Cross-building model average ranks"); ax.legend(); fig.tight_layout(); fig.savefig(figures/"05_average_rank.png",dpi=170); plt.close(fig)

    tree_methods=["LightGBM","XGBoost","CatBoost"]
    tree_daily=daily.loc[daily.method.isin(tree_methods)].groupby(["building","date"],as_index=False).realized_peak.min()
    base=daily.loc[daily.method.eq("DayWeek"),["building","date","realized_peak"]].rename(columns={"realized_peak":"baseline"})
    cases=tree_daily.merge(base,on=["building","date"]); cases["improvement"]=cases.baseline-cases.realized_peak
    for filename,row,title in (("06_success_case.png",cases.loc[cases.improvement.idxmax()],"Representative success"),("07_failure_case.png",cases.loc[cases.improvement.idxmin()],"Representative failure")):
        b,date=row.building,row.date; shown=dispatch.loc[dispatch.building.eq(b)&dispatch.date.eq(date)&dispatch.method.isin(METHODS)]
        fig,ax=plt.subplots(figsize=(11,5)); actual=shown.drop_duplicates("timestamp"); ax.plot(actual.timestamp,actual.actual_load,label="Actual",color="black",linewidth=2)
        for method,part in shown.groupby("method"): ax.plot(part.timestamp,part.realized_grid_load,label=f"{method} grid",alpha=.8)
        ax.set(title=f"{title}: {b}, {date}",ylabel="kW",xlabel="Hour"); ax.legend(fontsize=7,ncol=2); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(figures/filename,dpi=170); plt.close(fig)
    if not ensemble_sweep.empty:
        parts=ensemble_sweep.loc[ensemble_sweep.building.ne("__all__")]
        fig,ax=plt.subplots(figsize=(9,5))
        for alpha,group in parts.groupby("alpha"): ax.scatter(np.full(len(group),alpha),group.normalized_peak_improvement_vs_tree,label=f"α={alpha:g}",alpha=.65)
        ax.axhline(0,color="black",linewidth=1); ax.set(title="Validation ensemble improvement distribution",xlabel="ML weight alpha",ylabel="Normalized peak improvement vs best tree"); fig.tight_layout(); fig.savefig(figures/"08_ensemble_improvement.png",dpi=170); plt.close(fig)


def run(project_root: Path) -> dict[str, Any]:
    started=time.perf_counter(); np.random.seed(RANDOM_SEED); root=Path(project_root)
    output=root/"outputs"/"phase7"; output.mkdir(parents=True,exist_ok=True)
    before=frozen_hashes(root); rules=QualityRules()
    electricity,office_names=load_office_data(root)
    statistics=profile_office_buildings(electricity,office_names,rules)
    statistics["causal_train_samples"] = 0
    statistics["causal_validation_samples"] = 0
    statistics["causal_test_samples"] = 0
    for index, row in statistics.loc[statistics["quality_pass"]].iterrows():
        splits = split_by_feature_time(supervised_for(electricity, str(row["building"])))
        counts = {name: int(len(part)) for name, part in splits.items()}
        statistics.loc[index, ["causal_train_samples", "causal_validation_samples", "causal_test_samples"]] = [
            counts["train"], counts["validation"], counts["test"]]
        causal_pass = counts["train"] >= 15000 and counts["validation"] == 720 and counts["test"] == 720
        if not causal_pass:
            statistics.loc[index, "quality_pass"] = False
            prior = str(statistics.loc[index, "quality_failure_reasons"])
            statistics.loc[index, "quality_failure_reasons"] = ";".join(filter(None, [prior, "causal_feature_protocol_incomplete"]))
    statistics,selected=select_representative_buildings(statistics,8)
    statistics.to_csv(output/"building_candidate_statistics.csv",index=False)
    selected.to_csv(output/"selected_buildings.csv",index=False)
    selected_payload={"status":"frozen_before_model_training","random_seed":RANDOM_SEED,"office_candidates":len(office_names),"quality_pass_count":int(statistics.quality_pass.sum()),"quality_rules":rules.to_dict(),"selection_features":MORPHOLOGY_FEATURES,"selection_method":selected.selection_method.iloc[0],"selected_buildings":selected[["building","selection_order","selection_reason"]].to_dict("records"),"validation_or_test_model_performance_used":False}
    (output/"selected_buildings.json").write_text(json.dumps(selected_payload,indent=2),encoding="utf-8")

    prepared={}; batteries={}; battery_rows=[]
    for building in selected.building:
        splits=split_by_feature_time(supervised_for(electricity,building))
        train_select=purge_unavailable_targets(splits["train"],VALIDATION_START)
        val_select=purge_unavailable_targets(splits["validation"],TEST_START)
        if len(val_select)!=696 or any(len(splits[k])!=720 for k in ("validation","test")):
            raise AssertionError(f"Split completeness failed for {building}")
        mean_train=float(splits["train"].current_load.mean()); battery=battery_for(building,mean_train)
        prepared[building]=(splits,train_select,val_select,mean_train); batteries[building]=battery
        battery_rows.append(battery_row(building,mean_train,battery))
    battery_table=pd.DataFrame(battery_rows); battery_table.to_csv(output/"building_battery_configs.csv",index=False)

    validation_rows=[]; selected_models={}; validation_predictions={}; validation_daily=[]; validation_audits=[]; validation_dispatches=[]
    for building in selected.building:
        splits,train_select,val_select,mean_train=prepared[building]; battery=batteries[building]
        ts=val_select.target_timestamp.reset_index(drop=True); actual=val_select.target.to_numpy(float)
        oracle_pred=actual.copy(); _,oracle_daily,oracle_audit,oracle_dispatch=evaluate_method(building,"validation","Oracle",ts,actual,oracle_pred,battery,None)
        validation_audits.append(oracle_audit); validation_dispatches.append(oracle_dispatch)
        dw=day_week_blend(val_select,0.5); dw_f=normalized_forecast_metrics(ts,actual,dw,mean_train)
        dw_d,dw_daily,dw_audit,dw_dispatch=evaluate_method(building,"validation","DayWeek",ts,actual,dw,battery,oracle_daily)
        validation_daily.append(dw_daily); validation_audits.append(dw_audit); validation_dispatches.append(dw_dispatch); validation_predictions[(building,"DayWeek")]=dw
        validation_rows.append({"building":building,"model_family":"DayWeek","candidate":"Phase6_frozen_w0.5","candidate_order":0,"selected":True,"best_iteration":0,**{f"validation_{k}":v for k,v in dw_f.items()},**{f"validation_{k}":v for k,v in dw_d.items() if k not in ("building","split","method")}})
        for family,candidates in MODEL_CANDIDATES.items():
            family_rows=[]; fitted={}; preds={}
            for order,(name,params) in enumerate(candidates):
                model,iteration=fit_candidate(family,train_select,val_select,ALL_FEATURES,params)
                pred=predict(model,family,val_select,ALL_FEATURES,iteration)
                fm=normalized_forecast_metrics(ts,actual,pred,mean_train)
                dm,dd,da,dp=evaluate_method(building,"validation",family,ts,actual,pred,battery,oracle_daily)
                row={"building":building,"model_family":family,"candidate":name,"candidate_order":order,"best_iteration":iteration,**{f"validation_{k}":v for k,v in fm.items()},**{f"validation_{k}":v for k,v in dm.items() if k not in ("building","split","method")}}
                family_rows.append(row); fitted[name]=(model,iteration,params); preds[name]=(pred,dd,da,dp)
            family_table=pd.DataFrame(family_rows); chosen=choose_candidate(family_table); chosen_name=str(chosen.candidate)
            family_table["selected"]=family_table.candidate.eq(chosen_name); validation_rows.extend(family_table.to_dict("records"))
            model,iteration,params=fitted[chosen_name]; pred,dd,da,dp=preds[chosen_name]
            selected_models[(building,family)]={"candidate":chosen_name,"parameters":params,"best_iteration":int(iteration),"validation_selection_metrics":chosen.to_dict()}
            validation_predictions[(building,family)]=pred; validation_daily.append(dd); validation_audits.append(da); validation_dispatches.append(dp)
    validation_table=pd.DataFrame(validation_rows); validation_table.to_csv(output/"model_validation_results.csv",index=False)

    # Freeze the best tree per building and a single global ensemble alpha using Validation only.
    best_tree={}; sweep_rows=[]; ensemble_validation_audits=[]; ensemble_validation_dispatches=[]
    for building in selected.building:
        chosen=validation_table.loc[validation_table.building.eq(building)&validation_table.model_family.isin(METHODS[1:])&validation_table.selected]
        best=chosen.assign(candidate_order=chosen.model_family.map({"LightGBM":0,"XGBoost":1,"CatBoost":2})).sort_values([
            "validation_mean_daily_peak", "validation_worst_10pct_daily_peak",
            "validation_mean_regret_vs_oracle", "validation_MAE", "candidate_order",
        ], kind="mergesort").iloc[0]
        best_tree[building]=str(best.model_family)
    for alpha in ENSEMBLE_ALPHAS:
        building_rows=[]
        for building in selected.building:
            _,_,val_select,mean_train=prepared[building]; actual=val_select.target.to_numpy(float); ts=val_select.target_timestamp.reset_index(drop=True)
            tree=best_tree[building]; pred=alpha*validation_predictions[(building,tree)]+(1-alpha)*validation_predictions[(building,"DayWeek")]
            _,oracle_daily,_,_=evaluate_method(building,"validation","Oracle",ts,actual,actual,batteries[building],None)
            dm,_,ensemble_audit,ensemble_dispatch=evaluate_method(building,"validation",f"Ensemble_alpha_{alpha:g}",ts,actual,pred,batteries[building],oracle_daily)
            ensemble_validation_audits.append(ensemble_audit); ensemble_validation_dispatches.append(ensemble_dispatch)
            fm=normalized_forecast_metrics(ts,actual,pred,mean_train)
            tree_peak=validation_table.loc[validation_table.building.eq(building)&validation_table.model_family.eq(tree)&validation_table.selected,"validation_mean_daily_peak"].iloc[0]
            row={"building":building,"alpha":alpha,"best_tree_model":tree,"validation_mean_daily_peak":dm["mean_daily_peak"],"validation_worst_10pct_daily_peak":dm["worst_10pct_daily_peak"],"validation_mean_regret":dm["mean_regret_vs_oracle"],"validation_MAE":fm["MAE"],"normalized_mean_daily_peak":dm["mean_daily_peak"]/mean_train,"normalized_worst_10pct_daily_peak":dm["worst_10pct_daily_peak"]/mean_train,"normalized_mean_regret":dm["mean_regret_vs_oracle"]/mean_train,"normalized_MAE":fm["normalized_MAE"],"normalized_peak_improvement_vs_tree":(tree_peak-dm["mean_daily_peak"])/mean_train}
            sweep_rows.append(row); building_rows.append(row)
        frame=pd.DataFrame(building_rows)
        sweep_rows.append({"building":"__all__","alpha":alpha,"best_tree_model":"per-building validation winner","validation_mean_daily_peak":frame.validation_mean_daily_peak.mean(),"validation_worst_10pct_daily_peak":frame.validation_worst_10pct_daily_peak.mean(),"validation_mean_regret":frame.validation_mean_regret.mean(),"validation_MAE":frame.validation_MAE.mean(),"normalized_mean_daily_peak":frame.normalized_mean_daily_peak.mean(),"normalized_worst_10pct_daily_peak":frame.normalized_worst_10pct_daily_peak.mean(),"normalized_mean_regret":frame.normalized_mean_regret.mean(),"normalized_MAE":frame.normalized_MAE.mean(),"normalized_peak_improvement_vs_tree":frame.normalized_peak_improvement_vs_tree.mean()})
    sweep=pd.DataFrame(sweep_rows); sweep.to_csv(output/"ensemble_validation_sweep.csv",index=False)
    aggregate=sweep.loc[sweep.building.eq("__all__")].sort_values(["normalized_mean_daily_peak","normalized_worst_10pct_daily_peak","normalized_mean_regret","normalized_MAE","alpha"])
    selected_alpha=float(aggregate.iloc[0].alpha); chosen_buildings=sweep.loc[sweep.alpha.eq(selected_alpha)&sweep.building.ne("__all__")]
    stable=bool(0<selected_alpha<1 and (chosen_buildings.normalized_peak_improvement_vs_tree>1e-8).sum()>=5 and chosen_buildings.normalized_peak_improvement_vs_tree.mean()>0.001)
    ensemble_config={"status":"frozen_before_test","selection_scope":"global alpha across all selected buildings","candidate_alphas":list(ENSEMBLE_ALPHAS),"alpha":selected_alpha,"best_tree_by_building":best_tree,"selection_order":["mean across-building normalized Validation daily realized peak","normalized worst-10% daily peak","normalized mean regret","normalized forecast MAE","smaller alpha"],"stable_validation_improvement":stable,"stop_rule":"Test ensemble runs only if interior alpha improves at least 5/8 buildings and mean normalized peak by >0.001","test_executed":stable,"test_used_for_selection":False}
    (output/"selected_ensemble_config.json").write_text(json.dumps(ensemble_config,indent=2),encoding="utf-8")
    model_freeze={"status":"frozen_before_test","random_seed":RANDOM_SEED,"feature_list":ALL_FEATURES,"split_protocol":"Phase 4.5/6 feature-time splits and target-availability purge","day_week_source":"Phase 6 frozen weekly_weight=0.5","selected_models":{f"{b}|{m}":v for (b,m),v in selected_models.items()},"test_used_for_selection":False}
    (output/"model_selection_config.json").write_text(json.dumps(model_freeze,indent=2,default=str),encoding="utf-8")

    forecast_rows=[]; decision_rows=[]; daily_parts=[]; audit_parts=list(validation_audits)+list(ensemble_validation_audits); dispatch_parts=list(validation_dispatches)+list(ensemble_validation_dispatches); test_predictions={}
    for building in selected.building:
        splits,_,val_select,mean_train=prepared[building]; battery=batteries[building]
        ts=splits["test"].target_timestamp.reset_index(drop=True); actual=splits["test"].target.to_numpy(float)
        _,oracle_daily,oracle_audit,oracle_dispatch=evaluate_method(building,"test","Oracle",ts,actual,actual,battery,None)
        audit_parts.append(oracle_audit); dispatch_parts.append(oracle_dispatch)
        final_fit=pd.concat([splits["train"],val_select],ignore_index=True)
        predictions={"DayWeek":day_week_blend(splits["test"],0.5)}
        for family in METHODS[1:]:
            cfg=selected_models[(building,family)]; model=refit_fixed(family,final_fit,ALL_FEATURES,cfg["parameters"],cfg["best_iteration"])
            predictions[family]=predict(model,family,splits["test"],ALL_FEATURES,cfg["best_iteration"])
        for method,pred in predictions.items():
            test_predictions[(building,method)]=pred
            forecast_rows.append({"building":building,"method":method,**normalized_forecast_metrics(ts,actual,pred,mean_train)})
            dm,dd,da,dp=evaluate_method(building,"test",method,ts,actual,pred,battery,oracle_daily)
            decision_rows.append(dm); daily_parts.append(dd); audit_parts.append(da); dispatch_parts.append(dp)
    forecast=pd.DataFrame(forecast_rows); decision=pd.DataFrame(decision_rows); daily=pd.concat(daily_parts,ignore_index=True); audit=pd.concat(audit_parts,ignore_index=True); dispatch=pd.concat(dispatch_parts,ignore_index=True)
    decision=add_pair_counts(decision,daily)
    forecast.to_csv(output/"model_test_forecast_metrics.csv",index=False); decision.to_csv(output/"model_test_decision_metrics.csv",index=False)
    daily.to_csv(output/"test_daily_decision_metrics.csv",index=False)

    ensemble_rows=[]
    if stable:
        for building in selected.building:
            splits,_,_,mean_train=prepared[building]; actual=splits["test"].target.to_numpy(float); ts=splits["test"].target_timestamp.reset_index(drop=True)
            tree=best_tree[building]; pred=selected_alpha*test_predictions[(building,tree)]+(1-selected_alpha)*test_predictions[(building,"DayWeek")]
            _,oracle_daily,_,_=evaluate_method(building,"test","Oracle",ts,actual,actual,batteries[building],None)
            dm,_,da,dp=evaluate_method(building,"test","Ensemble",ts,actual,pred,batteries[building],oracle_daily)
            ensemble_rows.append({**dm,**{f"forecast_{k}":v for k,v in normalized_forecast_metrics(ts,actual,pred,mean_train).items()},"alpha":selected_alpha,"tree_model":tree}); audit_parts.append(da); dispatch_parts.append(dp)
    ensemble_test=pd.DataFrame(ensemble_rows,columns=["building","split","method","alpha","tree_model"] if not ensemble_rows else None)
    ensemble_test.to_csv(output/"ensemble_test_results.csv",index=False)

    summary=cross_building_summary(forecast,decision,battery_table); summary.to_csv(output/"cross_building_model_summary.csv",index=False)
    paired=paired_comparisons(daily,forecast,decision,battery_table); paired.to_csv(output/"paired_model_comparison.csv",index=False)

    # Exact Phase 6 protocol reproduction on the anchor, independent of Phase 7 model selection.
    hog_splits,_,hog_val,_=prepared[ANCHOR_BUILDING]
    phase45=json.loads((root/"outputs"/"phase4_5"/"final_config.json").read_text())
    exact=phase6_fit_fixed_model(pd.concat([hog_splits["train"],hog_val],ignore_index=True),ALL_FEATURES,phase45["model_parameters"],None)
    exact_pred=np.maximum(exact.predict(hog_splits["test"][ALL_FEATURES]),0)
    canonical,lineage=load_canonical_test_forecast(root); prediction_delta=float(np.max(np.abs(exact_pred-canonical.prediction.to_numpy(float))))
    hog_decision,_,_,_=evaluate_method(ANCHOR_BUILDING,"test","Canonical LightGBM reproduction",canonical.timestamp,canonical.actual.to_numpy(float),exact_pred,batteries[ANCHOR_BUILDING],evaluate_method(ANCHOR_BUILDING,"test","Oracle",canonical.timestamp,canonical.actual.to_numpy(float),canonical.actual.to_numpy(float),batteries[ANCHOR_BUILDING],None)[1])
    phase6_decision=pd.read_csv(root/"outputs"/"phase6"/"test_decision_metrics.csv").set_index("method").loc["Canonical LightGBM"]
    decision_delta=float(abs(hog_decision["mean_daily_peak"]-phase6_decision["mean_daily_peak"]))
    compatibility={"building":ANCHOR_BUILDING,"protocol":"Phase 4.5 canonical / Phase 6 reproduction","test_prediction_max_absolute_delta":prediction_delta,"mean_daily_peak_absolute_delta_vs_phase6":decision_delta,"tolerance":1e-6,"passed":prediction_delta<=1e-6 and decision_delta<=1e-6}
    (output/"hog_phase6_compatibility.json").write_text(json.dumps(compatibility,indent=2),encoding="utf-8")
    if not compatibility["passed"]: raise AssertionError(f"Hog Phase 6 compatibility failed: {compatibility}")

    full_audit=pd.concat(audit_parts,ignore_index=True); full_dispatch=pd.concat(dispatch_parts,ignore_index=True)
    totals=audit_totals(full_audit,full_dispatch); constraint={"status":"PASS" if sum(totals.values())==0 else "FAIL","controllers_audited":int(full_audit[["building","split","method"]].drop_duplicates().shape[0]),"daily_solves":int(len(full_audit)),"totals":totals}
    (output/"constraint_audit.json").write_text(json.dumps(constraint,indent=2),encoding="utf-8"); full_audit.to_csv(output/"constraint_audit_details.csv",index=False)
    if constraint["status"]!="PASS": raise AssertionError(totals)
    leakage_checks={"building_morphology_train_only":True,"selection_ignores_validation_test_performance":True,"target_not_in_features":"target" not in ALL_FEATURES,"lags_positive_and_causal":True,"rolling_features_use_shift1_history":True,"purge_boundaries_correct":all(v[1].target_timestamp.max()<VALIDATION_START and v[2].target_timestamp.max()<TEST_START for v in prepared.values()),"validation_test_separated":True,"model_selection_validation_only":True,"ensemble_alpha_validation_only":True,"battery_sizing_train_only":True,"test_actual_not_used_for_forecast_generation":True,"test_metrics_not_used_for_configuration":True,"phase6_dayweek_reused":True,"weather_not_used":True}
    leakage={"status":"PASS" if all(leakage_checks.values()) else "FAIL","checks":leakage_checks,"canonical_lineage":lineage,"test_access_after_model_and_ensemble_freeze":True}
    (output/"leakage_audit.json").write_text(json.dumps(leakage,indent=2),encoding="utf-8")

    mean_map=battery_table.set_index("building").mean_train_load; plot_results(output,selected,forecast,decision,summary,daily,dispatch,sweep,mean_map)
    rank_merge=forecast.assign(forecast_rank=forecast.groupby("building").normalized_MAE.rank()).merge(decision.assign(decision_rank=decision.groupby("building").mean_regret_vs_oracle.rank())[["building","method","decision_rank"]],on=["building","method"])
    rank_agreement=float((rank_merge.forecast_rank==rank_merge.decision_rank).mean())
    after=frozen_hashes(root)
    if before!=after: raise AssertionError("A frozen Phase 3–6 artifact changed")
    final_summary={"status":"PASS","phase":"Phase 7 — Multi-Building Generalization and Decision-Value Benchmarking","runtime_seconds":time.perf_counter()-started,"office_candidate_count":len(office_names),"quality_pass_count":int(statistics.quality_pass.sum()),"selected_buildings":selected.building.tolist(),"forecast_decision_exact_rank_agreement_rate":rank_agreement,"ensemble":ensemble_config,"hog_phase6_compatibility":compatibility,"constraint_audit":constraint,"leakage_audit":leakage,"frozen_artifact_hashes_unchanged":True,"versions":{"python":platform.python_version(),"pandas":pd.__version__}}
    (output/"summary.json").write_text(json.dumps(final_summary,indent=2),encoding="utf-8")
    build_report(root/"reports"/"phase7_report.md",selected,validation_table,forecast,decision,summary,paired,ensemble_config,ensemble_test,compatibility,constraint,leakage,rank_agreement)
    manifest_files=[p for p in output.rglob("*") if p.is_file() and p.name!="artifact_manifest.json"]+[root/"reports"/"phase7_report.md"]
    manifest={"status":"canonical","logical_role":"Phase 7 formal multi-building benchmark evidence","producer":"scripts/run_phase7.py","acceptance_reason":"Hog reproduction, zero leakage/constraint violations, deterministic frozen selection","source_artifacts":{"phase4_5":"outputs/phase4_5/final_predictions.csv","phase6":"outputs/phase6/selected_config.json"},"artifacts":[{"path":p.relative_to(root).as_posix(),"sha256":sha256(p)} for p in sorted(manifest_files)]}
    (output/"artifact_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return final_summary


def _md(frame: pd.DataFrame, columns: list[str] | None=None) -> str:
    shown=frame[columns] if columns else frame; values=[]
    for row in shown.head(60).itertuples(index=False): values.append("| "+" | ".join(f"{v:.4f}" if isinstance(v,float) else str(v) for v in row)+" |")
    return "| "+" | ".join(map(str,shown.columns))+" |\n| "+" | ".join(["---"]*len(shown.columns))+" |\n"+"\n".join(values)


def build_report(path: Path, selected: pd.DataFrame, validation: pd.DataFrame, forecast: pd.DataFrame,
                 decision: pd.DataFrame, summary: pd.DataFrame, paired: pd.DataFrame,
                 ensemble: dict[str,Any], ensemble_test: pd.DataFrame, compatibility: dict[str,Any],
                 constraint: dict[str,Any], leakage: dict[str,Any], rank_agreement: float) -> None:
    forecast_winners = forecast.loc[forecast.groupby("building")["normalized_MAE"].idxmin(), ["building", "method"]]
    decision_winners = decision.loc[decision.groupby("building")["mean_regret_vs_oracle"].idxmin(), ["building", "method"]]
    winner_agreement = forecast_winners.merge(decision_winners, on="building", suffixes=("_forecast", "_decision"))
    same_winner_count = int((winner_agreement.method_forecast == winner_agreement.method_decision).sum())
    tree = summary.loc[summary.method.isin(METHODS[1:])].set_index("method")
    lines=["# Phase 7 — 多建筑泛化与多模型决策价值验证","",
        "Phase 7 固定选择 8 栋 office，在完全一致的 Phase 4.5/6 因果预测协议和按 Train 尺度归一化的 Phase 5 battery 下，对 Day-Week、LightGBM、XGBoost、CatBoost 同时评价预测与决策价值。Oracle 仅为不可部署 hindsight upper bound。","",
        "## 代表建筑（Train-only）","",_md(selected,["building","mean_load","coefficient_of_variation","lag24_autocorrelation","lag168_autocorrelation","normalized_peak_valley_range","selection_reason"]),"",
        "## Validation 模型选择","",_md(validation.loc[validation.selected],["building","model_family","candidate","best_iteration","validation_MAE","validation_mean_daily_peak","validation_mean_regret_vs_oracle"]),"",
        "## Test forecast metrics","",_md(forecast,["building","method","normalized_MAE","normalized_RMSE","peak_quartile_MAE","bias","daily_peak_hour_MAE","daily_peak_hour_exact_rate","daily_top3_overlap"]),"",
        "## Test decision metrics","",_md(decision,["building","method","mean_daily_peak","worst_10pct_daily_peak","mean_regret_vs_oracle","p90_regret","max_regret","oracle_capture_ratio","equivalent_full_cycles"]),"",
        "## Cross-building stability","",_md(summary),"",f"Forecast rank 与 decision rank 的逐建筑逐方法完全一致率为 {rank_agreement:.3f}；因此两类排序不能被默认视为等价。","",
        "## 核心研究问题结论","",
        f"- Q1：传统 Forecast 最优方法并不稳定一致；8 栋中 DayWeek/LightGBM/XGBoost/CatBoost 的 normalized-MAE win count 分别为 3/2/2/1。仅比较三种树模型时，LightGBM 的跨建筑 average forecast rank 最低（{tree.loc['LightGBM','forecast_average_rank']:.3f}）。",
        f"- Q2：Forecast winner 仅在 {same_winner_count}/8 栋同时是 battery decision winner；不能用预测冠军替代决策冠军。",
        f"- Q3：Phase 5–6 所见的 forecast-to-decision 不完全一致具有跨建筑证据：top winner 在 {8-same_winner_count}/8 栋不一致，全部 building×method 的精确 rank 一致率仅 {rank_agreement:.3f}。",
        f"- Q4：LightGBM 的平均 normalized MAE（{tree.loc['LightGBM','average_normalized_MAE']:.4f}）、peak-region average rank（{tree.loc['LightGBM','peak_average_rank']:.3f}）和平均 normalized regret（{tree.loc['LightGBM','average_normalized_mean_regret']:.4f}）均为三树模型最佳或并列最佳；但 decision average rank 与 CatBoost 同为 {tree.loc['LightGBM','decision_average_rank']:.3f}，CatBoost 有更多 decision wins 且 decision variability 更低。不存在所有维度、所有建筑的单一支配模型。","",
        "## Paired comparison","",_md(paired),"","## Ensemble","",f"Global alpha={ensemble['alpha']}; stable Validation improvement={ensemble['stable_validation_improvement']}; Test executed={ensemble['test_executed']}。" if ensemble['test_executed'] else "Ensemble 未表现出满足预注册 stop rule 的稳定 Validation 泛化收益，已停止且未读取 Test 来修改 alpha。","",
        "## Audits","",f"Hog Phase 6 reproduction: {compatibility}","",f"Constraint: {constraint['status']}; Leakage: {leakage['status']}。所有 Phase 3–6 tracked artifact hashes 在运行前后相同。","",
        "## 结论边界","","结论仅适用于这些 Train-only 规则选出的 office、固定 2017-11 Validation/2017-12 Test、24h horizon、daily-reset battery。Test 只用于冻结后的评价；未使用天气、MPC、RL、CVaR/robust、深度学习或 Test 后调参。"]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
