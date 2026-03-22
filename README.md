# popcoord

[![PyPI](https://img.shields.io/pypi/v/popcoord)](https://pypi.org/project/popcoord/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/popcoord/popcoord/actions/workflows/ci.yml/badge.svg)](https://github.com/popcoord/popcoord/actions/workflows/ci.yml)

Query population, demographics, and density for any coordinate + radius on Earth.

```python
import popcoord

# Only lat and lon are required; everything else has sensible defaults
pop = popcoord.population(52.37, 4.90)   # Amsterdam, 5 km radius, latest year
```

## Install

```bash
pip install popcoord                # API + GHS-POP backends (lightweight)
pip install popcoord[raster]        # + WorldPop raster backend (adds rasterio)
```

## Quick Start

```python
import popcoord

# Minimal: just coordinates; defaults to 5 km radius, latest available year
pop = popcoord.population(52.37, 4.90)
print(pop.total)        # ~450,000
print(pop.year)         # 2020
print(pop.radius_km)    # 5.0

# Age × sex breakdown (18 age groups, male/female split)
demo = popcoord.demographics(51.51, -0.13)   # London
print(demo.male, demo.female)
print(demo.sex_ratio)          # male / female
print(demo.dependency_ratio)   # (0–14 + 65+) / 15–64
print(demo.median_age_bucket)  # e.g. '35_39'
print(demo.summary())          # full printable breakdown

# Access individual age cohorts
for label, ag in demo.age_groups.items():
    print(f"{label}: total={ag.total:.0f}, m={ag.male:.0f}, f={ag.female:.0f}")

# Population density (persons/km²)
d = popcoord.density(40.71, -74.01)   # New York
print(d.mean_density, d.max_density)

# Historical population back to 1975 via GHS-POP (any year snapped to nearest epoch)
hist = popcoord.population(39.91, 116.39, year=1980, backend="ghspop")  # Beijing
print(f"Beijing 1980: {hist.total:,.0f}")   # year was snapped to 1980
```

📓 **See [demo.ipynb](demo.ipynb) for comprehensive examples** including city comparisons, historical trends back to 1975, and backend comparisons.

## Functions

| Function | Returns | Description |
| --- | --- | --- |
| `population()` | `PopulationResult` | Total headcount in radius |
| `demographics()` | `DemographicResult` | Male/female totals + 18 five-year age groups |
| `density()` | `DensityResult` | Mean / max / min persons per km² |

## Parameters

`lat` and `lon` are the only **required** arguments. Everything else is optional:

| Parameter | Type | Valid Values | Default | Description |
| --- | --- | --- | --- | --- |
| `lat` | `float` | `-90` to `90` | **required** | Latitude (WGS-84 decimal degrees) |
| `lon` | `float` | `-180` to `180` | **required** | Longitude (WGS-84 decimal degrees) |
| `radius_km` | `float` | `> 0` | `5.0` | Search radius in kilometres |
| `year` | `int` | see Year Ranges | latest for backend | Reference year; clamped/snapped automatically |
| `backend` | `str` | `"api"`, `"raster"`, `"ghspop"` | `"api"` † | Data source backend |

† `density()` defaults to `"raster"` for pixel-level min/max/mean.

## Year Ranges

Year coverage differs by function and backend. Out-of-range years are automatically clamped or snapped.

| Function | `"api"` | `"raster"` | `"ghspop"` |
| --- | --- | --- | --- |
| `population()` | 2000–2020 | 2000–2022 ‡ | **1975–2030** § |
| `demographics()` | 2000–2020 | 2000–2020 | not supported |
| `density()` | 2000–2020 | 2000–2022 ‡ | **1975–2030** § |

‡ 2021–2022 use the UN-adjusted mosaic; age-sex at these years uses a different schema and is not supported.  
§ GHS-POP epochs are every 5 years (1975, 1980, …, 2020, 2025, 2030). Any year is snapped to the nearest epoch. 2025 and 2030 are modelled projections; 1975–2020 are calibrated estimates.

## Backends

| Backend | Install | Year range | Best for |
| --- | --- | --- | --- |
| `"api"` (default) | `pip install popcoord` | 2000–2020 | Quick queries, no extra dependencies |
| `"raster"` | `pip install popcoord[raster]` | 2000–2022 | Pixel-level detail (min/max/mean density) |
| `"ghspop"` | `pip install popcoord[raster]` | **1975–2030** | Historical & projected population |

## Age groups

18 five-year cohorts are available in `DemographicResult.age_groups`:

`0_1`, `1_4`, `5_9`, `10_14`, `15_19`, `20_24`, `25_29`, `30_34`, `35_39`, `40_44`, `45_49`, `50_54`, `55_59`, `60_64`, `65_69`, `70_74`, `75_79`, `80_plus`

Each age group returns an `AgeGroup` object with `.total`, `.male`, and `.female` attributes.

## Data Sources

### WorldPop (`"api"` and `"raster"` backends)
- **Source:** [worldpop.org](https://www.worldpop.org/) (CC BY 4.0)
- **Resolution:** ~1 km (30 arc-seconds) global mosaics
- **Population raster:** 2000–2020 unconstrained + 2021–2022 UN-adjusted mosaics
- **Demographics raster:** 2000–2020 (18 age-sex bands)

### JRC GHS-POP (`"ghspop"` backend)
- **Source:** [JRC Global Human Settlement Layer](https://ghsl.jrc.ec.europa.eu/) (European Commission open-data licence)
- **Dataset:** GHS_POP_GLOBE_R2023A (WGS84, 30 arc-second / ~1 km)
- **Epochs:** 1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030
- **Note:** Total population only (no age/sex breakdown). 2025 and 2030 are modelled projections.
- **Access:** Tile ZIPs (~1–5 MB each) downloaded on demand; only tiles covering the query area are fetched.
