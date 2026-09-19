"""
Tests for app/engine/htsi.py — Phases 4-7.
Run with: pytest tests/test_htsi_engine.py
"""

import pytest
from app.engine.htsi import (
    calculate_thermal_stress_score,
    calculate_htsi,
    classify_risk,
    generate_risk_reasons,
    generate_actions,
    compute_htsi_payload,
)


# ---------------------------------------------------------------------------
# classify_risk boundary tests
# ---------------------------------------------------------------------------

class TestClassifyRisk:
    def test_extreme_boundary(self):
        """HTSI = 81 must map to EXTREME."""
        assert classify_risk(81) == "EXTREME"

    def test_low_boundary(self):
        """HTSI = 20 must map to LOW."""
        assert classify_risk(20) == "LOW"

    def test_moderate_boundary_lower(self):
        """HTSI = 26 is the start of MODERATE."""
        assert classify_risk(26) == "MODERATE"

    def test_moderate_boundary_upper(self):
        """HTSI = 50 is still MODERATE."""
        assert classify_risk(50) == "MODERATE"

    def test_high_boundary_lower(self):
        """HTSI = 51 is the start of HIGH."""
        assert classify_risk(51) == "HIGH"

    def test_high_boundary_upper(self):
        """HTSI = 75 is still HIGH."""
        assert classify_risk(75) == "HIGH"

    def test_extreme_boundary_lower(self):
        """HTSI = 76 is the start of EXTREME."""
        assert classify_risk(76) == "EXTREME"

    def test_htsi_0_is_low(self):
        """HTSI = 0 is LOW."""
        assert classify_risk(0) == "LOW"

    def test_htsi_100_is_extreme(self):
        """HTSI = 100 is EXTREME."""
        assert classify_risk(100) == "EXTREME"


# ---------------------------------------------------------------------------
# calculate_htsi tests
# ---------------------------------------------------------------------------

class TestCalculateHTSI:
    def test_htsi_is_int(self):
        """calculate_htsi must return an int."""
        result = calculate_htsi(50.0, 50.0)
        assert isinstance(result, int)

    def test_htsi_bounded(self):
        """HTSI must never exceed 100 or go below 0."""
        assert 0 <= calculate_htsi(0.0, 0.0) <= 100
        assert 0 <= calculate_htsi(100.0, 100.0) <= 100

    def test_htsi_formula(self):
        """HTSI = round(0.60 * thermal + 0.40 * vuln), bounded to 0–100."""
        # 0.60*60 + 0.40*40 = 36 + 16 = 52
        assert calculate_htsi(60.0, 40.0) == 52


# ---------------------------------------------------------------------------
# calculate_thermal_stress_score tests
# ---------------------------------------------------------------------------

class TestThermalStressScore:
    def test_midpoint(self):
        """32.5°C (midpoint of 20–45) must produce ~50.0."""
        score = calculate_thermal_stress_score(32.5)
        assert score == pytest.approx(50.0, abs=1.0)

    def test_min_temp_produces_0(self):
        """20°C (min) must produce 0.0."""
        assert calculate_thermal_stress_score(20.0) == 0.0

    def test_max_temp_produces_100(self):
        """45°C (max) must produce 100.0."""
        assert calculate_thermal_stress_score(45.0) == 100.0


# ---------------------------------------------------------------------------
# compute_htsi_payload — integration tests
# ---------------------------------------------------------------------------

class TestComputeHTSIPayload:
    def test_mild_weather_low_or_moderate(self):
        """Mild weather (22°C, 40% RH, low pop density) must return LOW or MODERATE risk."""
        result = compute_htsi_payload(
            downscaled_temp=22.0,
            rh=40.0,
            wind_speed_kmh=15.0,
            pop_density=500.0,
        )
        assert result["risk_level"] in ("LOW", "MODERATE"), (
            f"Expected LOW or MODERATE, got {result['risk_level']} "
            f"(htsi={result['htsi']})"
        )

    def test_extreme_returns_nonempty_emergency_actions(self):
        """EXTREME risk must return non-empty recommended_actions containing emergency language."""
        result = compute_htsi_payload(
            downscaled_temp=45.0,
            rh=90.0,
            wind_speed_kmh=2.0,
            pop_density=10000.0,
            outdoor_worker_ratio=1.0,
            built_up_ratio=1.0,
        )
        assert result["risk_level"] == "EXTREME"
        assert len(result["recommended_actions"]) > 0
        actions_text = " ".join(result["recommended_actions"]).lower()
        assert "emergency" in actions_text, "EXTREME actions must mention emergency measures"

    def test_payload_keys_present(self):
        """compute_htsi_payload must return all six expected keys."""
        result = compute_htsi_payload(
            downscaled_temp=30.0, rh=60.0, wind_speed_kmh=10.0, pop_density=3000.0
        )
        expected = {"thermal_stress_score", "vulnerability_score", "htsi", "risk_level", "reasons", "recommended_actions"}
        assert expected == set(result.keys())

    def test_htsi_bounded_in_payload(self):
        """htsi value in payload must always be in [0, 100]."""
        result = compute_htsi_payload(
            downscaled_temp=50.0, rh=100.0, wind_speed_kmh=0.0, pop_density=99999.0
        )
        assert 0 <= result["htsi"] <= 100

    def test_risk_level_is_valid_tier(self):
        """risk_level must always be one of the four valid tiers."""
        valid_tiers = {"LOW", "MODERATE", "HIGH", "EXTREME"}
        for temp in [22.0, 30.0, 37.0, 45.0]:
            result = compute_htsi_payload(
                downscaled_temp=temp, rh=60.0, wind_speed_kmh=10.0, pop_density=3000.0
            )
            assert result["risk_level"] in valid_tiers


# ---------------------------------------------------------------------------
# generate_risk_reasons tests
# ---------------------------------------------------------------------------

class TestGenerateRiskReasons:
    def test_no_reasons_for_safe_conditions(self):
        """Safe conditions must produce an empty reasons list."""
        reasons = generate_risk_reasons(
            temp=25.0, rh=50.0, wind_speed=15.0, thermal_score=30.0, vuln_score=30.0
        )
        assert reasons == []

    def test_high_temp_reason_included(self):
        """temp >= 35 must produce a temperature reason."""
        reasons = generate_risk_reasons(
            temp=38.0, rh=50.0, wind_speed=15.0, thermal_score=30.0, vuln_score=30.0
        )
        assert any("temperature" in r.lower() for r in reasons)

    def test_high_rh_reason_included(self):
        """rh >= 65 must produce a humidity reason."""
        reasons = generate_risk_reasons(
            temp=25.0, rh=70.0, wind_speed=15.0, thermal_score=30.0, vuln_score=30.0
        )
        assert any("humidity" in r.lower() for r in reasons)

    def test_low_wind_reason_included(self):
        """wind_speed <= 8 must produce a wind speed reason."""
        reasons = generate_risk_reasons(
            temp=25.0, rh=50.0, wind_speed=5.0, thermal_score=30.0, vuln_score=30.0
        )
        assert any("wind" in r.lower() for r in reasons)
