import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_SITE_PACKAGES = os.path.join(BASE_DIR, "venv", "Lib", "site-packages")

if os.path.exists(VENV_SITE_PACKAGES):
    sys.path.insert(0, VENV_SITE_PACKAGES)

AREAS_PATH = os.path.join(BASE_DIR, "haldia_areas.json")
INDICATORS_PATH = os.path.join(BASE_DIR, "app", "data", "haldia_indicators.json")
OUT_PATH = os.path.join(BASE_DIR, "validate_result.txt")

sys.path.insert(0, BASE_DIR)

def log(msg):
    print(msg)
    with open(OUT_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Clear existing log file
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("--- Starting Validation ---\n")

try:
    log("1. Checking JSON files...")
    with open(AREAS_PATH, "r", encoding="utf-8") as f:
        areas_data = json.load(f)

    with open(INDICATORS_PATH, "r", encoding="utf-8") as f:
        indicators_data = json.load(f)

    areas_ids = [a["area_id"] for a in areas_data]
    indicators_ids = [i["area_id"] for i in indicators_data]

    assert len(indicators_data) == 30, f"Expected 30 items, got {len(indicators_data)}"
    assert areas_ids == indicators_ids, "Area IDs do not match haldia_areas.json exactly!"
    log("SUCCESS 1: haldia_indicators.json is valid JSON with exactly 30 matching area IDs.")

    for item in indicators_data:
        aid = item["area_id"]
        pop = item["population_density"]
        bu = item["built_up_ratio"]
        ol = item["outdoor_labor_ratio"]
        lst = item["lst_anomaly"]
        status = item["data_status"]
        
        assert 1500.0 <= pop <= 9500.0, f"[{aid}] pop density {pop} out of range"
        assert 0.15 <= bu <= 0.85, f"[{aid}] built up ratio {bu} out of range"
        assert 0.10 <= ol <= 0.60, f"[{aid}] outdoor labor ratio {ol} out of range"
        assert -1.5 <= lst <= 3.0, f"[{aid}] lst anomaly {lst} out of range"
        assert status == "demo", f"[{aid}] data_status {status} != 'demo'"

    log("SUCCESS 2: Indicator ranges and data_status=='demo' verified for all 30 wards.")

    log("2. Testing Pydantic schema import...")
    from app.schemas.risk_schema import (
        MacroWeatherInput,
        ThermalMetricsOutput,
        RiskDriver,
        WardRiskResponse
    )
    log("SUCCESS 3: Imported app.schemas.risk_schema successfully.")

    mw = MacroWeatherInput(temp_c=34.5, rh=72.0, wind_speed=12.0)
    tm = ThermalMetricsOutput(heat_index=39.2, downscaled_temp=35.1)
    rd = RiskDriver(code="HIGH_HUMIDITY", message="Elevated relative humidity", contribution_pct=45.0)
    wrr = WardRiskResponse(
        area_id="H01",
        area_name="Haldia Township",
        valid_at="2026-09-17T21:00",
        thermal_metrics=tm,
        top_drivers=[rd],
        recommended_actions=["Stay hydrated", "Avoid outdoor direct sunlight"]
    )
    assert wrr.disclaimer == "Population-level decision support indicator only; not a medical diagnosis or mortality prediction."
    log("SUCCESS 4: Pydantic V2 models instantiate correctly with default disclaimer.")

    try:
        MacroWeatherInput(temp_c=30.0, rh=105.0, wind_speed=5.0)
        assert False, "Failed to reject invalid rh > 100"
    except ValueError:
        log("SUCCESS 5: Validation error correctly raised for rh > 100.")

    try:
        RiskDriver(code="X", message="Y", contribution_pct=150.0)
        assert False, "Failed to reject invalid contribution_pct > 100"
    except ValueError:
        log("SUCCESS 6: Validation error correctly raised for contribution_pct > 100.")

    log("3. Testing main.py import...")
    from main import app, get_areas, get_weather
    log("SUCCESS 7: Existing main.py loaded cleanly without issues.")

    log("--- ALL PHASE 1 VERIFICATIONS PASSED SUCCESSFULLY ---")

except Exception as e:
    log(f"ERROR: Validation failed: {type(e).__name__}: {e}")
    import traceback
    log(traceback.format_exc())
