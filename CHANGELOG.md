# Changelog

## 0.1.2 (2026-03-22)

- Fix critical bug: `demographics.py` was excluded from the wheel by an overly broad sdist glob (`demo*`), causing `ModuleNotFoundError: No module named 'popcoord.demographics'` on install

## 0.1.1 (2026-03-22)

- Fix broken demo.ipynb link on PyPI page (use absolute GitHub URL)
- Add PyPI, license, and CI badges to README

## 0.1.0 (2026-03-21)

Initial release.

- `population()`: total headcount within a radius
- `demographics()`: age x sex breakdown (18 cohorts)
- `density()`: mean / min / max persons per km2
- Two backends: `"api"` (lightweight) and `"raster"` (pixel-level)
- Computed properties: `sex_ratio`, `dependency_ratio`, `median_age_bucket`
- WorldPop data coverage: 2000–2020, ~1 km global resolution
