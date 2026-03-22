"""Tests for popcoord: core helpers and model objects."""

import math
import pytest

from popcoord.core import (
    AGE_CODES,
    AGE_LABELS,
    bounding_box,
    circle_geojson,
    clamp_year,
    haversine_km,
    pixel_distances_km,
    validate_inputs,
)
from popcoord.models import AgeGroup, DemographicResult, DensityResult, PopulationResult

import numpy as np


# ---------------------------------------------------------------------------
# core.py tests
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_inputs(self):
        validate_inputs(52.0, 4.0, 10.0, 2020)  # should not raise

    def test_bad_lat(self):
        with pytest.raises(ValueError, match="lat"):
            validate_inputs(95.0, 4.0, 10.0, 2020)

    def test_bad_lon(self):
        with pytest.raises(ValueError, match="lon"):
            validate_inputs(52.0, 200.0, 10.0, 2020)

    def test_bad_radius(self):
        with pytest.raises(ValueError, match="radius"):
            validate_inputs(52.0, 4.0, -5.0, 2020)

    def test_bad_year(self):
        with pytest.raises(ValueError, match="year"):
            validate_inputs(52.0, 4.0, 10.0, 500)


class TestClampYear:
    def test_within_range(self):
        assert clamp_year(2015) == 2015

    def test_below_min(self):
        assert clamp_year(1990) == 2000

    def test_above_max(self):
        assert clamp_year(2025) == 2020


class TestHaversine:
    def test_same_point(self):
        assert haversine_km(0, 0, 0, 0) == pytest.approx(0.0)

    def test_equator_one_degree(self):
        # One degree of longitude at equator ≈ 111.19 km
        d = haversine_km(0, 0, 0, 1)
        assert 110 < d < 112

    def test_known_distance(self):
        # Amsterdam to Rotterdam ≈ 57 km
        d = haversine_km(52.3676, 4.9041, 51.9225, 4.4792)
        assert 55 < d < 60


class TestPixelDistances:
    def test_shape(self):
        lats = np.array([52.0, 52.1, 52.2])
        lons = np.array([4.0, 4.1])
        dists = pixel_distances_km(52.1, 4.05, lats, lons)
        assert dists.shape == (3, 2)

    def test_zero_distance(self):
        lats = np.array([52.0])
        lons = np.array([4.0])
        dists = pixel_distances_km(52.0, 4.0, lats, lons)
        assert dists[0, 0] == pytest.approx(0.0, abs=0.01)


class TestBoundingBox:
    def test_contains_center(self):
        south, north, west, east = bounding_box(52.0, 4.0, 10)
        assert south < 52.0 < north
        assert west < 4.0 < east

    def test_size_scales_with_radius(self):
        s1, n1, w1, e1 = bounding_box(52.0, 4.0, 10)
        s2, n2, w2, e2 = bounding_box(52.0, 4.0, 100)
        assert (n2 - s2) > (n1 - s1)

    def test_clamps_to_globe(self):
        south, north, _, _ = bounding_box(89.5, 0, 200)
        assert north <= 90.0
        assert south >= -90.0


class TestCircleGeoJSON:
    def test_structure(self):
        geojson = circle_geojson(52.0, 4.0, 10, n_points=16)
        assert geojson["type"] == "Polygon"
        coords = geojson["coordinates"][0]
        assert len(coords) == 17  # 16 + closing point
        assert coords[0] == coords[-1]  # ring is closed

    def test_points_near_center(self):
        geojson = circle_geojson(0, 0, 50, n_points=32)
        for lon, lat in geojson["coordinates"][0]:
            d = haversine_km(0, 0, lat, lon)
            assert d == pytest.approx(50, rel=0.02)


class TestAgeGroups:
    def test_all_present(self):
        assert len(AGE_CODES) == 18
        assert AGE_LABELS[0] == "0_1"
        assert AGE_LABELS[-1] == "80_plus"


# ---------------------------------------------------------------------------
# models.py tests
# ---------------------------------------------------------------------------

class TestPopulationResult:
    def test_repr(self):
        r = PopulationResult(total=1234567, year=2020, lat=52, lon=4, radius_km=10)
        assert "1,234,567" in repr(r)


class TestDemographicResult:
    @pytest.fixture
    def demo(self):
        groups = {}
        for i, label in enumerate(AGE_LABELS):
            m = 100.0 * (18 - i)
            f = 110.0 * (18 - i)
            groups[label] = AgeGroup(label=label, total=m + f, male=m, female=f)
        total_m = sum(ag.male for ag in groups.values())
        total_f = sum(ag.female for ag in groups.values())
        return DemographicResult(
            total=total_m + total_f,
            male=total_m,
            female=total_f,
            age_groups=groups,
            year=2020,
        )

    def test_sex_ratio(self, demo):
        assert demo.sex_ratio is not None
        assert demo.sex_ratio == pytest.approx(demo.male / demo.female)

    def test_dependency_ratio(self, demo):
        dr = demo.dependency_ratio
        assert dr is not None
        assert dr > 0

    def test_median_age_bucket(self, demo):
        bucket = demo.median_age_bucket
        assert bucket is not None
        assert bucket in AGE_LABELS

    def test_summary(self, demo):
        s = demo.summary()
        assert "Total population" in s
        assert "Age groups:" in s


class TestDensityResult:
    def test_repr(self):
        r = DensityResult(
            mean_density=500.0, max_density=12000.0, min_density=1.0,
            total_population=100000, area_km2=314.159,
        )
        assert "500" in repr(r)


# ---------------------------------------------------------------------------
# Backend dispatch tests (no network; just verify routing)
# ---------------------------------------------------------------------------

class TestBackendDispatch:
    def test_population_bad_backend(self):
        from popcoord.population import population
        with pytest.raises(ValueError, match="Unknown backend"):
            population(52, 4, 10, 2020, backend="nosuch")

    def test_demographics_bad_backend(self):
        from popcoord.demographics import demographics
        with pytest.raises(ValueError, match="Unknown backend"):
            demographics(52, 4, 10, 2020, backend="nosuch")

    def test_density_bad_backend(self):
        from popcoord.density import density
        with pytest.raises(ValueError, match="Unknown backend"):
            density(52, 4, 10, 2020, backend="nosuch")
