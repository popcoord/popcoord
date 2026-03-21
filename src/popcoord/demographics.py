"""Query age-sex demographics within a radius of a coordinate."""

from __future__ import annotations

from popcoord.core import validate_inputs
from popcoord.models import DemographicResult


def demographics(
    lat: float,
    lon: float,
    radius_km: float,
    year: int = 2020,
    *,
    backend: str = "api",
) -> DemographicResult:
    """Estimate the age-sex breakdown of the population within *radius_km*
    of (*lat*, *lon*).

    Parameters
    ----------
    lat, lon : float
        WGS-84 decimal degrees. ``lat`` in [-90, 90], ``lon`` in [-180, 180].
    radius_km : float
        Search radius in kilometres (must be > 0).
    year : int, default 2020
        Reference year. Both backends cover 2000–2020; values outside
        this range are clamped to 2020.

        Note: WorldPop does publish 2021–2022 age-sex rasters, but they
        use a different age-band schema (21 bands vs. 18) and cannot be
        merged with the 2000–2020 series transparently.
    backend : ``"api"`` | ``"raster"``, default ``"api"``
        * ``"api"`` — single HTTP request to WorldPop stats API.
        * ``"raster"`` — reads 36 COG rasters (one per sex × age group).
          More reliable but slower.

    Returns
    -------
    DemographicResult
        Contains ``.total``, ``.male``, ``.female``, ``.age_groups`` dict,
        plus convenience properties like ``.sex_ratio``,
        ``.dependency_ratio``, and ``.median_age_bucket``.

    Examples
    --------
    >>> demo = demographics(lat=51.51, lon=-0.13, radius_km=15, year=2020)
    >>> print(demo.male)
    4_567_890
    >>> print(demo.age_groups["20_24"])
    AgeGroup('20_24', total=456789, m=228000, f=228789)
    >>> print(demo.summary())
    """
    validate_inputs(lat, lon, radius_km, year)

    if backend == "api":
        from popcoord.sources.worldpop_api import api_demographics

        return api_demographics(lat, lon, radius_km, year)
    elif backend == "raster":
        from popcoord.sources.worldpop_cog import raster_demographics

        return raster_demographics(lat, lon, radius_km, year)
    else:
        raise ValueError(f"Unknown backend {backend!r}. Use 'api' or 'raster'.")
