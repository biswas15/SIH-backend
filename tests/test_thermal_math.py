"""
tests/test_thermal_math.py

pytest test suite for the Phase 3 thermal math engine.

Verifies deterministic correctness of:
  - downscale_temperature  (app.engine.downscale)
  - calculate_bom_wbgt     (app.engine.thermal)
  - calculate_heat_index   (app.engine.thermal)
  - compute_thermal_metrics (app.engine.thermal)
  - heat_index_c
  - thermal_stress_score
"""

import sys
import os

# Allow imports from the project root when running from tests/ or project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.engine.downscale import downscale_temperature
from app.engine.thermal import (
    calculate_vapor_pressure,
    calculate_bom_wbgt,
    calculate_heat_index,
    compute_thermal_metrics,
    heat_index_c,
    thermal_stress_score,
)


# ---------------------------------------------------------------------------
# downscale_temperature
# ---------------------------------------------------------------------------

class TestDownscaleTemperature:
    def test_positive_anomaly_increases_temperature(self):
        """Positive LST anomaly should raise ward temperature above macro temp."""
        result = downscale_temperature(35.0, 4.0)
        expected = round(35.0 + 0.35 * 4.0, 2)
        assert result == expected, f"Expected {expected}, got {result}"

    def test_negative_anomaly_decreases_temperature(self):
        """Negative LST anomaly (e.g. water body) should lower ward temperature."""
        result = downscale_temperature(35.0, -4.0)
        expected = round(35.0 + 0.35 * -4.0, 2)
        assert result == expected
        assert result < 35.0

    def test_zero_anomaly_returns_macro_temp(self):
        """Zero LST anomaly must return the macro temperature unchanged."""
        result = downscale_temperature(32.5, 0.0)
        assert result == 32.5

    def test_alpha_offset_is_accurate(self):
        """
        Downscaled temperature must accurately add alpha * lst_anomaly offset.
        Using a non-default alpha to confirm the parameter is respected.
        """
        macro_temp = 30.0
        lst_anomaly = 6.0
        alpha = 0.5
        result = downscale_temperature(macro_temp, lst_anomaly, alpha=alpha)
        expected = round(macro_temp + alpha * lst_anomaly, 2)
        assert result == expected  # 33.0

    def test_default_alpha_value(self):
        """Default alpha of 0.35 should be applied when not supplied."""
        result = downscale_temperature(40.0, 2.0)
        assert result == round(40.0 + 0.35 * 2.0, 2)  # 40.7

    def test_result_rounded_to_two_decimal_places(self):
        """Result must be rounded to exactly 2 decimal places."""
        result = downscale_temperature(33.333, 1.111)
        assert result == round(33.333 + 0.35 * 1.111, 2)


# ---------------------------------------------------------------------------
# calculate_vapor_pressure
# ---------------------------------------------------------------------------

class TestCalculateVaporPressure:
    def test_higher_humidity_gives_higher_vapor_pressure(self):
        """At the same temperature, higher RH must produce higher vapour pressure."""
        vp_high = calculate_vapor_pressure(35.0, 80.0)
        vp_low = calculate_vapor_pressure(35.0, 20.0)
        assert vp_high > vp_low

    def test_zero_rh_gives_zero_vapor_pressure(self):
        """0 % RH must return zero vapour pressure (completely dry air)."""
        result = calculate_vapor_pressure(35.0, 0.0)
        assert result == 0.0

    def test_100_rh_gives_saturation_vapor_pressure(self):
        """100 % RH must equal the saturation vapour pressure."""
        import math
        sat_vp = 6.105 * math.exp((17.27 * 30.0) / (237.7 + 30.0))
        result = calculate_vapor_pressure(30.0, 100.0)
        assert abs(result - sat_vp) < 0.001


# ---------------------------------------------------------------------------
# calculate_bom_wbgt
# ---------------------------------------------------------------------------

class TestCalculateBomWbgt:
    def test_no_wind_adjustment_included(self):
        """calculate_bom_wbgt must NOT include a wind argument."""
        # Using the new BOM proxy function signature, which dropped wind_speed_kmh
        wbgt = calculate_bom_wbgt(38.0, 60.0)
        assert isinstance(wbgt, float)
        assert wbgt > 38.0 # WBGT will be high for this temp/humidity combo


# ---------------------------------------------------------------------------
# calculate_heat_index (Deprecated)
# ---------------------------------------------------------------------------

class TestCalculateHeatIndex:
    def test_high_humidity_gives_higher_heat_index(self):
        """
        40°C + 75% RH must produce a higher Heat Index than 40°C + 20% RH.
        """
        hi_humid = calculate_heat_index(40.0, 75.0)
        hi_dry = calculate_heat_index(40.0, 20.0)
        assert hi_humid > hi_dry, (
            f"Expected hi_humid ({hi_humid}) > hi_dry ({hi_dry})"
        )

    def test_heat_index_above_apparent_temperature_in_humid_conditions(self):
        """
        In hot, humid conditions the Heat Index should exceed air temperature,
        reflecting the reduced capacity for evaporative cooling.
        """
        hi = calculate_heat_index(38.0, 85.0)
        assert hi > 38.0, f"Expected HI > 38°C in humid conditions, got {hi}"

    def test_returns_celsius(self):
        """Return value must be in Celsius (not Fahrenheit)."""
        hi = calculate_heat_index(40.0, 60.0)
        # If returned in °F this would be >> 100
        assert hi < 80.0, f"Expected Celsius value, got {hi} (likely Fahrenheit)"


# ---------------------------------------------------------------------------
# compute_thermal_metrics (wrapper - Deprecated)
# ---------------------------------------------------------------------------

class TestComputeThermalMetrics:
    def test_returns_required_keys(self):
        """Wrapper must return a dict with exactly the three required keys."""
        result = compute_thermal_metrics(35.0, 70.0, 10.0, 2.0)
        assert isinstance(result, dict)
        assert "downscaled_temp" in result
        assert "wbgt_proxy" in result
        assert "heat_index" in result

    def test_downscaled_temp_is_correct(self):
        """downscaled_temp must match the standalone downscale_temperature result."""
        macro_temp, lst_anomaly = 35.0, 4.0
        result = compute_thermal_metrics(macro_temp, 70.0, 10.0, lst_anomaly)
        expected_dt = downscale_temperature(macro_temp, lst_anomaly)
        assert result["downscaled_temp"] == expected_dt

    def test_positive_lst_anomaly_raises_all_metrics(self):
        """A positive LST anomaly should increase all three output metrics."""
        base = compute_thermal_metrics(35.0, 60.0, 10.0, lst_anomaly=0.0)
        hot = compute_thermal_metrics(35.0, 60.0, 10.0, lst_anomaly=5.0)
        assert hot["downscaled_temp"] > base["downscaled_temp"]
        assert hot["wbgt_proxy"] > base["wbgt_proxy"]
        assert hot["heat_index"] > base["heat_index"]


# ---------------------------------------------------------------------------
# New Thermal Math Tests
# ---------------------------------------------------------------------------

class TestHeatIndexC:
    def test_humidity_increases_perceived_heat(self):
        """1. Humidity increases perceived heat"""
        assert heat_index_c(40, 70) > heat_index_c(40, 20)

class TestThermalStressScore:
    def test_more_wind_lowers_thermal_stress(self):
        """2. More wind lowers thermal stress"""
        score_windy = thermal_stress_score(
            temp_c=40,
            rh=70,
            wind_kmh=20,
            radiation_w_m2=0
        )["score"]
        
        score_calm = thermal_stress_score(
            temp_c=40,
            rh=70,
            wind_kmh=0,
            radiation_w_m2=0
        )["score"]
        
        assert score_windy < score_calm
        
    def test_missing_radiation_is_valid(self):
        """3. Missing radiation is valid and omitted from inputs_used"""
        result = thermal_stress_score(
            temp_c=40,
            rh=70,
            wind_kmh=10,
            radiation_w_m2=None
        )
        assert "radiation" not in result["inputs_used"]
        assert result["radiation_bonus"] == 0.0

    def test_base_score_is_present(self):
        """base_score is present"""
        result = thermal_stress_score(temp_c=40, rh=70, wind_kmh=10, radiation_w_m2=None)
        assert "base_score" in result

    def test_score_remains_between_0_and_100(self):
        """score remains between 0 and 100"""
        # Test extreme cold
        cold_res = thermal_stress_score(temp_c=-10, rh=10, wind_kmh=100, radiation_w_m2=0)
        assert 0 <= cold_res["score"] <= 100
        
        # Test extreme heat
        hot_res = thermal_stress_score(temp_c=60, rh=100, wind_kmh=0, radiation_w_m2=1000)
        assert 0 <= hot_res["score"] <= 100
