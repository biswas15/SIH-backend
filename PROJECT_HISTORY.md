# HeatSense — Project Development & Iteration History

This document serves as the single source of truth for all changes, architectural decisions, dataset updates, and validation logs across all project iterations.

---

## 📌 Project Overview
**HeatSense** is a hyper-local thermal risk assessment engine designed to provide decision support indicators for extreme heat events in Haldia Municipality.

---

## 📜 Phase History Log

### Phase 1: Baseline Weather Ingestion & Risk Schema Setup
* **Goal**: Establish the core FastAPI web service, Open-Meteo integration for micro-location forecast weather fetching (30 locations `H01`–`H30`), base Pydantic schema validation, and demo indicators layer.
* **Key Components**:
  * `main.py`: FastAPI endpoints (`/api/areas`, `/api/weather`).
  * `haldia_areas.json`: 30 sampling locations (`H01` to `H30`) with coordinates.
  * `app/data/haldia_indicators.json`: Demo synthetic indicators for 30 areas marked with `"data_status": "demo"`.
  * `app/schemas/risk_schema.py`: Pydantic V2 data models (`MacroWeatherInput`, `ThermalMetricsOutput`, `RiskDriver`, `WardRiskResponse`).
  * `validate_phase1.py`: Automated test suite for Phase 1 requirements.

---

### Phase 2: Integrate Real Haldia Population + Area Data Layer
* **Goal**: Implement the real ward-level population-density data layer for the 26 official Haldia municipal wards without modifying census values, inventing current population estimates, or prematurely modifying the H-area/weather pipeline.
* **Date**: September 18, 2026

#### 1. Data Rules & Sources Enforced
* **Population Source**: `Census of India 2011 — Haldia (M) ward record` (26 official municipal wards).
* **Boundary & Area Source**: `Haldia Municipality — Haldia Municipal Boundary 2012 KMZ` (GIS polygon area calculations in km²).
* **Calculation**: 
  $$\text{population\_density\_2011} = \frac{\text{population\_2011}}{\text{area\_km2}}$$
* **Precision**: Rounded programmatically to 2 decimal places for API display.

#### 2. Files Created & Artifacts

1. **`data/haldia_ward_areas_gis.json`**
   * Stores GIS polygon calculations (km²) for Wards 1 through 26 along with dataset metadata.

2. **`data/haldia_population_density.json`**
   * Final production JSON dataset holding all 26 official ward records.
   * Fields per record: `ward_number`, `population_2011`, `area_km2`, `population_density_2011`, `data_year`, `population_source`, `boundary_source`.

3. **`generate_population_density.py`**
   * Autonomous script to calculate population density programmatically from exact Census 2011 counts and GIS area inputs.

4. **`validate_population_density.py`**
   * Test & validation script verifying 7 strict dataset integrity assertions:
     1. Exactly 26 ward records exist.
     2. Ward numbers 1 through 26 all present without gaps.
     3. No duplicate ward numbers.
     4. Population values are strictly positive.
     5. Area values are strictly positive.
     6. Density matches arithmetic population / area within float tolerance (0.01).
     7. No missing or null values in required fields.

#### 3. Validation Summary
* **Result**: **7 PASS / 0 FAIL**
* Output logged to `validate_population_density_result.txt`.

#### 4. Sample Records Output (Verified GIS Polygon Areas)

* **Ward 1**:
  ```json
  {
    "ward_number": 1,
    "population_2011": 6308,
    "area_km2": 3.0282550486,
    "population_density_2011": 2083.05,
    "data_year": 2011,
    "population_source": "Census of India 2011 — Haldia (M) ward record",
    "boundary_source": "Haldia Municipality — Haldia Municipal Boundary 2012 KMZ"
  }
  ```
* **Ward 26**:
  ```json
  {
    "ward_number": 26,
    "population_2011": 7861,
    "area_km2": 3.0601046289,
    "population_density_2011": 2568.87,
    "data_year": 2011,
    "population_source": "Census of India 2011 — Haldia (M) ward record",
    "boundary_source": "Haldia Municipality — Haldia Municipal Boundary 2012 KMZ"
  }
  ```

#### 5. Phase 2A-Correction (GIS Area Source Update)
* **Goal**: Correct the GIS ward area values in `data/haldia_ward_areas_gis.json` with the verified WGS84 geodesic polygon areas (total $102.7688770629\text{ km}^2$).
* **Updated Area & Density Metrics**:
  * **Ward 1**: Area = $3.0282550486\text{ km}^2$, Population = $6308$, Density = $2083.05\text{ /km}^2$
  * **Ward 26**: Area = $3.0601046289\text{ km}^2$, Population = $7861$, Density = $2568.87\text{ /km}^2$
* **Validation**: All 7 validation checks passed.

#### 6. Existing Synthetic Data & Modular State
* `app/data/haldia_indicators.json` (H01–H30 synthetic data) was identified and left untouched with `"data_status": "demo"`.
* Ward-level population density remains modular and strictly un-connected from H01-H30 weather endpoints pending Phase 3 ward-to-area spatial mapping.

---

## 🛠️ Summary Table of Project Structure

| Path | Purpose / Description | Status |
|---|---|---|
| `main.py` | FastAPI server for Phase 1 weather API | Active |
| `haldia_areas.json` | Geographic point dataset (H01–H30) | Active |
| `app/data/haldia_indicators.json` | Demo synthetic indicators (H01–H30) | Active (Demo) |
| `app/schemas/risk_schema.py` | Pydantic V2 risk models | Active |
| `data/haldia_ward_areas_gis.json` | GIS polygon area dataset for Wards 1-26 | Active (Phase 2) |
| `data/haldia_population_density.json` | Census 2011 population density records | Active (Phase 2) |
| `generate_population_density.py` | Generator script for population density dataset | Active (Phase 2) |
| `validate_population_density.py` | Automated validator for ward population density | Active (Phase 2) |
| `gis_ward_mapping.py` | Spatial point-in-polygon join script for H01-H30 to Wards | Active (Phase 2) |
| `data/haldia_h_area_ward_map.json` | Mapping dataset connecting H01-H30 points to Haldia wards | Active (Phase 2) |
| `PROJECT_HISTORY.md` | Comprehensive single-file context & iteration tracker | Active |

---
*Note: This file will be continuously updated after every subsequent iteration plan to maintain complete project context.*
