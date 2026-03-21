"""Query population density within a radius of a coordinate."""

from __future__ import annotations

import math
from typing import Optional

from popcoord.core import MAX_YEAR, MAX_YEAR_RASTER, GHSPOP_MAX_YEAR, validate_inputs
from popcoord.models import DensityResult


def density(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    year: Optional[int] = None,
    *,
    backend: str = "raster",
) -> DensityResult:
    """Estimate population density within *radius_km* of (*lat*, *lon*).

    The density is derived from the per-pixel population raster: each 1 km²
    pixel value represents approximate persons in that cell, so it doubles
    as a density value.

    Parameters
    ----------
    lat, lon : float
        WGS-84 decimal degrees.
        **These are the only required arguments.**
    radius_km : float, default 5.0
        Search radius in kilometres (must be > 0).
    year : int, optional
        Reference year. Defaults to the latest available for the backend:
        2022 for ``"raster"``, 2020 for ``"api"`` and ``"ghspop"``.
    backend : ``"raster"`` (default) | ``"api"`` | ``"ghspop"``
        * ``"raster"`` — WorldPop COG; per-pixel min/max/mean density.
        * ``"api"`` — WorldPop REST API; mean density only (total / area).
        * ``"ghspop"`` — JRC GHS-POP 1975–2030; mean density only.

    Returns
    -------
    DensityResult
        Contains ``.mean_density``, ``.max_density``, ``.min_density``,
        ``.total_population``, and ``.area_km2``.
    """
    if year is None:
        if backend == "ghspop":
            year = GHSPOP_MAX_YEAR
        elif backend == "raster":
            year = MAX_YEAR_RASTER
        else:
            year = MAX_YEAR

    validate_inputs(lat, lon, radius_km, year)

    if backend == "raster":
        from popcoord.sources.worldpop_cog import raster_density

        return raster_density(lat, lon, radius_km, year)
    elif backend == "api":
        from popcoord.sources.worldpop_api import api_population

        pop_result = api_population(lat, lon, radius_km, year)
        area_km2 = math.pi * radius_km ** 2
        mean_d = pop_result.total / area_km2 if area_km2 > 0 else 0.0
        return DensityResult(
            mean_density=mean_d,
            max_density=mean_d,
            min_density=mean_d,
            total_population=pop_result.total,
            area_km2=area_km2,
            year=pop_result.year,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            backend="api",
            source="WorldPop REST API (derived)",
        )
    elif backend == "ghspop":
        from popcoord.sources.ghspop_cog import ghspop_population

        pop_result = ghspop_population(lat, lon, radius_km, year)
        area_km2 = math.pi * radius_km ** 2
        mean_d = pop_result.total / area_km2 if area_km2 > 0 else 0.0
        return DensityResult(
            mean_density=mean_d,
            max_density=mean_d,
            min_density=mean_d,
            total_population=pop_result.total,
            area_km2=area_km2,
            year=pop_result.year,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            backend="ghspop",
            source=pop_result.source,
        )
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'api', 'raster', or 'ghspop'."
        )
