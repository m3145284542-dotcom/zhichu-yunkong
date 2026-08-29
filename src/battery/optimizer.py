"""Small 24-hour battery peak-shaving MILP solved by SciPy/HiGHS."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from .model import BatteryConfig


@dataclass(frozen=True)
class DailyDispatchResult:
    charge: np.ndarray
    discharge: np.ndarray
    soc: np.ndarray
    optimized_forecast_grid_load: np.ndarray
    forecast_peak: float
    solver_status: str
    success: bool
    message: str


def optimize_day(load_forecast: np.ndarray, config: BatteryConfig) -> DailyDispatchResult:
    """Optimize one 24-hour schedule without access to realized future load."""
    forecast = np.asarray(load_forecast, dtype=float)
    if forecast.shape != (24,):
        raise ValueError("load_forecast must contain exactly 24 hourly values")
    if not np.isfinite(forecast).all():
        raise ValueError("load_forecast must contain only finite values")

    n = 24
    discharge_start = n
    soc_start = 2 * n
    peak_index = soc_start + n + 1
    mode_start = peak_index + 1
    n_variables = mode_start + n

    objective = np.zeros(n_variables)
    objective[:soc_start] = config.throughput_penalty
    objective[peak_index] = 1.0

    lower = np.full(n_variables, -np.inf)
    upper = np.full(n_variables, np.inf)
    lower[:discharge_start] = 0.0
    upper[:discharge_start] = config.max_charge_power
    lower[discharge_start:soc_start] = 0.0
    upper[discharge_start:soc_start] = config.max_discharge_power
    lower[soc_start:peak_index] = config.soc_min
    upper[soc_start:peak_index] = config.soc_max
    lower[peak_index] = 0.0
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
        # forecast + charge - discharge <= peak
        add({hour: 1.0, discharge_start + hour: -1.0, peak_index: -1.0}, -np.inf, -forecast[hour])
        # mode=1 permits charging; mode=0 permits discharging.
        add({hour: 1.0, mode_start + hour: -config.max_charge_power}, -np.inf, 0.0)
        add(
            {discharge_start + hour: 1.0, mode_start + hour: config.max_discharge_power},
            -np.inf,
            config.max_discharge_power,
        )

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
        raise RuntimeError(f"Daily battery MILP failed (status={result.status}): {result.message}")

    solution = np.asarray(result.x)
    solution[np.abs(solution) < 1e-9] = 0.0
    charge = solution[:discharge_start]
    discharge = solution[discharge_start:soc_start]
    soc = solution[soc_start:peak_index]
    forecast_grid = forecast + charge - discharge
    return DailyDispatchResult(
        charge=charge,
        discharge=discharge,
        soc=soc,
        optimized_forecast_grid_load=forecast_grid,
        forecast_peak=float(forecast_grid.max()),
        solver_status=f"{result.status}: optimal",
        success=True,
        message=str(result.message),
    )
