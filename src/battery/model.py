"""Battery configuration and derived energy/power limits."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class BatteryConfig:
    """Hourly BESS parameters.

    Source load is hourly energy (kWh per one-hour interval). Numerically,
    charge/discharge are both kWh per interval and average kW; SOC is kWh.
    """

    name: str
    capacity: float
    max_charge_power: float
    max_discharge_power: float
    soc_min_fraction: float = 0.10
    soc_max_fraction: float = 0.90
    initial_soc_fraction: float = 0.50
    terminal_soc_fraction: float = 0.50
    eta_charge: float = sqrt(0.9)
    eta_discharge: float = sqrt(0.9)
    throughput_penalty: float = 1e-6

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.max_charge_power <= 0 or self.max_discharge_power <= 0:
            raise ValueError("Battery capacity and power limits must be positive")
        fractions = (self.soc_min_fraction, self.soc_max_fraction, self.initial_soc_fraction, self.terminal_soc_fraction)
        if not all(0.0 <= value <= 1.0 for value in fractions):
            raise ValueError("SOC fractions must lie in [0, 1]")
        if self.soc_min_fraction > self.soc_max_fraction:
            raise ValueError("Minimum SOC cannot exceed maximum SOC")
        if not self.soc_min_fraction <= self.initial_soc_fraction <= self.soc_max_fraction:
            raise ValueError("Initial SOC must lie within the allowed SOC range")
        if not self.soc_min_fraction <= self.terminal_soc_fraction <= self.soc_max_fraction:
            raise ValueError("Terminal SOC must lie within the allowed SOC range")
        if not 0.0 < self.eta_charge <= 1.0 or not 0.0 < self.eta_discharge <= 1.0:
            raise ValueError("Efficiencies must lie in (0, 1]")
        if self.throughput_penalty < 0:
            raise ValueError("Throughput penalty cannot be negative")

    @property
    def soc_min(self) -> float:
        return self.capacity * self.soc_min_fraction

    @property
    def soc_max(self) -> float:
        return self.capacity * self.soc_max_fraction

    @property
    def initial_soc(self) -> float:
        return self.capacity * self.initial_soc_fraction

    @property
    def terminal_soc(self) -> float:
        return self.capacity * self.terminal_soc_fraction

    @property
    def round_trip_efficiency(self) -> float:
        return self.eta_charge * self.eta_discharge

    @classmethod
    def from_mean_train_load(cls, name: str, mean_train_load: float, capacity_fraction: float, throughput_penalty: float = 1e-6) -> "BatteryConfig":
        if mean_train_load <= 0 or capacity_fraction <= 0:
            raise ValueError("Mean train load and capacity fraction must be positive")
        capacity = 24.0 * float(mean_train_load) * float(capacity_fraction)
        return cls(name=name, capacity=capacity, max_charge_power=capacity / 4.0, max_discharge_power=capacity / 4.0, throughput_penalty=throughput_penalty)
