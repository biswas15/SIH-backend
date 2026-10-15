"""
conftest.py -- pytest root configuration.
Ensures the repo root is on sys.path so that 'app.*' imports work
from any test module in tests/ or the repo root.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture(autouse=True)
def clear_weather_cache():
    try:
        from main import weather_provider
        if hasattr(weather_provider, "clear_cache"):
            weather_provider.clear_cache()
    except Exception:
        pass
    yield
    try:
        from main import weather_provider
        if hasattr(weather_provider, "clear_cache"):
            weather_provider.clear_cache()
    except Exception:
        pass
