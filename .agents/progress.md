# HeatSense — Project Progress and State

This document consolidates the current state, implementation plan, task status, and custom project rules for the HeatSense backend.

---

## 🚀 Current Implementation Plan

The overall goal is to build a hyper-local thermal risk assessment engine for extreme heat events in Haldia Municipality. We are integrating real geographic and demographic data while keeping the architecture modular.

### Phases
1. **Phase 1: Baseline Weather Ingestion (Completed)**
   - Setup FastAPI.
   - Integrate Open-Meteo API for 30 sample locations (`H01`–`H30`).
   - Define base Pydantic schema validation.
2. **Phase 2: Real Haldia Population + Area Data Layer (Completed)**
   - Integrate verified Census 2011 population data for Haldia wards 1–26.
   - Use GIS-derived polygon areas from official KMZ boundaries.
   - Generate programmatic population density dataset.
3. **Phase 2A-Correction (Completed)**
   - Update GIS ward area source to true WGS84 geodesic polygon calculations.
4. **Integration: GIS Ward Mapping (Completed)**
   - Map H01–H30 sampling coordinates to official wards using point-in-polygon ray-casting.
   - Attach demographic data to `/api/areas` and `/api/weather` endpoints.
5. **Phase 3: Risk Engine Integration (Pending)**
   - Compute HeatSense Thermal Risk score based on weather and demographics.
   - Implement risk classification levels and actionable recommendations.

---

## 📝 Task Status: Completed vs. Pending

### ✅ Completed Tasks
- [x] Create core FastAPI server (`main.py`) with `/api/areas` and `/api/weather` endpoints.
- [x] Configure Open-Meteo integration for 30 coordinates (`H01`–`H30`).
- [x] Build `app/schemas/risk_schema.py` for response validation.
- [x] Create test validator for Phase 1 (`validate_phase1.py`).
- [x] Add verified GIS ward areas dataset (`data/haldia_ward_areas_gis.json`).
- [x] Add demographic dataset generator (`generate_population_density.py`).
- [x] Generate population density JSON (`data/haldia_population_density.json`).
- [x] Add population density validation script (`validate_population_density.py`).
- [x] Create project history tracker (`PROJECT_HISTORY.md`).
- [x] Update GIS area source to corrected WGS84 geodesic calculations.
- [x] Perform true point-in-polygon analysis to map H-areas to wards (`gis_ward_mapping.py`).
- [x] Generate GIS-verified ward mapping JSON (`data/haldia_h_area_ward_map.json`).
- [x] Update `main.py` to seamlessly attach demographic data to H-areas based on mapping.

### ⏳ Pending Tasks
- [ ] Connect the Ward population density layer to the actual Risk Engine (Phase 3).
- [ ] Implement thermal calculations (e.g., WBGT, heat index) based on Open-Meteo inputs.
- [ ] Apply normalization of population density for risk scoring.
- [ ] Develop ML components for risk scoring (if required later).
- [ ] Define comprehensive action recommendations based on top risk drivers.

---

## 📜 Custom Skills & Project Rules

Strict rules established during development to ensure data integrity and system stability:

1. **No Data Fabrication:** 
   - Do NOT generate fake, synthetic, estimated, or placeholder population values.
   - Do NOT modify the exact Census of India 2011 population values.
   - Do NOT invent current population projections.
2. **Data Provenance:** 
   - Area data MUST be derived directly from the Haldia Municipality 2012 ward-boundary KMZ using GIS polygon area calculation (WGS84).
   - Do not silently replace GIS-derived ward areas with generic published total areas.
   - Always preserve and cite source metadata in data structures.
3. **Immutability of Existing State:** 
   - Do NOT change ANY existing latitude or longitude values for `H01`–`H30`.
   - Keep Open-Meteo API functionality exactly as it currently works without disruption.
   - Existing synthetic demo data (`app/data/haldia_indicators.json`) must be isolated and not deleted prematurely.
4. **Documentation Requirement:** 
   - ALWAYS update `PROJECT_HISTORY.md` after every new iteration plan to save context continuously.
   - Keep this `.agents/progress.md` file consolidated and updated with the latest state.
