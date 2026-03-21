"""Query population density within a radius of a coordinate."""

from __future__ import annotations

import math

from popcoord.core import validate_inputs
from popcoord.models import DensityResult


def density(
    lat: float,
    lon: float,
    radius_km: float,
    year: int = 2020,
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
    radius_km : float
        Search radius in kilometres.
    year : int, default 2020
        Reference year (2000–2020).
    backend : ``"raster"`` (default) | ``"api"``
        The ``"api"`` backend computes density from total population /
        circle area (less detailed).  The ``"raster"`` backend provides
        per-pixel min/max/mean.

    Returns
    -------
    DensityResult
        Contains ``.mean_density``, ``.max_density``, ``.min_density``,
        ``.total_population``, and ``.area_km2``.
    """
    validate_inputs(lat, lon, radius_km, year)

    if backend == "raster":
        from popcoord.sources.worldpop_cog import raster_density

        return raster_density(lat, lon, radius_km, year)
    elif backend == "api":
        # Fallback: get total pop via API and divide by circle area.
        from popcoord.sources.worldpop_api import api_population

        pop_result = api_population(lat, lon, radius_km, year)
        area_km2 = math.pi * radius_km ** 2
        mean_d = pop_result.total / area_km2 if area_km2 > 0 else 0.0

        return DensityResult(
            mean_density=mean_d,
            max_density=mean_d,   # can't distinguish at API level
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
    else:
        raise ValueError(f"Unknown backend {backend!r}. Use 'api' or 'raster'.")
