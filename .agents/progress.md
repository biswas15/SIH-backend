# HeatSense — Project Progress and State

This document serves as the authoritative, up-to-date consolidation of the current implementation plan, task status (completed vs. pending), workspace rules, and custom skills for the **HeatSense** backend (SIH Problem Statement 26083: Extreme Heatwave Early Warning and Human Thermal Stress Index for Haldia Municipality).

---

## 📊 Current System State

- **Active Branch**: `feature/thermal-stress-ml`
- **FastAPI Service**: Running live via `uvicorn main:app --reload` (`/api/areas`, `/api/weather`, `/api/wards`, `/api/health`).
- **Test Suite Health**: **68 / 68 unit & integration tests passing** (`pytest -q` exited with code 0).
  - `test_get_areas.py`: 100% passing (asserts 30 areas, 25 mapped, 5 outside boundary, unified `assessment` object, demographic invariants).
  - `tests/test_htsi_engine.py`: 24 tests passing (HTSI calculations, risk tier thresholds, boundary conditions).
  - `tests/test_risk_engine.py`: 3 tests passing.
  - `tests/test_thermal_math.py`: 21 tests passing (NOAA Heat Index Rothfusz regression, BOM WBGT proxy, humidity corrections).
  - `tests/test_vulnerability.py`: 15 tests passing (Census 2011 density scoring, demographic weights).
  - `tests/test_weather_ingestion.py`: 4 tests passing (Open-Meteo weather normalization).
- **Authoritative API Contract**:
  - Legacy keys `thermal_metrics` and `risk_profile` have been officially deprecated and superseded.
  - All area responses (current timestep and 7-day hourly forecasts) return a unified `assessment` object:
    - `risk_level`: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), `EXTREME` (76–100).
    - `htsi`: Integer bounded between 0 and 100 ($0.60 \times \text{thermal\_stress} + 0.40 \times \text{vulnerability}$).
    - `thermal_stress`: Score breakdown, heat index, radiation bonus, wind relief.
    - `vulnerability`: Score breakdown, Census 2011 population density, worker and built-up ratios.
    - `supporting_metrics`: `heat_index_c`, `wbgt_proxy_c`.
    - `risk_drivers`: Transparent, explainable contributing factors.
    - `recommended_actions`: Tier-specific municipal and citizen advisories.
    - `data_status`: `live` or `unavailable`.
- **Geographic & Ward Centroid Layer**:
  - `data/WardBoundary.kmz`: Official Haldia Municipality ward polygons (26 placemarks).
  - `data/haldia_ward_centroids.json`: Extracted arithmetic polygon centroids for all 26 official wards from `doc.kml`. Every centroid verified unique and strictly within ward bounding boxes.
- **ML Dataset & Modeling Infrastructure**:
  - `data/ml_features_baseline.csv`: Generated and verified (18,720 rows, 26 wards × 30 days × 24 hours).
    - Ingested real Open-Meteo Archive weather at **each ward's individual polygon centroid**.
    - Bound to official Census 2011 population densities.
    - Missing demographic exposure ratios (`outdoor_worker_ratio`, `built_up_ratio`) are strictly preserved as `NaN` (zero synthetic or fabricated data).
  - `scripts/build_ml_dataset.py`: Fully reproducible feature pipeline script with polygon centroid parsing, rate-limited Open-Meteo fetching, deterministic engine calculations, and 15 automated validation checks.
  - `scripts/train_ml_baseline.py`: Standalone baseline training script for 6-hour HTSI forecasting ($t+6$).
  - `models/htsi_forecast_rf.joblib`: Trained Random Forest model (~33 MB, 300 estimators, max_depth=12).
  - `models/htsi_forecast_features.json`: Ordered feature list (21 features).
  - `models/ml_baseline_metrics.json`: Full metrics report.

---

## 🚀 Implementation Plan

HeatSense provides hyper-local thermal risk assessment and decision support for extreme heat events across the 26 municipal wards of Haldia, integrating verified Census of India 2011 demographics, geodesic GIS polygons, validated thermodynamic mathematics, and an experimental transparent ML forecasting layer.

### Phase 1: Baseline Weather Ingestion & API Layer (Completed)
- Built FastAPI application with CORS middleware, health endpoints, and modular routing.
- Integrated Open-Meteo forecast API for 30 coordinate points (`H01`–`H30`) in Haldia.
- Established baseline Pydantic V2 schemas for weather inputs and outputs.

### Phase 2 & 2A: Authentic Census 2011 & Geodesic GIS Ward Layer (Completed)
- Extracted official Census of India 2011 population figures for all 26 Haldia wards (no projections, no synthetic data).
- Derived exact WGS84 geodesic polygon areas from the official 2012 municipal boundary KMZ (total area: 102.77 km²).
- Generated authoritative population density dataset (`data/haldia_population_density.json`) and verified with 7 automated integrity checks.

### Phase 2-GIS: Point-in-Polygon Spatial Mapping (Completed)
- Implemented ray-casting point-in-polygon spatial join (`gis_ward_mapping.py`).
- Classified sampling points: 25 points successfully mapped into municipal wards; 5 points identified as `outside_boundary` (port/water/estuary buffer zones).
- Bound Census demographics (`population_2011`, `area_km2`, `population_density_2011`) directly to mapped sampling points in API responses.

### Phase 3: Thermal Stress Engine & Microclimate Downscaling (Completed)
- Implemented microclimate temperature downscaling (`app/engine/downscale.py`) using population-density LST anomaly proxy.
- Implemented validated thermodynamic formulations (`app/engine/thermal.py`):
  - **NOAA Heat Index** (`heat_index_c`): Rothfusz 9-parameter regression with low/high RH adjustments.
  - **Australian BOM WBGT Proxy** (`wbgt_proxy_c`): Incorporates vapor pressure and wind cooling.
  - Simplified WBGT proxy (`wbgt_simplified_c`).

### Phase 4: HTSI, Vulnerability & Decision Support Engine (Completed)
- Formulated deterministic Haldia Thermal Stress Index:
  $$\text{HTSI} = 0.60 \times \text{thermal\_stress\_score} + 0.40 \times \text{vulnerability\_score}$$
- Bounded HTSI strictly to [0, 100] and categorized into 4 risk levels: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), `EXTREME` (76–100).
- Created explainable risk driver generation (solar radiation penalties, wind relief, vulnerability weights).
- Created tier-specific municipal action advisories and citizen health guidance.

### Phase 5: Unified Pipeline & API Contract Migration (Completed)
- Refactored `main.py` to evaluate both current conditions and 7-day hourly forecasts via a single unified `process_area_timestep` pipeline.
- Migrated `/api/areas` and `/api/weather` endpoints to emit the unified `assessment` object.
- Updated `test_get_areas.py` and test suite to assert the new contract while preserving demographic invariants.

### Phase 5 Part 1 (Revised): Ward-Level Historical Feature Dataset Generator (Completed)
- Built polygon centroid extractor from `data/WardBoundary.kmz` (`scripts/extract_centroids.py` / integrated in `scripts/build_ml_dataset.py`).
- Extracted exact arithmetic centroids for all 26 official Haldia wards and exported to `data/haldia_ward_centroids.json`.
- Ingested 30 days (720 hours) of real Open-Meteo Archive historical weather for each ward at its individual centroid coordinates.
- Bound authentic Census 2011 population densities and evaluated all hours through deterministic HeatSense engines.
- Emitted `data/ml_features_baseline.csv` (18,720 rows, 13 columns, 0 missing in weather/metrics, 100% NaN for unverified worker/built-up ratios).

### Phase 5 Part 2: Transparent ML Baseline for 6-Hour HTSI Forecasting (Completed / Pending Retrain on Centroid Dataset)
- Developed `scripts/train_ml_baseline.py` implementing a Random Forest regressor for 6-hour-ahead HTSI forecasting ($t+6$).
- Enforces strict chronological train/validation/test splits (70% / 15% / 15%) without lookahead bias.
- Features: cyclical hour, diurnal indicators, lagged weather (1h, 3h, 6h), rolling means, and thermodynamic metrics.
- Benchmarked against naive persistence ($HTSI_{t+6} = HTSI_t$).
- Initial run achieved MAE 3.40 (vs persistence 5.52 — 38.4% improvement), test R²=0.2443, risk tier accuracy 81.1%.
- *Next step*: Re-run `train_ml_baseline.py` on the revised per-ward centroid dataset to refresh model weights and evaluation metrics.

### Phase 6: ML Model Evaluation & Refinement (In Progress)
- Validate feature importances and domain consistency across wards.
- Document scientific caveats regarding reanalysis grid cell resolution vs micro-scale ward variations.
- Retain ML model strictly as an auxiliary offline forecasting prototype; do not couple to synchronous production API request paths.

### Phase 7: Deployment, Git Clean-Up & Frontend Alignment (Pending)
- Stage and commit all engine refactoring, test fixes, and ML pipeline scripts to `feature/thermal-stress-ml`.
- Clean up scratch files (`scripts/extract_centroids.py`, `phase4_diff.txt`, `h23_output.json`).
- Update frontend dashboard consumers to ingest the unified `assessment` schema.
- Retire backwards-compatibility legacy stubs once all downstream consumers are confirmed updated.

---

## 📝 Task Status: Completed vs. Pending

### ✅ Completed Tasks

#### Core Web Service & Ingestion
- [x] Build core FastAPI application (`main.py`) with `/api/areas`, `/api/weather`, `/api/wards`, and `/api/health`.
- [x] Ingest Open-Meteo forecast data for 30 coordinate points (`H01`–`H30`).
- [x] Define Pydantic V2 schemas (`app/schemas/risk_schema.py`).

#### Geographic & Demographic Foundation
- [x] Create verified GIS polygon ward areas dataset (`data/haldia_ward_areas_gis.json`).
- [x] Extract authentic Census 2011 population records for all 26 wards.
- [x] Implement programmatic population density derivation (`generate_population_density.py`).
- [x] Implement automated 7-assertion validation test (`validate_population_density.py`).
- [x] Implement ray-casting point-in-polygon spatial join (`gis_ward_mapping.py`) mapping H01–H30 to wards.
- [x] Connect demographic records (`population_2011`, `area_km2`, `population_density_2011`) to `/api/areas` and `/api/weather`.
- [x] Extract exact arithmetic polygon centroids for all 26 official wards from `data/WardBoundary.kmz` (`data/haldia_ward_centroids.json`).

#### Thermodynamic, Vulnerability & HTSI Engines
- [x] Implement microclimate temperature downscaling (`app/engine/downscale.py`).
- [x] Implement NOAA Heat Index Rothfusz regression with humidity adjustments (`app/engine/thermal.py`).
- [x] Implement Australian BOM WBGT proxy math with vapor pressure and wind cooling (`app/engine/thermal.py`).
- [x] Build Census demographic vulnerability engine (`app/engine/vulnerability.py`).
- [x] Build Haldia Thermal Stress Index (HTSI) engine and 4-tier risk classifier (`app/engine/htsi.py`).
- [x] Build explainable risk drivers and municipal action advisories (`app/engine/htsi.py`).
- [x] Deprecate independent dual-tier classification in favor of single authoritative HTSI risk level.

#### Pipeline Unification & Testing
- [x] Unify weather processing in `main.py` under `process_area_timestep`.
- [x] Migrate `/api/areas` and `/api/weather` to the authoritative `assessment` contract.
- [x] Update `test_get_areas.py` to validate `assessment` schema and demographic invariants.
- [x] Verify that all 68 unit and integration tests pass cleanly (`.\venv\Scripts\pytest`).

#### Machine Learning Pipeline (Phase 5)
- [x] Build Phase 5 Part 1 standalone dataset generator (`scripts/build_ml_dataset.py`).
- [x] **Revision**: Update generator to fetch Open-Meteo historical weather at each ward's individual polygon centroid.
- [x] Generate verified `data/ml_features_baseline.csv` (18,720 rows across 26 wards, 13 columns).
- [x] Enforce data integrity: emit NaN for unverified worker/built-up ratios; zero fabricated data.
- [x] Write Phase 5 Part 2 ML baseline training script (`scripts/train_ml_baseline.py`) with 6-hour horizon, time-series splits, persistence comparisons, and risk matrix evaluations.
- [x] Initial ML training execution, generating `models/htsi_forecast_rf.joblib`, `models/ml_baseline_metrics.json`, and `data/ml_feature_importance.csv`.

---

### ⏳ Pending Tasks

#### Machine Learning Pipeline
- [ ] Retrain `scripts/train_ml_baseline.py` using the revised per-ward centroid dataset `data/ml_features_baseline.csv` to update final metrics and artifacts.
- [ ] Document grid-resolution limitations (Open-Meteo ERA5 / reanalysis resolution vs municipal microclimate).

#### Repository & Deployment Clean-Up
- [ ] Remove scratch helper scripts and temporary diff artifacts (`scripts/extract_centroids.py`, `phase4_diff.txt`, `h23_output.json`).
- [ ] Stage and commit all uncommitted refactor and ML files to `feature/thermal-stress-ml`.

#### Frontend & Downstream Integration
- [ ] Align frontend UI components to consume the unified `assessment` object instead of deprecated fields.
- [ ] Remove legacy stubs in `app/engine/risk.py` and `app/engine/thermal.py` once frontend migration is verified.
- [ ] Implement automated alert webhooks for municipal disaster management when HTSI reaches `EXTREME` (76–100).

---

## 📜 Custom Skills & Workspace Rules

Development within this repository is strictly governed by the following workspace rules and domain constraints:

### Core Workspace Rules

1. **Zero Data Fabrication & Strict Provenance**:
   - Never invent, estimate, interpolate, or extrapolate demographic or population numbers. Exact Census of India 2011 values are mandatory.
   - Ward boundaries and geodesic surface areas must strictly originate from the verified WGS84 polygon calculations of the official Haldia 2012 boundary KMZ file.
   - Any missing indicators (such as ward-level outdoor worker ratios or satellite built-up ratios) must be emitted as `null`/`NaN` with appropriate integrity warnings, never mock numbers.

2. **Thermodynamic Engine Integrity**:
   - Calculations for perceived heat and wet-bulb globe temperature must use validated physical formulations (NOAA Rothfusz regression, Australian BOM WBGT proxy).
   - Core thermodynamic evaluations must remain deterministic and transparent. No black-box machine learning models may replace the physical temperature downscaling or heat index calculations.

3. **Authoritative Single-Metric Risk Tiering**:
   - The Haldia Thermal Stress Index (HTSI) is the **sole authoritative metric** determining overall `risk_level` (`LOW`, `MODERATE`, `HIGH`, `EXTREME`).
   - WBGT and Heat Index serve as auxiliary supporting metrics and must not override or contradict the HTSI tier.

4. **Unified API Contract**:
   - All risk, thermal, vulnerability, supporting metrics, risk drivers, and recommended actions must be encapsulated under the single `assessment` key in API responses.
   - Fragmented legacy top-level keys (`thermal_metrics`, `risk_profile`) are deprecated.

5. **ML Prototype Safeguards & Architectural Boundary**:
   - Machine learning models (e.g., 6-hour HTSI forecasting) are strictly experimental future forecasting layers.
   - ML components must reside in `scripts/` and `models/` without modifying core production API endpoints or the deterministic current-condition engine.

6. **Test Invariant Preservation**:
   - Never weaken assertions, delete valid tests, or inject dummy bypasses to make tests pass.
   - Tests must validate against true mathematical and geographic invariants.

7. **Continuous Documentation & Traceability**:
   - Maintain `PROJECT_HISTORY.md` and `.agents/progress.md` after each phase or architectural iteration to preserve a complete operational log.

---

### Custom Skills & Built-in Tooling

The following skills and tools are configured and available in the environment:

| Skill / Tool | Source | Purpose & Application |
|---|---|---|
| **`google-antigravity-sdk`** | Plugin (`google-antigravity-sdk`) | Autonomous AI agent design, orchestration, and configuration workflows using the Google Antigravity SDK. |
| **`modern-web-guidance`** | Plugin (`modern-web-guidance-plugin`) | Best practices search and execution for modern web layouts, CSS glassmorphism, responsive components, and modern frontend dashboards. |
| **`chrome-extensions`** | Plugin (`modern-web-guidance-plugin`) | Manifest V3 best practices for browser extensions, service workers, and side-panel integrations. |
| **`agy-customizations`** | Built-in | Reference guide for customizing Antigravity rules, skills, plugins, and MCP server integrations. |
| **`antigravity-guide`** | Built-in | Reference and sitemap for Antigravity IDE, CLI, keybindings, and development tools. |

---

### Key Operational Workflows & Scripts

- **Full Test Suite**:
  ```powershell
  .\venv\Scripts\pytest -q
  ```
- **API Contract & Demographic Integration Test**:
  ```powershell
  .\venv\Scripts\python test_get_areas.py
  ```
- **GIS Population Density Verification**:
  ```powershell
  .\venv\Scripts\python validate_population_density.py
  ```
- **Spatial Ward Mapping Generator**:
  ```powershell
  .\venv\Scripts\python gis_ward_mapping.py
  ```
- **Historical ML Dataset Generator (Phase 5 Part 1 Revision)**:
  ```powershell
  .\venv\Scripts\python scripts/build_ml_dataset.py
  ```
- **ML Baseline 6-Hour Forecasting (Phase 5 Part 2)**:
  ```powershell
  .\venv\Scripts\python scripts/train_ml_baseline.py
  ```
