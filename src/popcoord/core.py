"""Shared geometry helpers used across popcoord."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0

# WorldPop global mosaic year range
MIN_YEAR = 2000
MAX_YEAR = 2020       # API backend + demographics raster
MAX_YEAR_RASTER = 2022  # Population raster extended with 2021-2022 UN-adj mosaics

# GHS-POP 5-year epochs (1975–2020 observed; 2025/2030 projected)
GHSPOP_EPOCHS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, 2030]
GHSPOP_MIN_YEAR = 1975
GHSPOP_MAX_YEAR = 2020  # default to latest *observed* epoch

# Age-group codes used by WorldPop and their human-readable labels.
# Keys are the WorldPop filename codes; values are our canonical labels.
AGE_CODES: Dict[str, str] = {
    "0":  "0_1",
    "1":  "1_4",
    "5":  "5_9",
    "10": "10_14",
    "15": "15_19",
    "20": "20_24",
    "25": "25_29",
    "30": "30_34",
    "35": "35_39",
    "40": "40_44",
    "45": "45_49",
    "50": "50_54",
    "55": "55_59",
    "60": "60_64",
    "65": "65_69",
    "70": "70_74",
    "75": "75_79",
    "80": "80_plus",
}

# Ordered list of canonical labels (youngest → oldest).
AGE_LABELS: List[str] = list(AGE_CODES.values())

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_inputs(
    lat: float, lon: float, radius_km: float, year: int
) -> None:
    """Raise ``ValueError`` for out-of-range inputs."""
    if not (-90 <= lat <= 90):
        raise ValueError(f"lat must be in [-90, 90], got {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"lon must be in [-180, 180], got {lon}")
    if radius_km <= 0:
        raise ValueError(f"radius_km must be positive, got {radius_km}")
    if not isinstance(year, int) or year < 1900 or year > 2100:
        raise ValueError(f"year looks unreasonable: {year}")


def clamp_year(year: int) -> int:
    """Clamp *year* to the WorldPop global-mosaic range [2000, 2020]."""
    return max(MIN_YEAR, min(MAX_YEAR, year))


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points (decimal degrees)."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def pixel_distances_km(
    lat_center: float,
    lon_center: float,
    lats: np.ndarray,
    lons: np.ndarray,
) -> np.ndarray:
    """Vectorised Haversine: distance from a centre to a 2-D grid of lat/lons.

    Returns a 2-D array of shape ``(len(lats), len(lons))`` in kilometres.
    """
    lat1 = np.radians(lat_center)
    lon1 = np.radians(lon_center)
    lat2 = np.radians(lats)[:, None]
    lon2 = np.radians(lons)[None, :]

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def bounding_box(
    lat: float, lon: float, radius_km: float, buffer: float = 1.15
) -> Tuple[float, float, float, float]:
    """Return ``(south, north, west, east)`` bounding the search circle.

    *buffer* adds a safety margin (default 15 %) so that no edge pixels
    are accidentally clipped.
    """
    deg_lat = radius_km / 111.0 * buffer
    deg_lon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01)) * buffer

    south = max(lat - deg_lat, -90.0)
    north = min(lat + deg_lat, 90.0)
    west = lon - deg_lon
    east = lon + deg_lon
    return south, north, west, east


def circle_geojson(
    lat: float, lon: float, radius_km: float, n_points: int = 64
) -> Dict[str, Any]:
    """Return a GeoJSON Polygon approximating a circle on the sphere.

    Used with the WorldPop REST API which accepts GeoJSON geometry.
    """
    coords = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        # Destination point given distance and bearing from start
        d = radius_km / EARTH_RADIUS_KM
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d)
            + math.cos(lat1) * math.sin(d) * math.cos(angle)
        )
        lon2 = lon1 + math.atan2(
            math.sin(angle) * math.sin(d) * math.cos(lat1),
            math.cos(d) - math.sin(lat1) * math.sin(lat2),
        )
        coords.append([math.degrees(lon2), math.degrees(lat2)])

    coords.append(coords[0])  # close the ring
    return {"type": "Polygon", "coordinates": [coords]}
