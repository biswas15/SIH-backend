import json
import os
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI(title="Thermal Risk - Phase 1 Weather Ingestion API")

# Load locations from local JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AREAS_FILE = os.path.join(BASE_DIR, "haldia_areas.json")
areas_db = {}

def load_areas():
    global areas_db
    if os.path.exists(AREAS_FILE):
        with open(AREAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                areas_db[item["area_id"]] = item

# Initialize db
load_areas()

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
        result.append({
            "area_id": area["area_id"],
            "area_name": area["area_name"],
            "current": {
                "temperature": current_data.get("temperature_2m"),
                "relative_humidity": current_data.get("relative_humidity_2m"),
                "wind_speed": current_data.get("wind_speed_10m"),
                "time": current_data.get("time")
            }
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
    standardized_data = {
        "area": area_info,
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
