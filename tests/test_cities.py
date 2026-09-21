import json
import os
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CITIES_FILE = os.path.join(DATA_DIR, "india_cities.json")


def test_cities_json_loads():
    """Test that the cities JSON file loads and has valid structure."""
    assert os.path.exists(CITIES_FILE), "india_cities.json not found"
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "cities" in data, "Missing 'cities' key"
    assert isinstance(data["cities"], list), "cities should be a list"
    assert len(data["cities"]) >= 12, "Should have at least 12 cities"
    for city in data["cities"]:
        assert "city_id" in city, "Missing city_id"
        assert "name" in city, "Missing name"
        assert "state" in city, "Missing state"
        assert "latitude" in city, "Missing latitude"
        assert "longitude" in city, "Missing longitude"
        assert "population" in city, "Missing population"
        assert "area_km2" in city, "Missing area_km2"
        assert "population_density" in city, "Missing population_density"
        assert "data_source" in city, "Missing data_source"
        assert "geography_type" in city, "Missing geography_type"


def test_city_ids_unique():
    """Test that all city_ids are unique."""
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    city_ids = [city["city_id"] for city in data["cities"]]
    assert len(city_ids) == len(set(city_ids)), "Duplicate city_ids found"


def test_coordinates_valid():
    """Test that coordinates are valid lat/lon."""
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for city in data["cities"]:
        lat = city["latitude"]
        lon = city["longitude"]
        assert -90 <= lat <= 90, f"Invalid latitude for {city['city_id']}: {lat}"
        assert -180 <= lon <= 180, f"Invalid longitude for {city['city_id']}: {lon}"


def test_population_area_consistency():
    """Test population and area are positive numbers."""
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for city in data["cities"]:
        assert city["population"] > 0, f"Population must be positive for {city['city_id']}"
        assert city["area_km2"] > 0, f"Area must be positive for {city['city_id']}"


def test_population_density_calculation():
    """Test that population_density = population / area_km2 (within rounding)."""
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for city in data["cities"]:
        expected = round(city["population"] / city["area_km2"], 1)
        actual = city["population_density"]
        assert abs(expected - actual) < 0.1, f"Density mismatch for {city['city_id']}: expected {expected}, got {actual}"


def test_api_cities_endpoint():
    """Test /api/cities returns successfully with correct structure."""
    response = client.get("/api/cities")
    assert response.status_code == 200
    data = response.json()
    assert "cities" in data, "Response missing 'cities' key"
    assert isinstance(data["cities"], list), "cities should be a list"
    assert len(data["cities"]) >= 12, "Should return at least 12 cities"
    for city in data["cities"]:
        assert "city_id" in city, "Missing city_id in response"
        assert "name" in city, "Missing name in response"
        assert "state" in city, "Missing state in response"
        assert "latitude" in city, "Missing latitude in response"
        assert "longitude" in city, "Missing longitude in response"
        assert "population" in city, "Missing population in response"
        assert "area_km2" in city, "Missing area_km2 in response"
        assert "population_density" in city, "Missing population_density in response"
        assert "data_source" in city, "Missing data_source in response"
        assert "geography_type" in city, "Missing geography_type in response"


def test_api_weather_city_id():
    """Test /api/weather?city_id=... works for a valid city."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    assert "current" in data, "Missing current weather"
    assert "forecast" in data, "Missing forecast"
    assert "forecast_24h" in data, "Missing forecast_24h"
    assert "forecast_48h" in data, "Missing forecast_48h"
    assert "forecast_72h" in data, "Missing forecast_72h"
    assert "assessment" in data["current"], "Missing assessment in current"
    assessment = data["current"]["assessment"]
    assert assessment is not None, "Assessment should not be None"
    assert "risk_level" in assessment, "Missing risk_level"
    assert "htsi" in assessment, "Missing htsi"
    assert "thermal_stress" in assessment, "Missing thermal_stress"
    assert "vulnerability" in assessment, "Missing vulnerability"
    assert "health_impact" in assessment, "Missing health_impact"
    assert "risk_drivers" in assessment, "Missing risk_drivers"
    assert "recommended_actions" in assessment, "Missing recommended_actions"


def test_api_weather_invalid_city_id():
    """Test /api/weather?city_id=INVALID returns 404."""
    response = client.get("/api/weather?city_id=INVALID_CITY")
    assert response.status_code == 404


def test_city_risk_calculation_valid_htsi():
    """Test that city risk calculation produces valid HTSI (0-100)."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    assessment = data["current"]["assessment"]
    htsi = assessment["htsi"]
    assert 0 <= htsi <= 100, f"HTSI out of range: {htsi}"


def test_city_risk_level_valid():
    """Test that risk level is one of the expected values."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    risk_level = data["current"]["assessment"]["risk_level"]
    assert risk_level in ["LOW", "MODERATE", "HIGH", "EXTREME"], f"Invalid risk level: {risk_level}"


def test_prototype_health_impact_exists():
    """Test that prototype health impact object exists in assessment."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    health_impact = data["current"]["assessment"]["health_impact"]
    assert health_impact is not None, "health_impact should not be None"
    assert "level" in health_impact, "Missing level in health_impact"
    assert "score" in health_impact, "Missing score in health_impact"
    assert "status" in health_impact, "Missing status in health_impact"
    assert "disclaimer" in health_impact, "Missing disclaimer in health_impact"


def test_health_impact_status_prototype_estimated():
    """Test that health impact status is PROTOTYPE_ESTIMATED."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    health_impact = data["current"]["assessment"]["health_impact"]
    assert health_impact["status"] == "PROTOTYPE_ESTIMATED", f"Expected PROTOTYPE_ESTIMATED, got {health_impact['status']}"


def test_health_impact_level_valid():
    """Test that health impact level is valid."""
    response = client.get("/api/weather?city_id=KOLKATA")
    assert response.status_code == 200
    data = response.json()
    level = data["current"]["assessment"]["health_impact"]["level"]
    assert level in ["LOW", "MODERATE", "HIGH", "EXTREME"], f"Invalid health impact level: {level}"