from typing import Any, Dict

from app.schemas.location import LocationContext
from app.schemas.weather import WeatherCurrent
from app.schemas.population import PopulationContext

from app.engine.thermal import thermal_stress_score, calculate_bom_wbgt
from app.engine.vulnerability import calculate_vulnerability
from app.engine.htsi import (
    calculate_htsi,
    classify_risk,
    generate_risk_drivers,
    generate_actions,
)
from app.engine.health_impact import generate_prototype_health_impact
from app.engine.affected_groups import derive_affected_groups
from app.engine.impact_actions import generate_contextual_actions


def process_area_timestep(
    location: LocationContext,
    weather: WeatherCurrent,
    population: PopulationContext | None
) -> Dict[str, Any]:
    """
    Common processing function for assessing heat risk at a location.
    Implements the full unified calculation pipeline using normalized domain models.
    """
    if weather is None or weather.temperature_c is None or weather.relative_humidity is None:
        return {
            "data_status": "unavailable"
        }

    # Extract needed fields
    temp_c = weather.temperature_c
    rh = weather.relative_humidity
    wind_kmh = weather.wind_speed_kmh
    radiation_w_m2 = weather.shortwave_radiation_w_m2
    
    # Population default logic based on prototype behavior
    # If no population density is available, vulnerability falls back, or the area is unmapped
    pop_density = population.density if population and population.density is not None else 0.0

    # If population is missing or 0, we can't do a full valid assessment, but the prototype
    # throws error or returns invalid if input is wrong. Actually, the prototype allows calculating 
    # thermal risk but vulnerability is 0. Let's trace back to what the prototype did. 
    # Prototype explicitly required pop_density in its function signature but allowed it to be 0.
    
    try:
        t_score_dict = thermal_stress_score(
            temp_c=temp_c,
            rh=rh,
            wind_kmh=wind_kmh,
            radiation_w_m2=radiation_w_m2
        )
        wbgt_proxy_c = calculate_bom_wbgt(temp_c, rh)
        t_score_dict["wbgt_proxy_c"] = wbgt_proxy_c
        
        # Calculate vulnerability using fixed prototype assumptions
        vuln_data = calculate_vulnerability(
            pop_density=pop_density,
            outdoor_worker_ratio=0.35,
            built_up_ratio=0.50
        )
        htsi_val = calculate_htsi(
            thermal_stress_score=t_score_dict["score"],
            vulnerability_score=vuln_data["vulnerability_score"]
        )
        risk_level = classify_risk(htsi_val)
        drivers = generate_risk_drivers(
            base_score=t_score_dict["base_score"],
            radiation_bonus=t_score_dict["radiation_bonus"],
            wind_relief=t_score_dict["wind_relief"],
            vulnerability_score=vuln_data["vulnerability_score"]
        )
        
        # Generate contextual actions (replaces static generate_actions)
        actions = generate_contextual_actions(
            risk_level=risk_level,
            risk_drivers=drivers,
            vulnerability=vuln_data,
            thermal_stress=t_score_dict,
        )
        
        # Derive affected population groups
        affected_groups = derive_affected_groups(
            risk_level=risk_level,
            risk_drivers=drivers,
            vulnerability=vuln_data,
            thermal_stress=t_score_dict,
        )
        
        health_impact = generate_prototype_health_impact(
            htsi=htsi_val,
            vulnerability_score=vuln_data["vulnerability_score"]
        )
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return {
            "data_status": "invalid",
            "error": "Weather or demographic input is invalid"
        }

    return {
        "risk_level": risk_level,
        "htsi": htsi_val,
        "thermal_stress": t_score_dict,
        "vulnerability": vuln_data,
        "health_impact": health_impact,
        "supporting_metrics": {
            "heat_index_c": t_score_dict["heat_index_c"],
            "wbgt_proxy_c": wbgt_proxy_c
        },
        "risk_drivers": drivers,
        "risk_driver_labels": {
            "high_heat_index": "High heat index",
            "high_solar_exposure": "High solar exposure",
            "wind_providing_relief": "Wind providing relief",
            "elevated_ward_vulnerability": "Elevated ward vulnerability",
        },
        "recommended_actions": actions,
        "affected_groups": affected_groups,
        "data_status": "available"
    }