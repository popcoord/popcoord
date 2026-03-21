"""Query age-sex demographics within a radius of a coordinate."""

from __future__ import annotations

from typing import Optional

from popcoord.core import MAX_YEAR, validate_inputs
from popcoord.models import DemographicResult


def demographics(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
    year: Optional[int] = None,
    *,
    backend: str = "api",
) -> DemographicResult:
    """Estimate the age-sex breakdown of the population within *radius_km*
    of (*lat*, *lon*).

    Parameters
    ----------
    lat, lon : float
        WGS-84 decimal degrees. ``lat`` in [-90, 90], ``lon`` in [-180, 180].
        **These are the only required arguments.**
    radius_km : float, default 5.0
        Search radius in kilometres (must be > 0).
    year : int, optional
        Reference year. Defaults to 2020 (latest available). Both backends
        cover 2000–2020; values outside this range are clamped.

        Note: WorldPop 2021–2022 age-sex rasters use a different band schema
        (21 bands vs. 18) and are not merged into this series.
    backend : ``"api"`` | ``"raster"``, default ``"api"``
        * ``"api"`` — single HTTP request to WorldPop stats API.
        * ``"raster"`` — reads 36 COG rasters (one per sex × age group).
          More reliable but slower.

        GHS-POP does not provide age/sex breakdowns; use ``population()``
        with ``backend='ghspop'`` for historical total-population queries.

    Returns
    -------
    DemographicResult
        Contains ``.total``, ``.male``, ``.female``, ``.age_groups`` dict,
        plus convenience properties like ``.sex_ratio``,
        ``.dependency_ratio``, and ``.median_age_bucket``.
    """
    if year is None:
        year = MAX_YEAR

    validate_inputs(lat, lon, radius_km, year)

    if backend == "api":
        from popcoord.sources.worldpop_api import api_demographics

        return api_demographics(lat, lon, radius_km, year)
    elif backend == "raster":
        from popcoord.sources.worldpop_cog import raster_demographics

        return raster_demographics(lat, lon, radius_km, year)
    elif backend == "ghspop":
        raise ValueError(
            "GHS-POP does not provide age-sex data. "
            "Use backend='api' or backend='raster' for demographics."
        )
    else:
        raise ValueError(f"Unknown backend {backend!r}. Use 'api' or 'raster'.")
