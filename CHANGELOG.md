# Changelog

## 0.1.0 — 2026-03-21

Initial release.

- `population()` — total headcount within a radius
- `demographics()` — age × sex breakdown (18 cohorts)
- `density()` — mean / min / max persons per km²
- Two backends: `"api"` (lightweight) and `"raster"` (pixel-level)
- Computed properties: `sex_ratio`, `dependency_ratio`, `median_age_bucket`
- WorldPop data coverage: 2000–2020, ~1 km global resolution
