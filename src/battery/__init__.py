"""Battery peak-shaving models used by Phase 5."""

from .model import BatteryConfig
from .optimizer import DailyDispatchResult, optimize_day

__all__ = ["BatteryConfig", "DailyDispatchResult", "optimize_day"]
