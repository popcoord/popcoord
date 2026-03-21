"""WorldPop Cloud Optimized GeoTIFF backend.

Reads only the spatial window needed via HTTP range requests — no full
file downloads.  Requires the ``rasterio`` optional dependency::

    pip install popcoord[raster]

Datasets (1 km global mosaics, 2000–2020):
    Total population   — ppp_{year}_1km_Aggregated.tif
    Age/sex cohorts    — global_{sex}_{agegroup}_{year}_1km.tif
    Population density — ppp_{year}_1km_Aggregated.tif (derived)
"""

from __future__ import annotations

import math
import warnings
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

_POP_URL = (
    "/vsicurl/https://data.worldpop.org/GIS/Population/"
    "Global_2000_2020/{year}/0_Mosaicked/ppp_{year}_1km_Aggregated.tif"
)

_AGESEX_URL = (
    "/vsicurl/https://data.worldpop.org/GIS/AgeSex_structures/"
    "Global_2000_2020/{year}/0_Mosaicked/global_{sex}_{agegroup}_{year}_1km.tif"
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
    """Total population from COG rasters."""
    _require_rasterio()
    year = clamp_year(year)
    url = _POP_URL.format(year=year)

    data, mask, _ = _read_window(url, lat, lon, radius_km)
    total = float(np.sum(data[mask])) if data is not None else 0.0

    return PopulationResult(
        total=total,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="raster",
        source=f"WorldPop COG (ppp_{year}_1km_Aggregated.tif)",
    )


def raster_demographics(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> DemographicResult:
    """Age-sex breakdown from COG rasters.

    Downloads one raster per sex × age-group combination (36 total).
    Each raster is small (only the bounding-box window), but this
    still involves 36 HTTP round-trips.  Use ``backend="api"`` if
    speed is critical.
    """
    _require_rasterio()
    year = clamp_year(year)

    age_groups: Dict[str, AgeGroup] = {}
    total_m = 0.0
    total_f = 0.0

    for code, label in AGE_CODES.items():
        m_val = 0.0
        f_val = 0.0

        for sex, var in [("m", "m_val"), ("f", "f_val")]:
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
            if sex == "m":
                m_val = val
            else:
                f_val = val

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
    """
    _require_rasterio()
    year = clamp_year(year)
    url = _POP_URL.format(year=year)

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
        source=f"WorldPop COG (ppp_{year}_1km_Aggregated.tif)",
    )
