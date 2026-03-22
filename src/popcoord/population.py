"""Query total population within a radius of a coordinate."""

from __future__ import annotations

from typing import Optional

from popcoord.core import MAX_YEAR, MAX_YEAR_RASTER, GHSPOP_MAX_YEAR, validate_inputs
from popcoord.models import PopulationResult


def population(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    year: Optional[int] = None,
    *,
    backend: str = "api",
) -> PopulationResult:
    """Estimate the total population within *radius_km* of (*lat*, *lon*).

    Parameters
    ----------
    lat, lon : float
        WGS-84 decimal degrees. ``lat`` in [-90, 90], ``lon`` in [-180, 180].
        **These are the only required arguments.**
    radius_km : float, default 5.0
        Search radius in kilometres (must be > 0).
    year : int, optional
        Reference year. Defaults to the latest year available for the chosen
        backend. Passed years are clamped/snapped to the valid range:

        * ``"api"`` backend: 2000–2020
        * ``"raster"`` backend: 2000–2022 (2021–2022 use UN-adjusted mosaic)
        * ``"ghspop"`` backend: snapped to nearest 5-year epoch (1975–2030)
    backend : ``"api"`` | ``"raster"`` | ``"ghspop"``, default ``"api"``
        * ``"api"``: WorldPop REST API. Lightweight; needs only ``requests``.
        * ``"raster"``: WorldPop Cloud-Optimized GeoTIFFs. Needs ``rasterio``.
        * ``"ghspop"``: JRC GHS-POP 1975-2030. Needs ``rasterio``.
          Extends coverage back to 1975 (per decade before 2000).
          2025 and 2030 epochs are modelled projections.

    Returns
    -------
    PopulationResult
    """
    if year is None:
        if backend == "ghspop":
            year = GHSPOP_MAX_YEAR
        elif backend == "raster":
            year = MAX_YEAR_RASTER
        else:
            year = MAX_YEAR

    validate_inputs(lat, lon, radius_km, year)

    if backend == "api":
        from popcoord.sources.worldpop_api import api_population

        return api_population(lat, lon, radius_km, year)
    elif backend == "raster":
        from popcoord.sources.worldpop_cog import raster_population

        return raster_population(lat, lon, radius_km, year)
    elif backend == "ghspop":
        from popcoord.sources.ghspop_cog import ghspop_population

        return ghspop_population(lat, lon, radius_km, year)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'api', 'raster', or 'ghspop'."
        )
