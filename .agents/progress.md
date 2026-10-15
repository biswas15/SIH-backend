# HeatSense — Project Progress and State

This document serves as the authoritative, up-to-date consolidation of the current implementation plan, task status (completed vs. pending), workspace rules, and custom skills for the **HeatSense** backend (SIH Problem Statement 83: Extreme Heatwave Early Warning and Human Thermal Stress Index).

---

## 📊 Current System State

- **Active Architecture**: **Scalable 3-Tier Provider Architecture** (Location, Weather, Population providers with a unified `HeatSenseService` layer).
- **FastAPI Service**: Running live via `uvicorn main:app --reload` (`/api/areas`, `/api/weather`, `/api/wards`, `/api/health`, `/api/alerts/config`).
- **Test Suite Health**: **98 / 98 unit & integration tests passing** (`pytest` exited with code 0).
- **Core Thermal Engine Invariant**:
  - The core mathematical engines (`app/engine/thermal.py`, `app/engine/vulnerability.py`, `app/engine/htsi.py`, `app/engine/downscale.py`, `app/engine/validation.py`) remain 100% untouched and mathematically pristine.
- **Authoritative API Contract**:
  - All area responses (current timestep and 7-day hourly forecasts) return a unified `assessment` object:
    - `risk_level`: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), `EXTREME` (76–100).
    - `htsi`: Bounded integer between 0 and 100 ($0.60 \times \text{thermal\_stress} + 0.40 \times \text{vulnerability}$).
    - `thermal_stress`: Breakdown score, Heat Index, WBGT proxy, solar radiation bonus, wind speed mitigation.
    - `vulnerability`: Breakdown score, Census 2011 population density, worker and built-up ratios.
    - `supporting_metrics`: `heat_index_c`, `wbgt_proxy_c`.
    - `risk_drivers`: Transparent, explainable contributing factors.
    - `recommended_actions`: Tier-specific municipal and citizen advisories.
    - `data_status`: `live`, `unavailable`, or `invalid`.
  - Forecast responses include explicit 24h, 48h, 72h projection arrays and a `forecast_projections` object.
  - Metadata includes canonical units, timezone information (Asia/Kolkata / IST / +05:30), and elevation.

---

## 🚀 Implementation Plan

HeatSense provides hyper-local thermal risk assessment and decision support for extreme heat events. The project is transitioning from a Haldia-specific prototype into a nationally scalable, location-driven heat-risk platform.

### Phase 1: Baseline Weather Ingestion & API Layer (Completed)
- Built FastAPI application with CORS middleware, health endpoints, and modular routing.
- Integrated Open-Meteo forecast API for coordinate points in Haldia.
- Added configurable timeout for weather requests via environment variable `HEATSENSE_WEATHER_TIMEOUT_S`.
- Added `/api/health` and `/api/alerts/config` endpoints.

### Phase 2: Census 2011 & Geodesic GIS Ward Layer (Completed)
- Extracted official Census of India 2011 population figures for all 26 Haldia wards.
- Generated population density dataset (`data/haldia_population_density.json`).
- Loaded ward area and geometry metadata (`data/haldia_ward_areas_gis.json`).

### Phase 3: Thermal Stress Engine & Downscaling (Completed)
- Implemented microclimate temperature downscaling (`app/engine/downscale.py`).
- Implemented thermodynamic formulations (`app/engine/thermal.py`):
  - **NOAA Heat Index** (`heat_index_c`)
  - **Australian BOM WBGT Proxy** (`wbgt_proxy_c`)
  - Added finite-input validation and range checks.

### Phase 4: HTSI, Vulnerability & Decision Support Engine (Completed)
- Formulated Haldia Thermal Stress Index (HTSI) bounded to [0, 100].
- Risk categorization: `LOW` (0–25), `MODERATE` (26–50), `HIGH` (51–75), `EXTREME` (76–100).
- Risk drivers and municipal actions generated deterministically from HTSI and vulnerability scores.

### Phase 5: Pipeline Unification & EXTREME HTSI Alert Service (Completed)
- Evaluated current conditions and 7-day forecasts via unified processing.
- Implemented `app/services/alerts.py` to dispatch webhooks upon EXTREME risk detection via FastAPI `BackgroundTasks`.

### Phase 6: Ward Metadata Endpoints (Completed)
- Added `/api/wards` and `/api/wards/{ward_number}` endpoints returning ward identifiers, area, population density, mapped area IDs, and status flags.

### Phase 7: Scalable 3-Tier Provider Architecture Refactoring (Completed)
- **Domain Schemas (`app/schemas/`)**:
  - `location.py`: `LocationContext` (lat/lon, name, state/district, area_sqkm, ward_number, elevation).
  - `weather.py`: `WeatherCurrent` & `WeatherForecastPoint` (normalized temperature, humidity, wind, solar radiation, units).
  - `population.py`: `PopulationContext` (total population, density per sqkm, worker ratio, vulnerable pop ratio, census year, data source).
- **Abstract Provider Interfaces (`app/providers/base.py`)**:
  - `LocationProvider`, `WeatherProvider`, `PopulationProvider`.
- **Concrete Provider Implementations**:
  - `HaldiaDemoLocationProvider` (`app/providers/location/haldia.py`)
  - `HaldiaDemoPopulationProvider` (`app/providers/population/haldia.py`)
  - `OpenMeteoWeatherProvider` (`app/providers/weather/open_meteo.py`)
- **Service Layer (`app/services/heatsense.py`)**:
  - `HeatSenseService`: Decouples business logic from HTTP endpoints and orchestrates providers with `app/engine/`.
- **Backward-Compatible Router (`main.py`)**:
  - Refactored `main.py` to route through `HeatSenseService` while preserving exact API contracts for frontend compatibility.

### Phase 8: External Location & Demographic Provider Expansion (Pending)
- Implement `GoogleMapsLocationProvider` / `OSMLocationProvider` for arbitrary coordinate/place geocoding.
- Implement `WorldPopPopulationProvider` for global/national high-resolution raster demographic data.
- Expose location-driven endpoint `/api/v2/assess?lat=...&lon=...`.

### Phase 9: Deployment & Frontend Alignment (Pending)
- Stage and commit provider architecture refactor.
- Align frontend consumers with unified `assessment` response structure where needed.
- Retire legacy dictionary parsing stubs once downstream frontend migration is complete.

---

## 📝 Task Status: Completed vs. Pending

### ✅ Completed Tasks

#### Core API & Weather Ingestion
- [x] Build core FastAPI application (`main.py`) with CORS middleware.
- [x] Ingest Open-Meteo forecast data for location coordinates.
- [x] Add `/api/health` and `/api/alerts/config` endpoints.
- [x] Add configurable weather request timeout (`HEATSENSE_WEATHER_TIMEOUT_S`).

#### GIS & Census Foundation
- [x] Create verified GIS polygon ward areas dataset (`data/haldia_ward_areas_gis.json`).
- [x] Extract authentic Census 2011 population records for Haldia wards.
- [x] Load ward mapping and population density datasets.

#### Engines (Thermal, Vulnerability, HTSI)
- [x] Microclimate temperature downscaling (`app/engine/downscale.py`).
- [x] NOAA Heat Index & BOM WBGT proxy formulations (`app/engine/thermal.py`).
- [x] Census demographic vulnerability engine (`app/engine/vulnerability.py`).
- [x] Haldia Thermal Stress Index (HTSI) engine and risk classifier (`app/engine/htsi.py`).
- [x] Explainable risk drivers and municipal action advisories.
- [x] Input validation and range checking (`app/engine/validation.py`).

#### Alerts & Ward API
- [x] EXTREME HTSI webhook alert notification service (`app/services/alerts.py`).
- [x] Ward list and ward lookup endpoints (`/api/wards`, `/api/wards/{ward_number}`).

#### Provider Architecture Refactoring
- [x] Domain schema definitions (`app/schemas/location.py`, `app/schemas/weather.py`, `app/schemas/population.py`).
- [x] Abstract provider interfaces (`app/providers/base.py`).
- [x] Concrete Haldia demo location provider (`app/providers/location/haldia.py`).
- [x] Concrete Haldia demo population provider (`app/providers/population/haldia.py`).
- [x] Concrete Open-Meteo weather provider (`app/providers/weather/open_meteo.py`).
- [x] Orchestrating service layer (`app/services/heatsense.py`).
- [x] Refactored `main.py` using `HeatSenseService` with 100% backward compatibility.
- [x] Provider unit and integration tests (`tests/test_providers.py`, `tests/test_weather_ingestion.py`, `tests/test_get_areas.py`).
- [x] Pass 98/98 backend tests cleanly.

### ⏳ Pending Tasks

#### Scalability & Multi-Region Expansion
- [ ] Implement `GoogleMapsLocationProvider` / `OSMLocationProvider` for dynamic national geocoding.
- [ ] Implement `WorldPopPopulationProvider` for global high-resolution population density grids.
- [ ] Implement generic coordinates assessment endpoint (`GET /api/v2/assess?lat={lat}&lon={lon}`).

#### Repository, Deployment & Frontend
- [ ] Stage and commit provider architecture changes.
- [ ] Align frontend dashboard components with the unified `assessment` contract.
- [ ] Remove legacy compatibility stubs in `app/engine/` after frontend confirmation.
- [ ] Configure `HEATSENSE_ALERT_WEBHOOK_URL` in live production environment.

---

## 📜 Custom Skills & Workspace Rules

### Core Workspace Rules

1. **Zero Data Fabrication & Strict Provenance**:
   - Never invent, estimate, interpolate, or extrapolate demographic or population numbers. Exact Census of India 2011 values or verified geospatial datasets must be used.
   - Any missing indicators must be emitted as `null`/`NaN` with appropriate integrity warnings, never fake numbers.

2. **Thermodynamic Engine Integrity**:
   - Calculations for perceived heat and wet-bulb globe temperature must use validated physical formulations.
   - Core thermodynamic evaluations must remain deterministic and transparent. No black-box ML models may replace physical downscaling or heat index calculations.

3. **Authoritative Single-Metric Risk Tiering**:
   - The Haldia Thermal Stress Index (HTSI) is the **sole authoritative metric** determining overall `risk_level`.

4. **Unified API Contract**:
   - All risk, thermal, vulnerability, supporting metrics, risk drivers, and recommended actions must be encapsulated under the single `assessment` key in API responses.

5. **ML Prototype Safeguards & Architectural Boundary**:
   - Machine learning models are strictly experimental future forecasting layers.
   - ML components must reside in isolated locations (`archive/`) without modifying core production API endpoints or the deterministic current-condition engine.

6. **Provider Architecture Decoupling**:
   - External dependencies (Open-Meteo, Census datasets, Geocoding APIs, WorldPop) must strictly implement Provider interfaces (`LocationProvider`, `WeatherProvider`, `PopulationProvider`).
   - Domain logic must interact exclusively through Pydantic domain models (`LocationContext`, `WeatherCurrent`, `PopulationContext`) via `HeatSenseService`.

7. **Test Invariant Preservation**:
   - Never weaken assertions, delete valid tests, or inject dummy bypasses to make tests pass.
   - Tests must validate against true mathematical, structural, and geographic invariants.

8. **Continuous Documentation & Traceability**:
   - Maintain `.agents/progress.md` after each major architectural phase or refactoring iteration.

### Custom Skills & Workspace Tooling

| Skill / Tool | Source / Path | Purpose & Application |
|---|---|---|
| **`google-antigravity-sdk`** | Plugin (`google-antigravity-sdk`) | Autonomous AI agent design, orchestration, and configuration workflows using Google Antigravity SDK. |
| **`modern-web-guidance`** | Plugin (`modern-web-guidance-plugin`) | Best practices search and execution for modern web layouts, CSS glassmorphism, responsive components. |
| **`chrome-extensions`** | Plugin (`modern-web-guidance-plugin`) | Manifest V3 best practices for browser extensions, service workers, and side-panel integrations. |
| **`gemini-api-dev`** | Plugin (`gemini-api`) | Text generation, multi-turn chat, multimodal understanding, structured outputs with Gemini API. |
| **`gemini-live-api-dev`** | Plugin (`gemini-api`) | Bidirectional streaming applications with Gemini Live API. |
| **`gemini-omni-flash-api`** | Plugin (`gemini-api`) | Generative video editing and multi-frame processing with Gemini Omni 1.1 Flash. |
| **`agy-customizations`** | Built-in | Reference guide for customizing Antigravity rules, skills, plugins, and MCP server integrations. |
| **`antigravity-guide`** | Built-in | Reference and sitemap for Antigravity IDE, CLI, keybindings, and development tools. |

---