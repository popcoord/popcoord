"""JRC Global Human Settlement Layer — Population (GHS-POP) backend.

Downloads the relevant tile ZIP(s) from JRC's open-data server and reads
the population raster using rasterio MemoryFile.  Each tile ZIP is
~1–5 MB — only the tile(s) covering the query bounding box are fetched.
Requires the ``rasterio`` optional dependency::

    pip install popcoord[raster]

Dataset:   GHS_POP_GLOBE_R2023A (WGS84, 30 arc-second / ~1 km)
Epochs:    1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030
           2025 and 2030 are modelled projections; 1975–2020 are calibrated estimates.
Coverage:  Global (tiles over unpopulated ocean/polar areas may not exist)
License:   European Commission open-data licence (free reuse with attribution)
Source:    https://ghsl.jrc.ec.europa.eu/
"""

from __future__ import annotations

import io
import math
import warnings
import zipfile
from typing import List, Optional, Tuple

import numpy as np
import requests

from popcoord.core import bounding_box, pixel_distances_km
from popcoord.models import PopulationResult

try:
    import rasterio
    from rasterio.windows import Window, from_bounds

    _HAS_RASTERIO = True
except ImportError:
    _HAS_RASTERIO = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
    "GHS_POP_GLOBE_R2023A/"
    "GHS_POP_E{year}_GLOBE_R2023A_4326_30ss/V1-0/tiles/"
)

# Outer-boundary origins of the global raster, measured from actual tile data.
# These are the outer (not pixel-centre) north/west edges of the tile grid.
_GHS_LAT_TOP: float = 89.09958330   # outer north edge of tile row 1
_GHS_LON_LEFT: float = -180.00791664  # outer west edge of tile col 1
_TILE_DEG: float = 10.0              # each tile spans exactly 10 geographic degrees
_TILE_ROWS: int = 22                 # rows 1–22 (not all populated)
_TILE_COLS: int = 36                 # cols 1–36

# Available 5-year epochs.  2025 and 2030 are modelled projections.
GHSPOP_EPOCHS: List[int] = [
    1975, 1980, 1985, 1990, 1995,
    2000, 2005, 2010, 2015, 2020,
    2025, 2030,
]
GHSPOP_MIN_YEAR: int = 1975
GHSPOP_MAX_YEAR: int = 2020  # latest *observed* epoch; 2025/2030 are projections

_REQUEST_TIMEOUT: int = 60  # seconds per tile


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_rasterio() -> None:
    if not _HAS_RASTERIO:
        raise ImportError(
            "The ghspop backend requires rasterio.  "
            "Install it with:  pip install popcoord[raster]"
        )


def snap_epoch(year: int) -> int:
    """Round *year* to the nearest GHS-POP epoch (1975, 1980, …, 2030).

    Examples
    --------
    >>> snap_epoch(1982)
    1980
    >>> snap_epoch(2021)
    2020
    >>> snap_epoch(2023)
    2025
    """
    return min(GHSPOP_EPOCHS, key=lambda e: abs(e - year))


def _tile_for_coord(lat: float, lon: float) -> Tuple[int, int]:
    """Return *(row, col)* of the tile that contains the point (*lat*, *lon*)."""
    col = math.floor((lon - _GHS_LON_LEFT) / _TILE_DEG) + 1
    row = math.floor((_GHS_LAT_TOP - lat) / _TILE_DEG) + 1
    col = max(1, min(_TILE_COLS, col))
    row = max(1, min(_TILE_ROWS, row))
    return row, col


def _tiles_for_bbox(
    south: float, north: float, west: float, east: float
) -> List[Tuple[int, int]]:
    """Return all *(row, col)* tiles that overlap the given bounding box."""
    row_n, col_w = _tile_for_coord(north, west)
    row_s, col_e = _tile_for_coord(south, east)
    return [
        (r, c)
        for r in range(row_n, row_s + 1)
        for c in range(col_w, col_e + 1)
    ]


def _fetch_tile(
    row: int, col: int, year: int
) -> Optional["rasterio.MemoryFile"]:
    """Download a GHS-POP tile ZIP and return it as a ``rasterio.MemoryFile``.

    Returns ``None`` if the tile doesn't exist (ocean / uninhabited area).
    Raises for network errors other than 404.
    """
    tile_name = (
        f"GHS_POP_E{year}_GLOBE_R2023A_4326_30ss_V1_0_R{row}_C{col}.zip"
    )
    url = _BASE_URL.format(year=year) + tile_name
    resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    tif_name = tile_name.replace(".zip", ".tif")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(tif_name) as f:
            return rasterio.MemoryFile(f.read())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ghspop_population(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> PopulationResult:
    """Total population from GHS-POP tiles.

    *year* is snapped to the nearest 5-year epoch.  Tiles over unpopulated
    areas (ocean, ice sheets) may not exist and are silently skipped.
    """
    _require_rasterio()

    epoch = snap_epoch(year)
    south, north, west, east = bounding_box(lat, lon, radius_km)
    tiles = _tiles_for_bbox(south, north, west, east)

    total = 0.0
    for t_row, t_col in tiles:
        memfile = _fetch_tile(t_row, t_col, epoch)
        if memfile is None:
            continue

        with memfile:
            with memfile.open() as src:
                window = from_bounds(
                    west, south, east, north, transform=src.transform
                )
                window = window.intersection(
                    Window(0, 0, src.width, src.height)
                )
                if window.width <= 0 or window.height <= 0:
                    continue

                data = src.read(1, window=window).astype(np.float64)
                nodata = src.nodata

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

                total += float(np.sum(data[mask]))

    return PopulationResult(
        total=total,
        year=epoch,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="ghspop",
        source=f"JRC GHS-POP R2023A (epoch {epoch}, 30 arc-sec / ~1 km)",
    )
