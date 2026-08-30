"""Scenario-based 24-hour battery peak-shaving with a CVaR objective."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from .model import BatteryConfig


@dataclass(frozen=True)
class RobustDailyDispatchResult:
    charge: np.ndarray
    discharge: np.ndarray
    soc: np.ndarray
    scenario_grid_load: np.ndarray
    scenario_peaks: np.ndarray
    expected_peak: float
    cvar_peak: float
    cvar_eta: float
    objective_value: float
    solver_status: str
    success: bool
    message: str


def empirical_cvar(values: np.ndarray, alpha: float) -> tuple[float, float]:
    """Return the exact finite-sample CVaR LP value and a minimizing eta."""
    samples = np.asarray(values, dtype=float)
    if samples.ndim != 1 or samples.size == 0 or not np.isfinite(samples).all():
        raise ValueError("values must be a non-empty finite vector")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    candidates = np.unique(samples)
    objectives = np.array(
        [eta + np.maximum(samples - eta, 0.0).mean() / (1.0 - alpha) for eta in candidates]
    )
    best = int(np.argmin(objectives))
    return float(objectives[best]), float(candidates[best])


def optimize_robust_day(
    scenario_loads: np.ndarray,
    config: BatteryConfig,
    *,
    alpha: float = 0.90,
    risk_lambda: float = 1.0,
) -> RobustDailyDispatchResult:
    """Optimize one common dispatch against load scenarios.

    The objective is mean(scenario peak) + lambda * CVaR_alpha(scenario peak)
    plus the same Phase 5 throughput tie-break penalty.
    """
    scenarios = np.asarray(scenario_loads, dtype=float)
    if scenarios.ndim != 2 or scenarios.shape[1] != 24 or scenarios.shape[0] < 1:
        raise ValueError("scenario_loads must have shape (n_scenarios, 24)")
    if not np.isfinite(scenarios).all():
        raise ValueError("scenario_loads must contain only finite values")
    if np.any(scenarios < 0.0):
        raise ValueError("scenario_loads must be nonnegative")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    if risk_lambda < 0.0:
        raise ValueError("risk_lambda must be nonnegative")

    n = 24
    n_scenarios = scenarios.shape[0]
    discharge_start = n
    soc_start = 2 * n
    peak_start = soc_start + n + 1
    eta_index = peak_start + n_scenarios
    excess_start = eta_index + 1
    mode_start = excess_start + n_scenarios
    n_variables = mode_start + n

    objective = np.zeros(n_variables)
    objective[:soc_start] = config.throughput_penalty
    objective[peak_start:eta_index] = 1.0 / n_scenarios
    objective[eta_index] = risk_lambda
    objective[excess_start:mode_start] = risk_lambda / ((1.0 - alpha) * n_scenarios)

    lower = np.full(n_variables, -np.inf)
    upper = np.full(n_variables, np.inf)
    lower[:discharge_start] = 0.0
    upper[:discharge_start] = config.max_charge_power
    lower[discharge_start:soc_start] = 0.0
    upper[discharge_start:soc_start] = config.max_discharge_power
    lower[soc_start:peak_start] = config.soc_min
    upper[soc_start:peak_start] = config.soc_max
    lower[peak_start:mode_start] = 0.0
    lower[mode_start:] = 0.0
    upper[mode_start:] = 1.0

    rows: list[np.ndarray] = []
    row_lower: list[float] = []
    row_upper: list[float] = []

    def add(coefficients: dict[int, float], lb: float, ub: float) -> None:
        row = np.zeros(n_variables)
        for index, coefficient in coefficients.items():
            row[index] = coefficient
        rows.append(row)
        row_lower.append(lb)
        row_upper.append(ub)

    add({soc_start: 1.0}, config.initial_soc, config.initial_soc)
    add({soc_start + n: 1.0}, config.terminal_soc, config.terminal_soc)
    for hour in range(n):
        add(
            {
                soc_start + hour + 1: 1.0,
                soc_start + hour: -1.0,
                hour: -config.eta_charge,
                discharge_start + hour: 1.0 / config.eta_discharge,
            },
            0.0,
            0.0,
        )
        add({hour: 1.0, mode_start + hour: -config.max_charge_power}, -np.inf, 0.0)
        add(
            {discharge_start + hour: 1.0, mode_start + hour: config.max_discharge_power},
            -np.inf,
            config.max_discharge_power,
        )

    for scenario in range(n_scenarios):
        peak_index = peak_start + scenario
        excess_index = excess_start + scenario
        for hour in range(n):
            add(
                {hour: 1.0, discharge_start + hour: -1.0, peak_index: -1.0},
                -np.inf,
                -scenarios[scenario, hour],
            )
        # peak_s - eta - excess_s <= 0
        add({peak_index: 1.0, eta_index: -1.0, excess_index: -1.0}, -np.inf, 0.0)

    integrality = np.zeros(n_variables, dtype=int)
    integrality[mode_start:] = 1
    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=LinearConstraint(np.vstack(rows), np.asarray(row_lower), np.asarray(row_upper)),
        options={"disp": False, "mip_rel_gap": 1e-9},
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"Robust daily battery MILP failed (status={result.status}): {result.message}")

    solution = np.asarray(result.x)
    solution[np.abs(solution) < 1e-9] = 0.0
    charge = solution[:discharge_start]
    discharge = solution[discharge_start:soc_start]
    soc = solution[soc_start:peak_start]
    scenario_grid = scenarios + charge[None, :] - discharge[None, :]
    scenario_peaks = scenario_grid.max(axis=1)
    cvar_peak, cvar_eta = empirical_cvar(scenario_peaks, alpha)
    expected_peak = float(scenario_peaks.mean())
    objective_value = (
        expected_peak
        + risk_lambda * cvar_peak
        + config.throughput_penalty * float(np.sum(charge) + np.sum(discharge))
    )
    return RobustDailyDispatchResult(
        charge=charge,
        discharge=discharge,
        soc=soc,
        scenario_grid_load=scenario_grid,
        scenario_peaks=scenario_peaks,
        expected_peak=expected_peak,
        cvar_peak=cvar_peak,
        cvar_eta=cvar_eta,
        objective_value=objective_value,
        solver_status=f"{result.status}: optimal",
        success=True,
        message=str(result.message),
    )
