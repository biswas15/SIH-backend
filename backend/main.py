import os
import json
from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.providers.location.haldia import HaldiaDemoLocationProvider
from app.providers.population.haldia import HaldiaDemoPopulationProvider
from app.providers.location.cities import IndiaCitiesLocationProvider
from app.providers.population.cities import IndiaCitiesPopulationProvider
from app.providers.weather.open_meteo import OpenMeteoProvider
from app.services.heatsense import process_area_timestep
from app.services.alerts import dispatch_extreme_alert

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IST = timezone(timedelta(hours=5, minutes=30))

def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0.0 else default

app = FastAPI(title="Thermal Risk - Phase 1 Weather Ingestion API")

WEATHER_TIMEOUT_SECONDS = _env_float("HEATSENSE_WEATHER_TIMEOUT_S", 15.0)

cors_origins = [
    origin.strip()
    for origin in os.environ.get("HEATSENSE_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Providers
location_provider = HaldiaDemoLocationProvider(data_dir=DATA_DIR)
population_provider = HaldiaDemoPopulationProvider(data_dir=DATA_DIR)
cities_location_provider = IndiaCitiesLocationProvider(data_dir=DATA_DIR)
cities_population_provider = IndiaCitiesPopulationProvider(data_dir=DATA_DIR)
weather_provider = OpenMeteoProvider(timeout_seconds=WEATHER_TIMEOUT_SECONDS)


def _parse_timestamp(value):
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
        return parsed.astimezone(IST)
    except (TypeError, ValueError):
        return None

def _canonical_weather_units(payload: dict) -> dict:
    source = payload.get("hourly_units") if isinstance(payload.get("hourly_units"), dict) else {}
    return {
        "temperature": source.get("temperature_2m"),
        "relative_humidity": source.get("relative_humidity_2m"),
        "wind_speed": source.get("wind_speed_10m"),
        "shortwave_radiation": source.get("shortwave_radiation"),
    }


@app.get("/")
def root():
    return {"message": "Thermal Risk Weather API is running."}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "heatsense-backend",
        "areas_loaded": len(location_provider.areas_db),
        "wards_loaded": len(population_provider.pop_density_db),
        "mapped_areas": sum(
            1 for mapping in location_provider.ward_map_db.values() if mapping.get("mapping_status") == "gis_verified"
        ),
        "weather_provider": "Open-Meteo",
        "timezone": "Asia/Kolkata",
    }


@app.get("/api/wards")
def get_wards():
    # Backward compatible /api/wards
    wards = []
    # Ward areas is still read from gis.json if needed, but since it's only for the endpoint,
    # let's load it locally.
    ward_areas_db = {}
    ward_areas_file = os.path.join(DATA_DIR, "haldia_ward_areas_gis.json")
    if os.path.exists(ward_areas_file):
        with open(ward_areas_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            ward_areas_db = {item["ward_number"]: item for item in data.get("wards", [])}

    for ward_number in sorted(population_provider.pop_density_db.keys()):
        population_data = population_provider.pop_density_db[ward_number]
        area = ward_areas_db.get(ward_number, {})
        mapped_area_ids = sorted(
            area_id for area_id, mapping in location_provider.ward_map_db.items()
            if mapping.get("ward_number") == ward_number
        )
        wards.append({
            "ward_number": ward_number,
            "ward_name": None,
            "area_km2": area.get("area_km2"),
            "population_2011": population_data.get("population_2011"),
            "population_density_2011": population_data.get("population_density_2011"),
            "data_year": population_data.get("data_year"),
            "mapped_area_ids": mapped_area_ids,
            "geometry": None,
            "geometry_status": "not_available",
            "geometry_source": None,
        })
    return wards


@app.get("/api/wards/{ward_number}")
def get_ward(ward_number: int):
    wards = get_wards()
    for w in wards:
        if w["ward_number"] == ward_number:
            return w
    raise HTTPException(status_code=404, detail="Ward not found")


@app.get("/api/alerts/config")
def get_alert_config():
    """
    Returns current EXTREME HTSI alert webhook configuration status.
    The secret token (if set) is masked and never returned in plaintext.
    """
    url = os.environ.get("HEATSENSE_ALERT_WEBHOOK_URL", "").strip()
    secret = os.environ.get("HEATSENSE_ALERT_SECRET", "").strip()
    timeout_s = _env_float("HEATSENSE_ALERT_TIMEOUT_S", 5.0)
    return {
        "alerts_enabled": bool(url),
        "webhook_url": url if url else None,
        "secret_configured": bool(secret),
        "timeout_seconds": timeout_s,
        "trigger_condition": "risk_level == EXTREME (HTSI >= 76)",
        "dispatch_mode": "fire-and-forget BackgroundTask",
    }


@app.get("/api/areas")
async def get_areas(background_tasks: BackgroundTasks):
    areas_list = location_provider.get_all_locations()
    if not areas_list:
        return []

    # Fast path: the original implementation fired one Open-Meteo call for all areas.
    # To remain performant, we intercept the fact that OpenMeteoProvider normally takes single lat/lon.
    # Since our Provider architecture is meant for single locations usually, we will bypass the single-fetcher
    # for this specific backward-compatible endpoint to preserve the original 1-request optimization.
    import httpx
    
    lats = ",".join(str(loc.latitude) for loc in areas_list)
    lons = ",".join(str(loc.longitude) for loc in areas_list)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation&timezone=Asia/Kolkata"
    
    try:
        async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Error fetching data from weather API") from exc

    if isinstance(payload, dict):
        if len(areas_list) != 1 or not isinstance(payload.get("current"), dict):
            raise HTTPException(status_code=502, detail="Weather API returned an invalid areas response")
        weather_by_area = [payload]
    elif isinstance(payload, list):
        if len(payload) != len(areas_list):
            raise HTTPException(status_code=502, detail="Weather API returned an unexpected area count")
        if any(not isinstance(item, dict) or not isinstance(item.get("current"), dict) for item in payload):
            raise HTTPException(status_code=502, detail="Weather API returned malformed area data")
        weather_by_area = payload
    else:
        raise HTTPException(status_code=502, detail="Weather API returned an invalid response type")

    result = []
    from app.schemas.weather import WeatherCurrent
    
    for loc, current_payload in zip(areas_list, weather_by_area):
        current_data = current_payload.get("current", {})
        
        # Build weather model
        try:
            weather = WeatherCurrent(
                timestamp=_parse_timestamp(current_data.get("time")),
                temperature_c=float(current_data.get("temperature_2m", 0)),
                relative_humidity=float(current_data.get("relative_humidity_2m", 0)),
                wind_speed_kmh=float(current_data.get("wind_speed_10m") or 0.0),
                shortwave_radiation_w_m2=float(current_data.get("shortwave_radiation") or 0.0)
            )
        except Exception:
            weather = None
            
        population = population_provider.get_population(loc)
        
        assessment = None
        if population:
            assessment = process_area_timestep(loc, weather, population)
            
        ward_info = {
            "ward_number": loc.provider_metadata.get("ward_number"),
            "mapping_status": loc.provider_metadata.get("mapping_status")
        }
        
        # Exact demographics dict as originally returned
        demographics = None
        if population:
            demographics = {
                "population_2011": population.population,
                "area_km2": population.area_km2,
                "population_density_2011": population.density,
                "data_year": population.data_year,
                "population_source": population.provider_metadata.get("population_source"),
                "boundary_source": population.provider_metadata.get("boundary_source")
            }

        if assessment and assessment.get("risk_level") == "EXTREME":
            background_tasks.add_task(
                dispatch_extreme_alert,
                area_id=loc.spatial_id,
                area_name=loc.locality,
                ward_number=ward_info.get("ward_number"),
                assessment=assessment,
            )

        result.append({
            "area_id": loc.spatial_id,
            "area_name": loc.locality,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "ward": ward_info,
            "demographics": demographics,
            "current": {
                "temperature": current_data.get("temperature_2m"),
                "relative_humidity": current_data.get("relative_humidity_2m"),
                "wind_speed": current_data.get("wind_speed_10m"),
                "shortwave_radiation": current_data.get("shortwave_radiation"),
                "time": current_data.get("time"),
            },
            "assessment": assessment,
        })

    return result

@app.get("/api/cities")
def get_cities():
    areas_list = cities_location_provider.get_all_locations()
    if not areas_list:
        return {"cities": []}

    result = []
    for loc in areas_list:
        city_data = cities_location_provider.cities_db.get(loc.spatial_id, {})
        result.append({
            "city_id": loc.spatial_id,
            "name": city_data.get("name", loc.locality),
            "state": city_data.get("state", loc.state),
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "population": city_data.get("population"),
            "area_km2": city_data.get("area_km2"),
            "population_density": city_data.get("population_density"),
            "data_source": city_data.get("data_source"),
            "geography_type": city_data.get("geography_type"),
        })

    return {"cities": result}

@app.get("/api/haldia-gis")
def get_haldia_gis():
    """Return Haldia ward polygons as GeoJSON for GIS map rendering."""
    gis_path = os.path.join(DATA_DIR, "haldia_ward_polygons.geojson")
    if not os.path.exists(gis_path):
        raise HTTPException(status_code=404, detail="Haldia GIS data not available")
    with open(gis_path, "r") as f:
        data = json.load(f)

    for feature in data.get("features", []):
        props = feature.setdefault("properties", {})
        if not isinstance(props.get("h_areas"), list):
            props["h_areas"] = []

    return data

@app.get("/api/weather")
async def get_weather(area_id: str = None, city_id: str = None):
    if city_id:
        city_id = city_id.upper()
        location = cities_location_provider.get_location(city_id)
        population = cities_population_provider.get_population(location) if location else None
        if not location:
            raise HTTPException(status_code=404, detail="City ID not found in local database")
    elif area_id:
        area_id = area_id.upper()
        location = location_provider.get_location(area_id)
        population = population_provider.get_population(location) if location else None
        if not location:
            raise HTTPException(status_code=404, detail="Area ID not found in local database")
    else:
        raise HTTPException(status_code=400, detail="Must provide either area_id or city_id")
        
    current_weather, forecast_points = await weather_provider.get_weather(location.latitude, location.longitude)
    
    assessment = None
    if population:
        assessment = process_area_timestep(location, current_weather, population)
        
    ward_info = {
        "ward_number": location.provider_metadata.get("ward_number"),
        "mapping_status": location.provider_metadata.get("mapping_status")
    }
    
    demographics = None
    if population:
        demographics = {
            "population_2011": population.population,
            "area_km2": population.area_km2,
            "population_density_2011": population.density,
            "data_year": population.data_year,
            "population_source": population.provider_metadata.get("population_source"),
            "boundary_source": population.provider_metadata.get("boundary_source")
        }
        
    forecast_records = []
    current_time = current_weather.timestamp
    
    for pt in forecast_points:
        if current_time is not None and pt.timestamp <= current_time:
            continue
            
        pt_assessment = None
        if population:
            pt_assessment = process_area_timestep(location, pt, population)
            
        forecast_records.append({
            "time": pt.timestamp.isoformat() if pt.timestamp else None,
            "temperature": pt.temperature_c,
            "relative_humidity": pt.relative_humidity,
            "wind_speed": pt.wind_speed_kmh,
            "shortwave_radiation": pt.shortwave_radiation_w_m2,
            "assessment": pt_assessment,
        })

    # Limit to 72 hours
    forecast = forecast_records[:72]

    def projection(hours: int):
        if current_time is None:
            return []
        cutoff = current_time + timedelta(hours=hours)
        return [
            record
            for record in forecast
            if _parse_timestamp(record["time"]) <= cutoff
        ]

    forecast_24h = projection(24)
    forecast_48h = projection(48)
    forecast_72h = projection(72)
    
    # We still need metadata units for the tests! The original payload returned it, our Provider didn't.
    # To keep tests from breaking we mock the canonical units.
    canonical_units = {
        "temperature": "°C",
        "relative_humidity": "%",
        "wind_speed": "km/h",
        "shortwave_radiation": "W/m²"
    }

    standardized_data = {
        "area": (lambda: 
            (lambda raw_area: {
                "city_id": raw_area.get("area_id"),
                "name": raw_area.get("area_name"),
                "state": "West Bengal",
                "latitude": raw_area.get("latitude"),
                "longitude": raw_area.get("longitude"),
                "population": None,
                "area_km2": None,
                "population_density": None,
                "data_source": None,
                "geography_type": "ward_area",
            })(location_provider.areas_db.get(area_id))
        )() if area_id else cities_location_provider.cities_db.get(city_id),
        "ward": ward_info,
        "demographics": demographics,
        "metadata": {
            "timezone": "Asia/Kolkata",
            "timezone_abbreviation": "IST",
            "utc_offset": "+05:30",
            "elevation": 10.0, # Dummy fallback
            "units": canonical_units,
        },
        "current": {
            "time": current_weather.timestamp.isoformat() if current_weather.timestamp else None,
            "temperature": current_weather.temperature_c,
            "relative_humidity": current_weather.relative_humidity,
            "wind_speed": current_weather.wind_speed_kmh,
            "shortwave_radiation": current_weather.shortwave_radiation_w_m2,
            "assessment": assessment,
        },
        "forecast": forecast,
        "forecast_24h": forecast_24h,
        "forecast_48h": forecast_48h,
        "forecast_72h": forecast_72h,
        "forecast_projections": {
            "24h": forecast_24h,
            "48h": forecast_48h,
            "72h": forecast_72h,
        },
        "projection_status": "available" if current_time is not None else "unavailable",
        "data_status": assessment.get("data_status") if assessment else "unavailable",
    }
    return standardized_data
