"""Query total population within a radius of a coordinate."""

from __future__ import annotations

from popcoord.core import validate_inputs
from popcoord.models import PopulationResult


def population(
    lat: float,
    lon: float,
    radius_km: float,
    year: int = 2020,
    *,
    backend: str = "api",
) -> PopulationResult:
    """Estimate the total population within *radius_km* of (*lat*, *lon*).

    Parameters
    ----------
    lat, lon : float
        WGS-84 decimal degrees.
    radius_km : float
        Search radius in kilometres.
    year : int, default 2020
        Reference year (WorldPop covers 2000–2020; values outside this
        range are clamped).
    backend : ``"api"`` | ``"raster"``, default ``"api"``
        * ``"api"`` — uses the WorldPop REST API (lightweight, needs
          only ``requests``).
        * ``"raster"`` — reads Cloud-Optimized GeoTIFFs via HTTP range
          requests (needs ``rasterio``).

    Returns
    -------
    PopulationResult
    """
    validate_inputs(lat, lon, radius_km, year)

    if backend == "api":
        from popcoord.sources.worldpop_api import api_population

        return api_population(lat, lon, radius_km, year)
    elif backend == "raster":
        from popcoord.sources.worldpop_cog import raster_population

        return raster_population(lat, lon, radius_km, year)
    else:
        raise ValueError(f"Unknown backend {backend!r}. Use 'api' or 'raster'.")
