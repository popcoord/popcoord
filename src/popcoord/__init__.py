"""
popcoord: Query population & demographics for any coordinate + radius on Earth.

Uses WorldPop open data (https://www.worldpop.org/).  Two backends:

* **api** (default): lightweight, uses WorldPop REST API, needs only `requests`.
* **raster**: reads Cloud-Optimized GeoTIFFs via HTTP range requests, needs `rasterio`.

Quick start
-----------
>>> import popcoord
>>> result = popcoord.population(lat=52.37, lon=4.90, radius_km=10, year=2020)
>>> print(result)
PopulationResult(total=1_234_567, year=2020, ...)

>>> demo = popcoord.demographics(lat=52.37, lon=4.90, radius_km=10, year=2020)
>>> print(demo.male)
612345
>>> print(demo.age_groups["20_24"])
AgeGroup(total=98765, male=49000, female=49765)
"""

from popcoord.models import (
    AgeGroup,
    DemographicResult,
    DensityResult,
    PopulationResult,
)
from popcoord.population import population
from popcoord.demographics import demographics
from popcoord.density import density

__version__ = "0.1.0"
__all__ = [
    "population",
    "demographics",
    "density",
    "PopulationResult",
    "DemographicResult",
    "DensityResult",
    "AgeGroup",
]
