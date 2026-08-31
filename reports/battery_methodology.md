# Battery methodology and unit semantics

The source BDG2 electricity meter field is energy accumulated over each hourly interval, measured in kWh. For dispatch, the interval-average load power is

`P_t [kW] = E_t [kWh] / Δt [h]`.

All evaluated intervals have `Δt = 1 h`; therefore the values are numerically unchanged after conversion, but their dispatch interpretation is interval-average kW. Battery capacity and state of charge are kWh. Charge and discharge limits are kW; per-step charged and discharged energy are kWh and equal the corresponding average-kW values only because the interval is one hour.

Decision regret and peak reduction are power-peak metrics. Battery throughput is an energy metric. Peak shaving must not be interpreted as reduced total electricity use, reduced cost, or reduced emissions because those outcomes are not modeled.
