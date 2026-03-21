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
| `year` | `int` | `2000` to `2020` | `2020` | Reference year (values outside range are clamped) |
| `backend` | `str` | `"api"` or `"raster"` | `"api"`* | Data source backend |

\* Note: `density()` defaults to `"raster"` backend for pixel-level detail.

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

- **Source:** WorldPop unconstrained global mosaics (~1 km resolution)
- **Coverage:** Global, years 2000–2020
- **License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — please cite [worldpop.org](https://www.worldpop.org/)

## License

AGPL-3.0-or-later
