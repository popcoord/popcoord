"""WorldPop Cloud Optimized GeoTIFF backend.

Reads only the spatial window needed via HTTP range requests — no full
file downloads.  Requires the ``rasterio`` optional dependency::

    pip install popcoord[raster]

Datasets (1 km global mosaics):
    Total population   2000–2020 — ppp_{year}_1km_Aggregated.tif
    Total population   2021–2022 — global_ppp_{year}_1km_UNadj.tif (UN-adjusted)
    Age/sex cohorts    2000–2020 — global_{sex}_{agegroup}_{year}_1km.tif
    Population density 2000–2020 — ppp_{year}_1km_Aggregated.tif (derived)

Note on resolution: WorldPop global mosaics are produced at 1 km (~30 arc-sec).
100 m per-country rasters exist but there is no streamable 100 m global mosaic.
"""

from __future__ import annotations

import math
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Tuple

import numpy as np

from popcoord.core import (
    AGE_CODES,
    AGE_LABELS,
    bounding_box,
    clamp_year,
    pixel_distances_km,
)
from popcoord.models import AgeGroup, DemographicResult, DensityResult, PopulationResult

try:
    import rasterio
    from rasterio.windows import Window, from_bounds

    _HAS_RASTERIO = True
except ImportError:
    _HAS_RASTERIO = False


# ---------------------------------------------------------------------------
# URL templates
# ---------------------------------------------------------------------------

# 2000-2020 unconstrained 1km total population mosaic
_POP_URL = (
    "/vsicurl/https://data.worldpop.org/GIS/Population/"
    "Global_2000_2020/{year}/0_Mosaicked/ppp_{year}_1km_Aggregated.tif"
)

# 2021-2022 UN-adjusted 1km total population mosaic
_POP_URL_2021_2022 = (
    "/vsicurl/https://data.worldpop.org/GIS/Population/"
    "Global_2021_2022_1km_UNadj/unconstrained/{year}/0_Mosaicked/"
    "global_ppp_{year}_1km_UNadj.tif"
)

# 2000-2020 age-sex 1km global mosaics (files live in global_mosaic_1km/ subdir)
_AGESEX_URL = (
    "/vsicurl/https://data.worldpop.org/GIS/AgeSex_structures/"
    "Global_2000_2020/{year}/0_Mosaicked/global_mosaic_1km/"
    "global_{sex}_{agegroup}_{year}_1km.tif"
)


def _require_rasterio() -> None:
    if not _HAS_RASTERIO:
        raise ImportError(
            "The raster backend requires rasterio.  "
            "Install it with:  pip install popcoord[raster]"
        )


def _rasterio_env() -> "rasterio.Env":
    """Return a rasterio Env configured for efficient COG HTTP reads."""
    return rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
        VSI_CACHE=True,
        VSI_CACHE_SIZE=10_000_000,
    )


def _read_window(
    url: str,
    lat: float,
    lon: float,
    radius_km: float,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Read a circular window from a COG and return (data, mask, distances).

    Returns ``(None, None, None)`` if the window falls entirely outside
    the raster extent.
    """
    south, north, west, east = bounding_box(lat, lon, radius_km)

    with _rasterio_env():
        with rasterio.open(url) as src:
            window = from_bounds(west, south, east, north, transform=src.transform)
            window = window.intersection(
                Window(0, 0, src.width, src.height)
            )
            if window.width <= 0 or window.height <= 0:
                return None, None, None

            data = src.read(1, window=window).astype(np.float64)
            nodata = src.nodata

            # Pixel-centre coordinates
            win_tf = src.window_transform(window)
            nrows, ncols = data.shape
            pixel_lons = win_tf.c + (np.arange(ncols) + 0.5) * win_tf.a
            pixel_lats = win_tf.f + (np.arange(nrows) + 0.5) * win_tf.e

            dists = pixel_distances_km(lat, lon, pixel_lats, pixel_lons)
            mask = dists <= radius_km
            if nodata is not None:
                mask &= data != nodata
            mask &= np.isfinite(data)
            mask &= data >= 0

    return data, mask, dists


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def raster_population(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> PopulationResult:
    """Total population from COG rasters.

    Supports 2000–2022.  Years 2021–2022 use the UN-adjusted mosaic
    (``Global_2021_2022_1km_UNadj``); earlier years use the standard
    unconstrained mosaic.  Years outside 2000–2022 are clamped.
    """
    _require_rasterio()
    from popcoord.core import MAX_YEAR_RASTER
    year = max(2000, min(MAX_YEAR_RASTER, year))

    if year >= 2021:
        url = _POP_URL_2021_2022.format(year=year)
        source = f"WorldPop COG (global_ppp_{year}_1km_UNadj.tif)"
    else:
        url = _POP_URL.format(year=year)
        source = f"WorldPop COG (ppp_{year}_1km_Aggregated.tif)"

    data, mask, _ = _read_window(url, lat, lon, radius_km)
    total = float(np.sum(data[mask])) if data is not None else 0.0

    return PopulationResult(
        total=total,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="raster",
        source=source,
    )


def raster_demographics(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> DemographicResult:
    """Age-sex breakdown from COG rasters.

    Fetches 36 rasters (18 age groups × male/female) concurrently via
    a thread pool, reducing wall time to roughly a single HTTP round-trip
    instead of 36 sequential ones.
    """
    _require_rasterio()
    year = clamp_year(year)

    # Build the full list of (sex, code) tasks up front.
    tasks = [
        (sex, code)
        for code in AGE_CODES
        for sex in ("m", "f")
    ]

    def _fetch(sex_code: Tuple[str, str]) -> Tuple[str, str, float]:
        sex, code = sex_code
        url = _AGESEX_URL.format(year=year, sex=sex, agegroup=code)
        try:
            data, mask, _ = _read_window(url, lat, lon, radius_km)
            val = float(np.sum(data[mask])) if data is not None else 0.0
        except Exception as exc:
            warnings.warn(
                f"Could not read age-sex raster {sex}_{code} for {year}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            val = 0.0
        return sex, code, val

    raw: Dict[Tuple[str, str], float] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch, t): t for t in tasks}
        for fut in as_completed(futures):
            sex, code, val = fut.result()
            raw[(sex, code)] = val

    age_groups: Dict[str, AgeGroup] = {}
    total_m = 0.0
    total_f = 0.0
    for code, label in AGE_CODES.items():
        m_val = raw.get(("m", code), 0.0)
        f_val = raw.get(("f", code), 0.0)
        ag = AgeGroup(label=label, total=m_val + f_val, male=m_val, female=f_val)
        age_groups[label] = ag
        total_m += m_val
        total_f += f_val

    return DemographicResult(
        total=total_m + total_f,
        male=total_m,
        female=total_f,
        age_groups=age_groups,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="raster",
        source="WorldPop COG (global age-sex mosaics)",
    )


def raster_density(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> DensityResult:
    """Population density derived from the total-population COG raster.

    Since WorldPop provides *persons per pixel* and each pixel is ~1 km²,
    the pixel value is approximately the density in persons/km².  We also
    compute the aggregate density as total_population / circle_area.

    Supports 2000–2022, matching ``raster_population``.
    """
    _require_rasterio()
    from popcoord.core import MAX_YEAR_RASTER
    year = max(2000, min(MAX_YEAR_RASTER, year))

    if year >= 2021:
        url = _POP_URL_2021_2022.format(year=year)
        source = f"WorldPop COG (global_ppp_{year}_1km_UNadj.tif)"
    else:
        url = _POP_URL.format(year=year)
        source = f"WorldPop COG (ppp_{year}_1km_Aggregated.tif)"

    data, mask, _ = _read_window(url, lat, lon, radius_km)

    if data is not None and np.any(mask):
        values = data[mask]
        total = float(np.sum(values))
        mean_d = float(np.mean(values))
        max_d = float(np.max(values))
        min_d = float(np.min(values))
    else:
        total = mean_d = max_d = min_d = 0.0

    area_km2 = math.pi * radius_km ** 2

    return DensityResult(
        mean_density=mean_d,
        max_density=max_d,
        min_density=min_d,
        total_population=total,
        area_km2=area_km2,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="raster",
        source=source,
    )
