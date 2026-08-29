# Building Data Genome Project 2 (BDG2)

## Official source and paper

- Official repository: <https://github.com/buds-lab/building-data-genome-project-2>
- Data descriptor: Clayton Miller et al., “The Building Data Genome Project 2, energy meter data from the ASHRAE Great Energy Predictor III competition,” *Scientific Data* 7, 368 (2020), <https://doi.org/10.1038/s41597-020-00712-x>
- The project uses only official repository files; no mirrors or republished copies are accepted by the download script.

## Scope and resolution

BDG2 contains non-residential whole-building meter data. The published data range is the two full calendar years 2016–2017 at hourly resolution. Timestamps are expressed in each site’s local time; the metadata `timezone` field identifies the site time zone.

Electricity readings are energy summed over each hour, in kWh (`kWh_sum` in the source documentation). They are not instantaneous kW demand. The cleaned electricity file has undergone the source project’s documented cleaning: additional outlier removal, removal of zero runs longer than 24 hours, and removal of zero readings in electricity meters. Missing cleaned values therefore must not be interpreted as zero consumption.

## Weather fields

The official weather documentation defines these possible fields. The processing script audits the actual CSV schema instead of assuming every field exists.

| Field | Meaning / unit |
| --- | --- |
| `timestamp` | Local date and time |
| `site_id` | Site identifier |
| `airTemperature` | Air temperature, °C |
| `cloudCoverage` | Cloud cover, oktas |
| `dewTemperature` | Dew-point temperature, °C |
| `precipDepth1HR` | One-hour precipitation depth, mm |
| `precipDepth6HR` | Six-hour precipitation depth, mm |
| `seaLvlPressure` | Mean sea-level pressure, mbar/hPa |
| `windDirection` | Direction from true north, degrees |
| `windSpeed` | Wind speed, m/s |

## License and attribution

The official repository includes the Creative Commons Attribution-ShareAlike 4.0 license text (CC BY-SA 4.0). Reuse must retain attribution, link the license, indicate modifications, and apply the ShareAlike condition where required. This project attributes the Building Data Genome Project 2 and cites the paper above. Users distributing the data or derivatives should review the repository license themselves; this note is not legal advice.

Official license: <https://github.com/buds-lab/building-data-genome-project-2/blob/master/LICENSE>

## Files used in this project

| Local path | Official repository path | Purpose |
| --- | --- | --- |
| `data/raw/metadata.csv` | `data/metadata/metadata.csv` | Building/site/use/area/time-zone metadata |
| `data/raw/weather.csv` | `data/weather/weather.csv` | Hourly site weather |
| `data/raw/electricity_cleaned.csv` | `data/meters/cleaned/electricity_cleaned.csv` | Cleaned hourly whole-building electricity |

No chilled-water, steam, gas, water, irrigation, hot-water, solar, or Kaggle meter file is downloaded or processed in stage two.

Raw files are immutable inputs. `scripts/download_bdg2.py` keeps an existing valid raw file, writes downloads through a temporary file, and creates a hash manifest. Derived campus data and its separate provenance manifest are written under `data/processed/`.

