import json
import os
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException
# pyrefly: ignore [missing-import]
import httpx

from app.engine.thermal import compute_thermal_metrics

app = FastAPI(title="Thermal Risk - Phase 1 Weather Ingestion API")

# Load locations from local JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AREAS_FILE = os.path.join(BASE_DIR, "haldia_areas.json")
WARD_MAP_FILE = os.path.join(BASE_DIR, "data", "haldia_h_area_ward_map.json")
POP_DENSITY_FILE = os.path.join(BASE_DIR, "data", "haldia_population_density.json")

areas_db = {}
ward_map_db = {}
pop_density_db = {}

def load_areas():
    global areas_db
    if os.path.exists(AREAS_FILE):
        with open(AREAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                areas_db[item["area_id"]] = item

def load_ward_data():
    global ward_map_db, pop_density_db
    if os.path.exists(WARD_MAP_FILE):
        with open(WARD_MAP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            ward_map_db = data.get("mapping", {})
    if os.path.exists(POP_DENSITY_FILE):
        with open(POP_DENSITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                pop_density_db[item["ward_number"]] = item

# Initialize db
load_areas()
load_ward_data()

def get_ward_and_demographics(area_id):
    ward_info = {"ward_number": None, "mapping_status": "unmapped"}
    demographics = None
    
    if area_id in ward_map_db:
        mapping = ward_map_db[area_id]
        status = mapping.get("mapping_status")
        # Map gis_verified to mapped for the API response, or keep original outside_municipal_boundary
        if status == "gis_verified":
            ward_info["mapping_status"] = "mapped"
            ward_info["ward_number"] = mapping.get("ward_number")
        elif status == "outside_municipal_boundary":
            ward_info["mapping_status"] = "outside_boundary"
        else:
            ward_info["mapping_status"] = status
            
        if ward_info["ward_number"] is not None and ward_info["ward_number"] in pop_density_db:
            pop_data = pop_density_db[ward_info["ward_number"]]
            demographics = {
                "population_2011": pop_data.get("population_2011"),
                "area_km2": pop_data.get("area_km2"),
                "population_density_2011": pop_data.get("population_density_2011"),
                "data_year": pop_data.get("data_year"),
                "population_source": pop_data.get("population_source"),
                "boundary_source": pop_data.get("boundary_source")
            }
            
    return ward_info, demographics

@app.get("/")
def root():
    return {"message": "Thermal Risk Weather API is running."}

@app.get("/api/areas")
async def get_areas():
    if not areas_db:
        return []
        
    areas_list = list(areas_db.values())
    lats = ",".join(str(area["latitude"]) for area in areas_list)
    lons = ",".join(str(area["longitude"]) for area in areas_list)
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=Asia/Kolkata"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Error fetching data from weather API: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"Weather API returned error status: {exc.response.status_code}")
            
    result = []
    for i, area in enumerate(areas_list):
        current_data = data[i].get("current", {}) if isinstance(data, list) else data.get("current", {})
        ward_info, demographics = get_ward_and_demographics(area["area_id"])
        
        thermal_metrics = None
        if demographics:
            macro_temp = current_data.get("temperature_2m", 0.0)
            rh = current_data.get("relative_humidity_2m", 0.0)
            wind_speed_kmh = current_data.get("wind_speed_10m", 0.0)
            lst_anomaly = round((demographics.get("population_density_2011", 0) / 3000.0) * 2.0, 2)
            thermal_metrics = compute_thermal_metrics(macro_temp, rh, wind_speed_kmh, lst_anomaly)
        
        result.append({
            "area_id": area["area_id"],
            "area_name": area["area_name"],
            "latitude": area["latitude"],
            "longitude": area["longitude"],
            "ward": ward_info,
            "demographics": demographics,
            "current": {
                "temperature": current_data.get("temperature_2m"),
                "relative_humidity": current_data.get("relative_humidity_2m"),
                "wind_speed": current_data.get("wind_speed_10m"),
                "time": current_data.get("time")
            },
            "thermal_metrics": thermal_metrics
        })
        
    return result

@app.get("/api/weather")
async def get_weather(area_id: str):
    """
    Fetches current and hourly weather data (temp, humidity, wind speed) for a given area_id.
    """
    area_id = area_id.upper()
    if area_id not in areas_db:
        raise HTTPException(status_code=404, detail="Area ID not found in local database")
    
    area_info = areas_db[area_id]
    lat = area_info["latitude"]
    lon = area_info["longitude"]
    
    ward_info, demographics = get_ward_and_demographics(area_id)
    
    # Open-Meteo API endpoint
    # Fetching current weather and hourly forecasts for temperature_2m, relative_humidity_2m, wind_speed_10m
    # Using forecast_days=3 to get exactly 72 hours of data
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m&forecast_days=3&timezone=Asia/Kolkata"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Error fetching data from weather API: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"Weather API returned error status: {exc.response.status_code}")
            
    # Standardize output
    current_data = data.get("current", {})
    
    thermal_metrics = None
    if demographics:
        macro_temp = current_data.get("temperature_2m", 0.0)
        rh = current_data.get("relative_humidity_2m", 0.0)
        wind_speed_kmh = current_data.get("wind_speed_10m", 0.0)
        lst_anomaly = round((demographics.get("population_density_2011", 0) / 3000.0) * 2.0, 2)
        thermal_metrics = compute_thermal_metrics(macro_temp, rh, wind_speed_kmh, lst_anomaly)
        
    standardized_data = {
        "area": area_info,
        "ward": ward_info,
        "demographics": demographics,
        "thermal_metrics": thermal_metrics,
        "metadata": {
            "timezone": "IST",
            "elevation": data.get("elevation"),
            "units": {
                "temperature": data.get("hourly_units", {}).get("temperature_2m"),
                "relative_humidity": data.get("hourly_units", {}).get("relative_humidity_2m"),
                "wind_speed": data.get("hourly_units", {}).get("wind_speed_10m"),
            }
        },
        "current": {
            "time": current_data.get("time"),
            "temperature": current_data.get("temperature_2m"),
            "relative_humidity": current_data.get("relative_humidity_2m"),
            "wind_speed": current_data.get("wind_speed_10m")
        },
        "forecast": []
    }
    
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    
    # Combine the arrays into a clean list of objects
    for i in range(len(times)):
        standardized_data["forecast"].append({
            "time": times[i],
            "temperature": temps[i] if i < len(temps) else None,
            "relative_humidity": humidities[i] if i < len(humidities) else None,
            "wind_speed": wind_speeds[i] if i < len(wind_speeds) else None
        })
        
    return standardized_data
