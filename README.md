# popcoord

Query population, demographics, and density for any coordinate + radius on Earth.

Powered by [WorldPop](https://www.worldpop.org/) open data (CC BY 4.0).

## Install

```bash
pip install popcoord                # API backend (lightweight)
pip install popcoord[raster]        # + raster backend (adds rasterio)
```

## Quick Start

```python
import popcoord

# Total population within 10 km of Amsterdam
pop = popcoord.population(lat=52.38, lon=4.90, radius_km=10, year=2020)
print(pop.total)  # estimated headcount

# Age × sex breakdown (18 age groups, male/female split)
demo = popcoord.demographics(lat=52.38, lon=4.90, radius_km=10, year=2020)
print(demo.male, demo.female)
print(demo.sex_ratio)          # male / female
print(demo.dependency_ratio)   # (0-14 + 65+) / 15-64
print(demo.median_age_bucket)  # e.g. '35_39'
print(demo.summary())          # full printable breakdown

# Access individual age cohorts
for label, ag in demo.age_groups.items():
    print(f"{label}: total={ag.total:.0f}, m={ag.male:.0f}, f={ag.female:.0f}")

# Population density (persons/km²)
d = popcoord.density(lat=52.38, lon=4.90, radius_km=10, year=2020, backend="raster")
print(d.mean_density, d.max_density)
```

📓 **See [demo.ipynb](demo.ipynb) for comprehensive examples** including city comparisons, historical trends, and more.

## Functions

| Function | Returns | Description |
| --- | --- | --- |
| `population()` | `PopulationResult` | Total headcount in radius |
| `demographics()` | `DemographicResult` | Male/female totals + 18 five-year age groups |
| `density()` | `DensityResult` | Mean / max / min persons per km² |

## Parameters

All functions accept the following parameters:

| Parameter | Type | Valid Values | Default | Description |
| --- | --- | --- | --- | --- |
| `lat` | `float` | `-90` to `90` | *required* | Latitude in WGS-84 decimal degrees |
| `lon` | `float` | `-180` to `180` | *required* | Longitude in WGS-84 decimal degrees |
| `radius_km` | `float` | `> 0` | *required* | Search radius in kilometres |
| `year` | `int` | see below | `2020` | Reference year (clamped per function — see Year Ranges) |
| `backend` | `str` | `"api"` or `"raster"` | `"api"`* | Data source backend |

\* Note: `density()` defaults to `"raster"` backend for pixel-level detail.

## Year Ranges

Year coverage differs by function and backend:

| Function | `"api"` backend | `"raster"` backend |
| --- | --- | --- |
| `population()` | 2000–2020 | **2000–2022** (2021–2022 use UN-adjusted mosaic) |
| `demographics()` | 2000–2020 | 2000–2020 |
| `density()` | 2000–2020 | 2000–2020 |

Years outside the supported range for a given function/backend are automatically clamped to the nearest valid year. The 2021–2022 age-sex rasters use a different band schema (21 bands vs. 18) and are not yet merged into the demographics series.

## Backends

| Backend | Install | Best for |
| --- | --- | --- |
| `"api"` (default) | `pip install popcoord` | Quick queries, lightweight environments |
| `"raster"` | `pip install popcoord[raster]` | Pixel-level detail, offline caching |

## Age groups

18 five-year cohorts are available in `DemographicResult.age_groups`:

`0_1`, `1_4`, `5_9`, `10_14`, `15_19`, `20_24`, `25_29`, `30_34`, `35_39`, `40_44`, `45_49`, `50_54`, `55_59`, `60_64`, `65_69`, `70_74`, `75_79`, `80_plus`

Each age group returns an `AgeGroup` object with `.total`, `.male`, and `.female` attributes.

## Data

- **Source:** WorldPop open data (CC BY 4.0) — [worldpop.org](https://www.worldpop.org/)
- **Coverage:** Global
- **Resolution:** ~1 km (30 arc-seconds) — the maximum resolution for streamable global mosaics; 100 m rasters exist but only as per-country files with no global mosaic
- **Population (`"raster"` backend):** 2000–2022
  - 2000–2020: unconstrained global mosaic (`ppp_{year}_1km_Aggregated.tif`)
  - 2021–2022: UN-adjusted global mosaic (`global_ppp_{year}_1km_UNadj.tif`)
- **Demographics / density:** 2000–2020 (both backends)
- **Projections:** WorldPop publishes 2015–2030 projected data (R2025A release), but these are per-country files only with no streamable global mosaic — not currently supported
- **License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — please cite [worldpop.org](https://www.worldpop.org/)

## License

AGPL-3.0-or-later
