# HeatSense — Project Progress and State

This document consolidates the current state, implementation plan, task status, and custom workspace rules/skills for the **HeatSense** backend (SIH26083, Haldia Municipality).

---

## 📊 Current System State

- **Active Branch**: `feature/thermal-stress-ml`
- **FastAPI Server**: Running live on `uvicorn main:app --reload` (`/api/areas`, `/api/weather`, `/api/wards`, `/api/health`).
- **Test Suite Health**: **68 / 68 tests passing** (`pytest -q` exited with code 0).
  - `test_get_areas.py`: Passing (asserts new unified `assessment` contract and demographics).
  - `tests/test_htsi_engine.py`: 24 tests passing.
  - `tests/test_risk_engine.py`: 3 tests passing.
  - `tests/test_thermal_math.py`: 21 tests passing.
  - `tests/test_vulnerability.py`: 15 tests passing.
  - `tests/test_weather_ingestion.py`: 4 tests passing.
- **Authoritative API Contract**:
  - Legacy top-level keys `thermal_metrics` and `risk_profile` have been officially deprecated and superseded.
  - Both current and forecast area timesteps now return a single, unified `assessment` object containing:
    - `risk_level` (`LOW`, `MODERATE`, `HIGH`, `EXTREME`)
    - `htsi` (Integer 0–100)
    - `thermal_stress` (Score breakdown, heat index, radiation bonus, wind relief)
    - `vulnerability` (Score breakdown, population density, worker and built-up ratios)
    - `supporting_metrics` (`heat_index_c`, `wbgt_proxy_c`)
    - `risk_drivers` (Human-readable contributing factors)
    - `recommended_actions` (Tier-specific advisories)
    - `data_status` (`live` or `unavailable`)

---

## 🚀 Implementation Plan

The objective is to deliver a hyper-local thermal risk assessment engine for extreme heat events in Haldia Municipality, integrating authentic geographic and demographic data with validated thermodynamic math.

### Phase Breakdown

1. **Phase 1: Baseline Weather Ingestion (Completed)**
   - Setup FastAPI service with CORS middleware and health checks.
   - Integrated Open-Meteo forecast API for 30 coordinate points (`H01`–`H30`) in Haldia.
   - Implemented Pydantic schemas for data validation.

2. **Phase 2 & Phase 2A: Authentic Census & Geodesic Ward Layer (Completed)**
   - Integrated verified Census of India 2011 population data for Haldia wards 1–26.
   - Calculated true WGS84 geodesic polygon areas from official 2012 municipal boundary KMZ (total area: 102.77 km²).
   - Programmatically derived population densities per ward and validated with automated assertions.

3. **Phase 2-GIS: Point-in-Polygon Spatial Mapping (Completed)**
   - Implemented ray-casting point-in-polygon spatial algorithm (`gis_ward_mapping.py`) mapping coordinates `H01`–`H30` to official municipal wards.
   - Bound demographic records (`population_2011`, `area_km2`, `population_density_2011`) directly to mapped sampling points in API responses.

4. **Phase 3: Thermal Stress Engine & Microclimate Downscaling (Completed)**
   - Implemented microclimate temperature downscaling using population-density LST anomaly proxy.
   - Built validated thermodynamic functions:
     - NOAA Heat Index (`heat_index_c`) using the full Rothfusz multi-parameter regression.
     - Australian Bureau of Meteorology (BOM) WBGT proxy (`wbgt_proxy_c`) incorporating vapor pressure and wind speed.
     - Simplified WBGT proxy (`wbgt_simplified_c`).

5. **Phase 4: HTSI, Vulnerability & Decision Support Engine (Completed)**
   - Built deterministic Haldia Thermal Stress Index:
     $$\text{HTSI} = 0.60 \times \text{thermal\_stress\_score} + 0.40 \times \text{vulnerability\_score}$$
   - Bounded HTSI to integer scale [0, 100] and established 4 risk tiers: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), and `EXTREME` (76–100).
   - Generated dynamic, explainable risk drivers (solar radiation penalty, wind cooling relief, socio-demographic vulnerability).
   - Formulated tier-specific municipal and citizen action advisories.

6. **Phase 5: Unified Pipeline & API Contract Migration (Completed)**
   - Replaced fragmented evaluation logic in `main.py` with a single unified `process_area_timestep` function.
   - Standardized both current conditions and 7-day hourly forecasts to emit the uniform `assessment` object.
   - Retained legacy function signatures as non-breaking stubs to maintain backwards test compatibility.

7. **Phase 6: Test Suite Alignment & Invariant Enforcement (Completed)**
   - Refactored `test_get_areas.py` to assert the new `assessment` structure while strictly maintaining ward and demographic validations.
   - Verified that all 68 unit and integration tests pass cleanly with zero failures.

8. **Next Phase: Deployment, Clean-up & Frontend Alignment (Pending)**
   - Commit all modified and untracked engine files to the Git branch `feature/thermal-stress-ml`.
   - Reconcile frontend dashboard consumption with the new `assessment` contract.
   - Retire deprecated legacy engine stubs once external test dependencies are safely migrated.
   - Optional future: Connect real-time satellite LST anomaly feeds (e.g., Landsat/Sentinel thermal infrared) when live data ingestion pipelines are configured.

---

## 📝 Task Status: Completed vs. Pending

### ✅ Completed Tasks

- [x] Build core FastAPI application (`main.py`) with `/api/areas`, `/api/weather`, `/api/wards`, and `/api/health`.
- [x] Ingest Open-Meteo meteorological data for 30 coordinate points (`H01`–`H30`).
- [x] Define Pydantic V2 risk schemas (`app/schemas/risk_schema.py`).
- [x] Create verified GIS polygon ward areas dataset (`data/haldia_ward_areas_gis.json`).
- [x] Create Census 2011 population density generator & dataset (`data/haldia_population_density.json`).
- [x] Enforce automated population density validation (`validate_population_density.py`).
- [x] Implement point-in-polygon spatial join (`gis_ward_mapping.py`) producing `data/haldia_h_area_ward_map.json`.
- [x] Connect demographic layer to `/api/areas` and `/api/weather` for mapped sampling areas.
- [x] Implement microclimate temperature downscaling (`app/engine/downscale.py`).
- [x] Implement validated NOAA Heat Index and BOM WBGT proxy math (`app/engine/thermal.py`).
- [x] Build demographic and socio-economic vulnerability score engine (`app/engine/vulnerability.py`).
- [x] Build Haldia Thermal Stress Index (HTSI) engine and risk classifier (`app/engine/htsi.py`).
- [x] Build explainable risk drivers and actionable advisory generator (`app/engine/htsi.py`).
- [x] Deprecate independent WBGT/HI dual-tier classification (`app/engine/risk.py`) in favor of authoritative HTSI tier.
- [x] Unify weather processing in `main.py` under single pipeline (`process_area_timestep`).
- [x] Migrate `/api/areas` and `/api/weather` to new authoritative `assessment` contract.
- [x] Update `test_get_areas.py` to validate `assessment` schema and demographic invariants.
- [x] Ensure all 68 unit and integration tests pass (`.\venv\Scripts\pytest`).

### ⏳ Pending Tasks

- [ ] Stage and commit all uncommitted refactoring changes on branch `feature/thermal-stress-ml`.
- [ ] Align frontend consumer components to parse the unified `assessment` object instead of legacy fields.
- [ ] Remove deprecated legacy stubs in `app/engine/risk.py` and `app/engine/thermal.py` once downstream consumers are fully migrated.
- [ ] Implement live satellite LST raster processing if satellite feed integration becomes available.
- [ ] Configure alert threshold webhooks for municipal disaster management notifications.

---

## 📜 Custom Skills & Workspace Rules

The following core rules and operational practices govern all development in this workspace:

### Workspace Rules

1. **No Data Fabrication**:
   - Never invent, estimate, or extrapolate demographic numbers. Exact Census of India 2011 values must be preserved.
   - Do not generate synthetic population projections or mock census statistics.
2. **Data Provenance & Geodesic Rigor**:
   - Ward boundaries and area calculations must originate from the verified WGS84 geodesic polygon calculations of the Haldia 2012 KMZ boundary file.
   - Source citations and metadata must be preserved in all exported datasets.
3. **Immutability of Coordinate System**:
   - Coordinates (`latitude`, `longitude`) for sampling locations `H01` through `H30` are fixed and must never be shifted or altered.
4. **Thermodynamic Math & Engine Governance**:
   - Use only validated physical and thermodynamic formulations (Rothfusz NOAA Heat Index regression, Australian BOM WBGT proxy).
   - Do not introduce arbitrary black-box machine learning, AHP, or SHAP models into the core deterministic thermodynamic engine.
   - Single authoritative risk metric: `risk_level` is determined exclusively by HTSI ($0.60 \times \text{thermal} + 0.40 \times \text{vulnerability}$); WBGT and Heat Index serve as supporting metrics.
5. **Unified API Contract**:
   - All thermal stress, vulnerability, and risk assessments must be encapsulated under the `assessment` key in API responses.
   - Avoid proliferating fragmented or conflicting top-level keys.
6. **Test Integrity & Invariant Preservation**:
   - Never weaken assertions, delete valid tests, or inject dummy bypasses to make tests pass.
   - Tests must validate against true mathematical and geographic invariants.
7. **Documentation & Traceability**:
   - Keep `PROJECT_HISTORY.md` and `.agents/progress.md` continuously updated with all architectural decisions, formula definitions, and milestone completions.

### Workspace Skills & Operational Workflows

1. **Test Runner Workflow**:
   - Virtual environment Python binaries are located at `.\venv\Scripts\python.exe` and `.\venv\Scripts\pytest.exe`.
   - Run the full test suite via `.\venv\Scripts\pytest` from the workspace root.
2. **Spatial Verification Workflow**:
   - Re-run `python gis_ward_mapping.py` whenever sampling points or ward boundary geometries change.
   - Run `python validate_population_density.py` to assert data integrity of the Census 2011 population density layer.
3. **API Integration Verification Workflow**:
   - Run `python test_get_areas.py` against the running Uvicorn server to verify endpoint contracts, demographic binding, and assessment payloads.
