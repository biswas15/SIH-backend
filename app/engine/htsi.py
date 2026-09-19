"""
app/engine/htsi.py

HTSI Engine — Thermal Stress Index, Risk Classifier,
Risk Driver Generator, and Action Recommendation System.

Final HTSI formula (unchanged weights):
    HTSI = 0.60 * thermal_stress_score + 0.40 * vulnerability_score

Risk bands (unchanged):
    LOW       =  0–25
    MODERATE  = 26–50
    HIGH      = 51–75
    EXTREME   = 76–100

All formulas are transparent, deterministic, and bounded to 0.0–100.0.
No ML, sklearn, or external libraries used.
"""

from app.engine.vulnerability import calculate_vulnerability, normalize_indicator


# ---------------------------------------------------------------------------
# HTSI calculation
# ---------------------------------------------------------------------------

def calculate_htsi(thermal_stress_score: float, vulnerability_score: float) -> int:
    """
    Calculates Human Thermal Stress Index (HTSI) on a 0 - 100 integer scale.
    Formula: HTSI = 0.60 * thermal_stress_score + 0.40 * vulnerability_score
    """
    htsi = (0.60 * thermal_stress_score) + (0.40 * vulnerability_score)
    return int(round(max(0.0, min(100.0, htsi))))


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def classify_risk(htsi: int) -> str:
    """
    Maps HTSI (0 - 100) to 4 tiers:
    0  - 25  → LOW
    26 - 50  → MODERATE
    51 - 75  → HIGH
    76 - 100 → EXTREME
    """
    if htsi <= 25:
        return "LOW"
    elif htsi <= 50:
        return "MODERATE"
    elif htsi <= 75:
        return "HIGH"
    else:
        return "EXTREME"


# ---------------------------------------------------------------------------
# Risk drivers (Step 5)
# ---------------------------------------------------------------------------

def generate_risk_drivers(
    base_score: float,
    radiation_bonus: float,
    wind_relief: float,
    vulnerability_score: float,
) -> list[str]:
    """
    Generates the authoritative list of risk contributing factors.

    Uses ONLY:
        base_score         — normalized Heat Index component (0-100)
        radiation_bonus    — prototype solar adjustment applied
        wind_relief        — prototype wind relief applied
        vulnerability_score — ward-level exposure score (0-100)

    Allowed driver keys:
        "high_heat_index"           when base_score >= 50
        "high_solar_exposure"       when radiation_bonus >= 3
        "wind_providing_relief"     when wind_relief >= 3  (risk reduction)
        "elevated_ward_vulnerability" when vulnerability_score >= 50

    No SHAP, LST, population density, raw humidity/wind thresholds,
    WBGT thresholds, or Heat Index thresholds other than the normalized
    base_score condition above.
    """
    drivers = []
    if base_score >= 50:
        drivers.append("high_heat_index")
    if radiation_bonus >= 3:
        drivers.append("high_solar_exposure")
    if wind_relief >= 3:
        drivers.append("wind_providing_relief")
    if vulnerability_score >= 50:
        drivers.append("elevated_ward_vulnerability")
    return drivers


# ---------------------------------------------------------------------------
# Action recommendations
# ---------------------------------------------------------------------------

def generate_actions(risk_level: str) -> list[str]:
    """Returns rule-based municipal action recommendations based on risk level."""
    actions_map = {
        "LOW": [
            "Normal monitoring of microclimate indicators"
        ],
        "MODERATE": [
            "Issue public heat advisory",
            "Monitor vulnerable populations and outdoor worker sites",
        ],
        "HIGH": [
            "Increase public drinking water availability",
            "Prepare and open designated cooling centers",
            "Adjust outdoor work hours for municipal and construction labor",
            "Send targeted alerts to vulnerable communities",
        ],
        "EXTREME": [
            "Activate emergency municipal heat-action plan",
            "Ensure 24/7 cooling center availability",
            "Alert local healthcare facilities for heat-stroke emergency readiness",
            "Issue urgent public alerts and restrict non-essential outdoor labor",
        ],
    }
    return actions_map.get(risk_level, actions_map["LOW"])


# ---------------------------------------------------------------------------
# DEPRECATED legacy helpers — kept only so test_htsi_engine.py imports resolve
# ---------------------------------------------------------------------------

def calculate_thermal_stress_score(
    downscaled_temp: float,
    min_temp: float = 20.0,
    max_temp: float = 45.0,
) -> float:
    """
    DEPRECATED — used only by test_htsi_engine.py legacy tests.
    New pipeline uses thermal_stress_score() from app.engine.thermal.
    Normalizes temperature to a 0.0 - 100.0 thermal stress scale.
    """
    return normalize_indicator(downscaled_temp, min_temp, max_temp)


def generate_risk_reasons(
    temp: float,
    rh: float,
    wind_speed: float,
    thermal_score: float,
    vuln_score: float,
) -> list[str]:
    """
    DEPRECATED — used only by test_htsi_engine.py legacy tests.
    Generates legacy human-readable explanations for local heat risk.
    The new pipeline uses generate_risk_drivers() instead.
    """
    reasons = []
    if temp >= 35.0:
        reasons.append(f"High temperature: {temp}°C")
    if rh >= 65.0:
        reasons.append(f"High relative humidity: {rh}%")
    if wind_speed <= 8.0:
        reasons.append("Low wind speed limiting convective cooling")
    if thermal_score >= 50.0:
        reasons.append("Elevated microclimate thermal stress")
    if vuln_score >= 50.0:
        reasons.append("High population and built-up exposure")
    return reasons


def compute_htsi_payload(
    downscaled_temp: float,
    rh: float,
    wind_speed_kmh: float,
    pop_density: float,
    outdoor_worker_ratio: float = 0.35,
    built_up_ratio: float = 0.50,
) -> dict:
    """
    DEPRECATED — used only by test_htsi_engine.py legacy tests.
    The new pipeline uses process_area_timestep() in main.py instead.
    Retained so existing test assertions do not break.
    """
    vuln_data = calculate_vulnerability(pop_density, outdoor_worker_ratio, built_up_ratio)
    vuln_score = vuln_data["vulnerability_score"]

    thermal_score = calculate_thermal_stress_score(downscaled_temp)
    htsi = calculate_htsi(thermal_score, vuln_score)
    risk_level = classify_risk(htsi)
    reasons = generate_risk_reasons(downscaled_temp, rh, wind_speed_kmh, thermal_score, vuln_score)
    actions = generate_actions(risk_level)

    return {
        "thermal_stress_score": thermal_score,
        "vulnerability_score": vuln_score,
        "htsi": htsi,
        "risk_level": risk_level,
        "reasons": reasons,
        "recommended_actions": actions,
    }
