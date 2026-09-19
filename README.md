# HeatSense — Hyperlocal Heat Stress Early Warning Backend

HeatSense is a FastAPI backend for a hyperlocal, ward-level heat stress early warning system focused on Haldia, West Bengal.

The backend combines live weather information with GIS-verified municipal ward mapping and Census-based demographic data to provide the data foundation for hyperlocal heat-stress assessment.

---

## Current Development Status

### Phase 2 — Data & Weather Integration

**Status: Complete and validated**

The current backend supports:

- Haldia area coordinate management
- Live weather data from Open-Meteo
- 72-hour weather forecasts
- GIS-based H-area → municipal ward mapping
- Census of India 2011 ward-level population data
- GIS-derived ward areas
- Ward-level population density
- Combined weather + demographic API responses

### Upcoming — Phase 3

The next development stage will introduce:

- Thermal-stress calculations
- Heat Index / WBGT-related metrics
- Ward-level risk scoring
- Risk categories
- Explainable alert drivers
- ML-based risk/prediction components where scientifically justified

These components are not yet part of the current production API.

---

## System Architecture

```text
                    ┌─────────────────────┐
                    │   Haldia Areas      │
                    │ haldia_areas.json   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ GIS Ward Mapping    │
                    │ H-area → Ward       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │ Census 2011 Data    │          │ Open-Meteo API      │
   │ Population / Wards  │          │ Temperature         │
   └──────────┬──────────┘          │ Humidity / Wind     │
              │                     │ 72h Forecast        │
              ▼                     └──────────┬──────────┘
   ┌─────────────────────┐                     │
   │ Ward Density Data   │                     │
   └──────────┬──────────┘                     │
              │                                │
              └────────────────┬───────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   FastAPI Backend   │
                    │       main.py       │
                    └──────────┬──────────┘
                               │
                               ▼
                    Weather + Ward +
                    Demographic Response

                         ↓ Phase 3 ↓

                    Thermal Stress Engine
                         ↓
                    Risk Assessment
                         ↓
                    HeatSense Alerts
Tech Stack
Python 3.9+
FastAPI
Uvicorn
HTTPX
Open-Meteo
JSON
GIS / GeoJSON / KMZ boundary data
Census of India 2011 data
Project Structure
SIH-backend/
│
├── main.py
├── haldia_areas.json
├── requirements.txt
├── README.md
├── PROJECT_HISTORY.md
│
├── app/
│   ├── data/
│   │   └── haldia_indicators.json
│   └── schemas/
│       ├── __init__.py
│       └── risk_schema.py
│
├── data/
│   ├── haldia_h_area_ward_map.json
│   ├── haldia_population_density.json
│   ├── haldia_ward_areas_gis.json
│   ├── HaldiaMunicipalBoundary2012.kmz
│   └── WardBoundary.kmz
│
├── generate_population_density.py
├── gis_ward_mapping.py
│
├── validate_population_density.py
├── validate_integration.py
├── validate_phase1.py
├── test_get_areas.py
├── test_open_meteo.py
└── test_ward_integration.py
Data Sources
Weather

Live weather and forecast data are retrieved from Open-Meteo using the coordinates defined in:

haldia_areas.json

The original H-area latitude and longitude values are preserved for weather queries.

Currently used weather variables:

Air temperature
Relative humidity
Wind speed
Forecast time

The API provides a 72-hour forecast.

Haldia Ward Boundaries

Municipal ward boundaries are derived from the Haldia Municipal Boundary 2012 KMZ dataset.

The GIS dataset contains 26 municipal wards.

Ward areas used by the backend are calculated from the GIS boundary polygons rather than manually entered estimates.

Population

Ward-level population values are based on the Census of India 2011 Haldia (M) ward records.

The dataset contains 26 wards with a total population of:

200,827

Population data year:

2011

Population density is calculated as:

Population Density = Ward Population / Ward Area
H-area → Ward Mapping

H-area identifiers such as H01, H02, etc. are not assumed to correspond to ward numbers.

Each H-area coordinate is mapped to a municipal ward using point-in-polygon GIS analysis.

Current mapping:

25 H-areas mapped to municipal wards
5 H-areas located outside the supplied municipal boundary

For an H-area outside the municipal boundary, the API returns:

{
    "ward": {
        "ward_number": null,
        "mapping_status": "outside_boundary"
    }
}

Demographic data is returned as null for such areas.

API Endpoints
Root
GET /

Returns basic backend information.

Get All Areas
GET /api/areas

Returns all H-areas along with:

Area ID
Area name
Latitude
Longitude
Mapped ward
Ward demographics
Current weather
Get Area Weather
GET /api/weather?area_id=H01

Returns:

Area information
Ward mapping
Ward demographics
Current weather
72-hour forecast

Example:

/api/weather?area_id=H04
Running the Backend
1. Create the virtual environment
python -m venv venv
2. Activate the environment
.\venv\Scripts\activate
3. Install dependencies
pip install -r requirements.txt
4. Start FastAPI
python -m uvicorn main:app --reload

The development server will normally be available at:

http://127.0.0.1:8000
Testing the API
Get all areas
curl.exe "http://127.0.0.1:8000/api/areas"
Get weather for an area
curl.exe "http://127.0.0.1:8000/api/weather?area_id=H01"
Validation
Population-Density Validation

Run:

python validate_population_density.py

The validation checks:

Exactly 26 ward records
Ward numbers 1–26
No duplicate wards
Positive population values
Positive GIS areas
Correct population-density calculation
No missing required fields

Current result:

7 passed, 0 failed
Integration Validation

Run:

python validate_integration.py

The integration validation checks:

All 30 H-areas are present
Original latitude/longitude values are preserved
Ward numbers are valid
Ward 1 population and density
Ward 26 population and density
Total Census population

Current result:

8 passed, 0 failed
Important Data Integrity Notes
Census and GIS

Population values and ward boundaries come from separate source datasets:

Population: Census of India 2011
Boundaries/areas: Haldia Municipal Boundary 2012 GIS dataset

Ward population density is calculated by combining these datasets.

H-area Coordinates

The existing H-area coordinates are preserved because they are used by the Open-Meteo weather integration.

Synthetic Indicators

The file:

app/data/haldia_indicators.json

contains earlier demonstration/synthetic indicators.

These values should not be treated as measured or official Haldia data and should not be used as real-world training data without appropriate replacement or validation.
