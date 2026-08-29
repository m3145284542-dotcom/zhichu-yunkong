# Processed data validation

- File: `data/processed/campus_hourly.csv`
- Shape: 17,544 rows × 10 columns
- Time range: 2016-01-01 00:00:00 to 2017-12-31 23:00:00 (source-local naive timestamps)
- Metadata timezone: Europe/London
- Timestamp order/duplicates/continuity: increasing, no duplicates, exactly one hour between rows
- Load unit: kWh
- Load min/mean/median/max: 2131.9218 / 5770.9082 / 5533.3589 / 9330.0514
- Missing/zero/negative load rows: 0 / 0 / 0
- IQR 1.5× flags: 76 (bounds 3317.4626 to 8150.8260); retained for review, not treated as proven errors
- Absolute z-score > 4 flags: 1; retained for review

## Weather missingness

| Field | Missing rows | Missing rate |
| --- | ---: | ---: |
| `airTemperature` | 29 | 0.1653% |
| `cloudCoverage` | 14,177 | 80.8083% |
| `dewTemperature` | 29 | 0.1653% |
| `precipDepth1HR` | 17,544 | 100.0000% |
| `precipDepth6HR` | 16,125 | 91.9118% |
| `seaLvlPressure` | 89 | 0.5073% |
| `windDirection` | 34 | 0.1938% |
| `windSpeed` | 28 | 0.1596% |

## Leakage and provenance checks

- Load is a same-hour sum only; no lag/lead, rolling window, random split, interpolation, or model feature was created.
- Missing building readings were not filled with zero; selected buildings have complete source coverage.
- Weather was filtered by metadata site_id and left-joined on the exact same local timestamp.
- Weather missing values remain missing; no past value was repaired with future data.
- Raw source names, byte sizes, SHA-256 hashes, selected site/buildings, timezone, unit, and policies are recorded in the processed manifest.
