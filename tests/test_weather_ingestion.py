import pytest
import httpx
from main import app, get_weather, get_areas

@pytest.mark.anyio
async def test_weather_endpoint_radiation_structure():
    """Verify /api/weather exposes shortwave_radiation in current and forecast entries."""
    result = await get_weather("H23")
    
    # Check current
    assert "current" in result
    assert "shortwave_radiation" in result["current"]
    
    # Check metadata units
    assert "metadata" in result
    assert "units" in result["metadata"]
    assert "shortwave_radiation" in result["metadata"]["units"]
    
    # Check forecast entries
    assert "forecast" in result
    assert len(result["forecast"]) > 0
    for entry in result["forecast"]:
        assert "shortwave_radiation" in entry

@pytest.mark.anyio
async def test_areas_endpoint_radiation_structure():
    """Verify /api/areas exposes shortwave_radiation in current dict for each area."""
    areas = await get_areas()
    assert len(areas) > 0
    for area in areas:
        assert "current" in area
        assert "shortwave_radiation" in area["current"]

@pytest.mark.anyio
async def test_weather_missing_radiation_handling(monkeypatch):
    """Verify API handles absent shortwave_radiation in current/hourly response gracefully (defaults to None)."""
    mock_response_data = {
        "elevation": 10.0,
        "hourly_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h"
            # shortwave_radiation unit omitted
        },
        "current": {
            "time": "2026-09-19T00:00",
            "temperature_2m": 28.5,
            "relative_humidity_2m": 80.0,
            "wind_speed_10m": 12.0
            # shortwave_radiation omitted
        },
        "hourly": {
            "time": ["2026-09-19T00:00", "2026-09-19T01:00", "2026-09-19T02:00"],
            "temperature_2m": [28.5, 28.0, 27.5],
            "relative_humidity_2m": [80, 82, 85],
            "wind_speed_10m": [12, 10, 8],
            "shortwave_radiation": [150.0]  # shorter array than time array
        }
    }
    
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return mock_response_data

    async def mock_get(self, url):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    
    res = await get_weather("H23")
    
    assert res["current"]["shortwave_radiation"] is None
    assert res["metadata"]["units"]["shortwave_radiation"] is None
    assert len(res["forecast"]) == 3
    assert res["forecast"][0]["shortwave_radiation"] == 150.0
    assert res["forecast"][1]["shortwave_radiation"] is None
    assert res["forecast"][2]["shortwave_radiation"] is None

@pytest.mark.anyio
async def test_weather_absent_radiation_array(monkeypatch):
    """Verify API does not crash if shortwave_radiation array is completely absent from hourly."""
    mock_response_data = {
        "elevation": 10.0,
        "hourly_units": {},
        "current": {},
        "hourly": {
            "time": ["2026-09-19T00:00"],
            "temperature_2m": [28.5]
            # shortwave_radiation key completely missing from hourly dict
        }
    }
    
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return mock_response_data

    async def mock_get(self, url):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    
    res = await get_weather("H23")
    assert res["forecast"][0]["shortwave_radiation"] is None
