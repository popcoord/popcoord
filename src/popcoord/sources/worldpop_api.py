"""WorldPop REST API backend.

Sends a GeoJSON polygon (circle) to the WorldPop stats API and parses the
JSON response.  No heavy geospatial dependencies required — only `requests`.

API docs: https://www.worldpop.org/sdi/advancedapi/

Datasets:
    wpgppop  — total population (2000–2020)
    wpgpas   — age-sex structures (2000–2020)
"""

from __future__ import annotations

import json
import time
import warnings
from typing import Any, Dict, Optional

import requests

from popcoord.core import AGE_CODES, AGE_LABELS, circle_geojson, clamp_year
from popcoord.models import AgeGroup, DemographicResult, DensityResult, PopulationResult

_BASE_URL = "https://api.worldpop.org/v1/services/stats"
_TIMEOUT = 120  # seconds


def _query_api(
    dataset: str,
    year: int,
    geojson: Dict[str, Any],
    runasync: bool = False,
) -> Dict[str, Any]:
    """Submit a stats query and return the parsed JSON response."""
    params = {
        "dataset": dataset,
        "year": str(year),
        "geojson": json.dumps(geojson),
        "runasync": str(runasync).lower(),
    }
    resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    # The API may return a task ID for async processing.
    if "taskid" in data and data.get("status") != "finished":
        task_url = data.get("url") or f"https://api.worldpop.org/v1/tasks/{data['taskid']}"
        for _ in range(60):
            time.sleep(2)
            poll = requests.get(task_url, timeout=_TIMEOUT)
            poll.raise_for_status()
            data = poll.json()
            if data.get("status") == "finished":
                break
        else:
            raise TimeoutError(
                f"WorldPop API task {data.get('taskid')} did not finish within timeout."
            )

    return data


# ---------------------------------------------------------------------------
# Public helpers called by the top-level functions
# ---------------------------------------------------------------------------

def api_population(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> PopulationResult:
    """Fetch total population via the WorldPop REST API."""
    year = clamp_year(year)
    geojson = circle_geojson(lat, lon, radius_km)

    data = _query_api("wpgppop", year, geojson)

    # Parse total from response
    total = _extract_total(data)
    return PopulationResult(
        total=total,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="api",
        source="WorldPop REST API (wpgppop)",
    )


def api_demographics(
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
) -> DemographicResult:
    """Fetch age-sex breakdown via the WorldPop REST API."""
    year = clamp_year(year)
    geojson = circle_geojson(lat, lon, radius_km)

    data = _query_api("wpgpas", year, geojson)

    # The API returns a dict with keys like "m_0", "f_0", "m_1", "f_1", etc.
    stats = data.get("data", data)  # response shape can vary

    age_groups: Dict[str, AgeGroup] = {}
    total_m = 0.0
    total_f = 0.0

    for code, label in AGE_CODES.items():
        m_key = f"m_{code}"
        f_key = f"f_{code}"
        m_val = _safe_float(stats, m_key)
        f_val = _safe_float(stats, f_key)
        ag = AgeGroup(label=label, total=m_val + f_val, male=m_val, female=f_val)
        age_groups[label] = ag
        total_m += m_val
        total_f += f_val

    return DemographicResult(
        total=total_m + total_f,
        male=total_m,
        female=total_f,
        age_groups=age_groups,
        year=year,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        backend="api",
        source="WorldPop REST API (wpgpas)",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_total(data: Dict[str, Any]) -> float:
    """Best-effort extraction of total population from API response JSON."""
    # Response format varies slightly; try common keys.
    for key in ("total_population", "totpop", "pop", "total"):
        if key in data:
            return float(data[key])
    # Nested under "data"
    inner = data.get("data", {})
    if isinstance(inner, dict):
        for key in ("total_population", "totpop", "pop", "total"):
            if key in inner:
                return float(inner[key])
    # If the response has individual age/sex keys, sum them.
    s = 0.0
    found = False
    for k, v in (inner if isinstance(inner, dict) else data).items():
        if k.startswith(("m_", "f_")):
            try:
                s += float(v)
                found = True
            except (TypeError, ValueError):
                pass
    if found:
        return s

    warnings.warn(
        f"Could not parse total population from API response keys: {list(data.keys())}. "
        "Returning 0.  You may want to switch to backend='raster'.",
        RuntimeWarning,
        stacklevel=3,
    )
    return 0.0


def _safe_float(d: Dict[str, Any], key: str) -> float:
    """Return ``d[key]`` as float, or 0.0 if missing / unparseable."""
    try:
        return float(d[key])
    except (KeyError, TypeError, ValueError):
        return 0.0
