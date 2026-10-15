from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_weather_purba_medinipur():
    """Test /api/weather?state=West+Bengal&district=Purba+Medinipur."""
    response = client.get("/api/weather?state=West+Bengal&district=Purba+Medinipur")
    assert response.status_code == 200
    data = response.json()
    assert data["area"]["name"] == "Purba Medinipur"
    assert data["area"]["state"] == "West Bengal"
    assert "current" in data
    assert "assessment" in data["current"]
    assessment = data["current"]["assessment"]
    assert assessment is not None
    assert "risk_level" in assessment
    assert "htsi" in assessment
    assert 0 <= assessment["htsi"] <= 100
    assert len(data["forecast"]) > 0

def test_api_weather_srikakulam():
    """Test /api/weather?state=Andhra+Pradesh&district=Srikakulam."""
    response = client.get("/api/weather?state=Andhra+Pradesh&district=Srikakulam")
    assert response.status_code == 200
    data = response.json()
    assert data["area"]["name"] == "Srikakulam"
    assert data["area"]["state"] == "Andhra Pradesh"
    assert "current" in data
    assert "assessment" in data["current"]

def test_api_weather_district_only():
    """Test /api/weather?district=Srikakulam without state parameter."""
    response = client.get("/api/weather?district=Srikakulam")
    assert response.status_code == 200
    data = response.json()
    assert data["area"]["name"] == "Srikakulam"

def test_api_weather_invalid_district():
    """Test /api/weather?district=NonExistentDistrict returns 404."""
    response = client.get("/api/weather?district=NonExistentDistrictXYZ")
    assert response.status_code == 404

def test_api_districts_list():
    """Test /api/districts returns states and districts."""
    response = client.get("/api/districts")
    assert response.status_code == 200
    data = response.json()
    assert "states" in data
    assert "West Bengal" in data["states"]
    assert "Purba Medinipur" in data["states"]["West Bengal"]

def test_api_districts_filter_state():
    """Test /api/districts?state=Andhra+Pradesh."""
    response = client.get("/api/districts?state=Andhra+Pradesh")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "Andhra Pradesh"
    assert "Srikakulam" in data["districts"]
