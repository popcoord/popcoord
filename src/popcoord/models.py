"""Result types returned by popcoord queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PopulationResult:
    """Total population estimate within the queried area.

    Attributes
    ----------
    total : float
        Estimated number of people.
    year : int
        Reference year of the estimate.
    lat : float
        Query latitude.
    lon : float
        Query longitude.
    radius_km : float
        Query radius in kilometres.
    backend : str
        Backend used (``"api"`` or ``"raster"``).
    source : str
        Data source description.
    """

    total: float
    year: int
    lat: float
    lon: float
    radius_km: float
    backend: str = "api"
    source: str = "WorldPop"

    def __repr__(self) -> str:
        return (
            f"PopulationResult(total={self.total:,.0f}, year={self.year}, "
            f"radius_km={self.radius_km}, backend={self.backend!r})"
        )


@dataclass
class AgeGroup:
    """Population count for a single 5-year age cohort.

    Attributes
    ----------
    label : str
        Human-readable label, e.g. ``"0_1"``, ``"5_9"``, ``"80_plus"``.
    total : float
        Male + female count for this age group.
    male : float
        Male count.
    female : float
        Female count.
    """

    label: str
    total: float
    male: float
    female: float

    def __repr__(self) -> str:
        return (
            f"AgeGroup({self.label!r}, total={self.total:,.0f}, "
            f"m={self.male:,.0f}, f={self.female:,.0f})"
        )


@dataclass
class DemographicResult:
    """Full age-sex breakdown for the queried area.

    Attributes
    ----------
    total : float
        Estimated total population (sum of all cohorts).
    male : float
        Total male population.
    female : float
        Total female population.
    age_groups : dict[str, AgeGroup]
        Mapping from age-group label to :class:`AgeGroup`.
        Keys: ``"0_1"``, ``"1_4"``, ``"5_9"``, ``"10_14"``, …, ``"80_plus"``.
    year : int
        Reference year.
    lat, lon, radius_km : float
        Original query parameters.
    backend : str
        Backend used.
    source : str
        Data source description.
    """

    total: float
    male: float
    female: float
    age_groups: Dict[str, AgeGroup] = field(default_factory=dict)
    year: int = 2020
    lat: float = 0.0
    lon: float = 0.0
    radius_km: float = 0.0
    backend: str = "api"
    source: str = "WorldPop"

    # ---- Convenience helpers ------------------------------------------------

    @property
    def sex_ratio(self) -> Optional[float]:
        """Male-to-female ratio, or *None* if female count is zero."""
        return self.male / self.female if self.female > 0 else None

    @property
    def dependency_ratio(self) -> Optional[float]:
        """(Age 0-14 + 65+) / (Age 15-64), or *None* if working-age is zero.

        A common demographic indicator: values > 0.5 indicate a large
        dependent population relative to the working-age population.
        """
        young = 0.0
        working = 0.0
        old = 0.0
        _young_labels = {"0_1", "1_4", "5_9", "10_14"}
        _old_labels = {"65_69", "70_74", "75_79", "80_plus"}
        for label, ag in self.age_groups.items():
            if label in _young_labels:
                young += ag.total
            elif label in _old_labels:
                old += ag.total
            else:
                working += ag.total
        return (young + old) / working if working > 0 else None

    @property
    def median_age_bucket(self) -> Optional[str]:
        """Label of the age group that contains the median person."""
        if not self.age_groups:
            return None
        half = self.total / 2.0
        cumulative = 0.0
        for label, ag in self.age_groups.items():
            cumulative += ag.total
            if cumulative >= half:
                return label
        return None

    def summary(self) -> str:
        """Return a human-readable multi-line summary."""
        lines = [
            f"Demographics: {self.radius_km} km around ({self.lat}, {self.lon}), year {self.year}",
            f"  Total population : {self.total:>12,.0f}",
            f"  Male             : {self.male:>12,.0f}",
            f"  Female           : {self.female:>12,.0f}",
        ]
        if self.sex_ratio is not None:
            lines.append(f"  Sex ratio (M/F)  : {self.sex_ratio:>12.3f}")
        if self.dependency_ratio is not None:
            lines.append(f"  Dependency ratio : {self.dependency_ratio:>12.3f}")
        if self.median_age_bucket is not None:
            lines.append(f"  Median age bucket: {self.median_age_bucket:>12s}")
        if self.age_groups:
            lines.append("  Age groups:")
            for label, ag in self.age_groups.items():
                pct = (ag.total / self.total * 100) if self.total > 0 else 0
                lines.append(
                    f"    {label:>8s}: {ag.total:>10,.0f}  "
                    f"(m={ag.male:>10,.0f}  f={ag.female:>10,.0f})  "
                    f"{pct:5.1f}%"
                )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"DemographicResult(total={self.total:,.0f}, "
            f"male={self.male:,.0f}, female={self.female:,.0f}, "
            f"age_groups={len(self.age_groups)}, year={self.year})"
        )


@dataclass
class DensityResult:
    """Population density estimate for the queried area.

    Attributes
    ----------
    mean_density : float
        Mean persons per km² across the circular query area.
    max_density : float
        Maximum pixel-level density within the area.
    min_density : float
        Minimum pixel-level density (excluding nodata).
    total_population : float
        Sum of population within the area (same as PopulationResult.total).
    area_km2 : float
        Approximate area of the search circle (π r²).
    year : int
        Reference year.
    lat, lon, radius_km : float
        Original query parameters.
    backend : str
        Backend used.
    source : str
        Data source.
    """

    mean_density: float
    max_density: float
    min_density: float
    total_population: float
    area_km2: float
    year: int = 2020
    lat: float = 0.0
    lon: float = 0.0
    radius_km: float = 0.0
    backend: str = "raster"
    source: str = "WorldPop"

    def __repr__(self) -> str:
        return (
            f"DensityResult(mean={self.mean_density:,.1f} ppl/km², "
            f"total={self.total_population:,.0f}, year={self.year})"
        )
