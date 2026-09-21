"""
app/engine/impact_actions.py

Generates context-aware recommended actions from risk level,
risk drivers, and vulnerability components.

Actions are rule-based and deterministic. No ML.
"""

from typing import List, Dict, Any


def generate_contextual_actions(
    risk_level: str,
    risk_drivers: List[str],
    vulnerability: Dict[str, Any],
    thermal_stress: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Generates recommended actions based on risk context.

    Returns list of action objects with:
    - action: specific action description
    - category: thematic category
    - priority: "immediate" | "short_term" | "ongoing"
    - targets: which affected groups this addresses
    - rationale: why this action given the risk drivers
    """
    actions = []

    vuln_score = vulnerability.get("vulnerability_score", 0)
    pop_density_norm = vulnerability.get("pop_density_norm", 0)
    outdoor_exposure_norm = vulnerability.get("outdoor_exposure_norm", 0)
    builtup_exposure_norm = vulnerability.get("builtup_exposure_norm", 0)

    base_score = thermal_stress.get("base_score", 0)
    radiation_bonus = thermal_stress.get("radiation_bonus", 0)
    wind_relief = thermal_stress.get("wind_relief", 0)

    # Determine dominant vulnerability component
    vuln_components = {
        "population_density": pop_density_norm,
        "outdoor_exposure": outdoor_exposure_norm,
        "builtup_exposure": builtup_exposure_norm,
    }
    dominant_vuln = max(vuln_components, key=vuln_components.get) if any(v > 0 for v in vuln_components.values()) else None

    def add_action(action: str, category: str, priority: str, targets: List[str], rationale: str):
        actions.append({
            "action": action,
            "category": category,
            "priority": priority,
            "targets": targets,
            "rationale": rationale,
        })

    # === BASE ACTIONS BY RISK LEVEL ===

    if risk_level == "LOW":
        add_action(
            "Continue routine microclimate monitoring",
            "monitoring",
            "ongoing",
            ["general_population"],
            "Baseline conditions — maintain situational awareness"
        )

    elif risk_level == "MODERATE":
        add_action(
            "Issue public heat advisory with hydration guidance",
            "communication",
            "immediate",
            ["general_population", "outdoor_workers", "elderly"],
            "Elevated heat index warrants public awareness"
        )
        add_action(
            "Ensure drinking water access at public locations",
            "water_access",
            "immediate",
            ["outdoor_workers", "street_vendors", "transit_users"],
            "Prevent dehydration during prolonged exposure"
        )
        add_action(
            "Advise vulnerable populations to limit peak-hour outdoor activity",
            "behavioral",
            "immediate",
            ["elderly", "children", "chronic_illness"],
            "Reduce exposure during highest heat index hours"
        )

    elif risk_level == "HIGH":
        add_action(
            "Activate designated cooling centers with extended hours",
            "cooling_infrastructure",
            "immediate",
            ["elderly", "urban_residents", "indoor_workers_no_ac", "low_income_households"],
            "High heat index + vulnerability requires refuge access"
        )
        add_action(
            "Deploy mobile water distribution points in high-density areas",
            "water_access",
            "immediate",
            ["dense_community_residents", "outdoor_workers", "street_vendors"],
            "High population density + heat stress requires distributed water access"
        )
        add_action(
            "Issue work-rest cycle guidance for outdoor labor (15 min rest per hour)",
            "occupational_health",
            "immediate",
            ["outdoor_workers", "construction_workers"],
            "Physiological strain at high heat index requires structured rest"
        )
        add_action(
            "Advise rescheduling non-essential outdoor work to early morning/evening",
            "occupational_health",
            "short_term",
            ["construction_workers", "municipal_workers", "landscaping"],
            "Avoid peak heat index hours (11 AM - 4 PM)"
        )
        add_action(
            "Increase health worker outreach to elderly and chronic illness patients",
            "healthcare",
            "immediate",
            ["elderly", "chronic_illness"],
            "High heat exacerbates cardiovascular/respiratory conditions"
        )

    elif risk_level == "EXTREME":
        add_action(
            "Activate emergency municipal heat-action plan (24/7 operations)",
            "emergency_management",
            "immediate",
            ["general_population"],
            "EXTREME risk requires coordinated multi-agency response"
        )
        add_action(
            "Open all cooling centers 24/7 with transport coordination",
            "cooling_infrastructure",
            "immediate",
            ["elderly", "urban_residents", "low_income_households", "indoor_workers_no_ac", "homeless"],
            "Continuous cooling access required for survival"
        )
        add_action(
            "Issue urgent public alerts via SMS, radio, TV, and municipal channels",
            "communication",
            "immediate",
            ["general_population"],
            "Life-threatening conditions require maximum reach"
        )
        add_action(
            "Restrict non-essential outdoor labor; enforce work stoppage if needed",
            "occupational_health",
            "immediate",
            ["construction_workers", "municipal_workers", "industrial_workers"],
            "Physiological strain exceeds safe limits for physical exertion"
        )
        add_action(
            "Alert hospitals/EMS for heat-stroke emergency readiness; pre-position ambulances",
            "healthcare",
            "immediate",
            ["elderly", "chronic_illness", "outdoor_workers"],
            "Extreme heat index predicts heat-stroke incidence surge"
        )
        add_action(
            "Prioritize welfare checks on isolated elderly and medically vulnerable",
            "healthcare",
            "immediate",
            ["elderly", "chronic_illness", "socially_isolated"],
            "Highest mortality risk in socially isolated vulnerable populations"
        )
        add_action(
            "Deploy water tankers to all high-density and informal settlements",
            "water_access",
            "immediate",
            ["dense_community_residents", "low_income_households", "informal_settlements"],
            "Water security critical at extreme heat index"
        )

    # === DRIVER-SPECIFIC ACTIONS ===

    # High heat index (base_score >= 50)
    if "high_heat_index" in risk_drivers:
        add_action(
            "Emphasize heat index (feels-like) in all public communications, not just air temperature",
            "communication",
            "immediate",
            ["general_population"],
            "Heat index better represents physiological strain than temperature alone"
        )
        add_action(
            "Advise employers to provide shaded rest areas and cool water for outdoor workers",
            "occupational_health",
            "immediate",
            ["outdoor_workers", "construction_workers", "street_vendors"],
            "High heat index requires workplace heat-illness prevention"
        )

    # High solar exposure (radiation_bonus >= 3)
    if "high_solar_exposure" in risk_drivers:
        add_action(
            "Recommend wide-brimmed hats, UV-protective clothing, and sunscreen for outdoor exposure",
            "personal_protection",
            "immediate",
            ["outdoor_workers", "construction_workers", "street_vendors", "children"],
            "High solar radiation increases radiative heat load and UV damage risk"
        )
        add_action(
            "Deploy temporary shade structures at transit stops, markets, and work sites",
            "cooling_infrastructure",
            "short_term",
            ["street_vendors", "transit_users", "outdoor_workers"],
            "Direct solar radiation significantly increases heat stress beyond air temperature"
        )

    # Wind providing relief (wind_relief >= 3) - note limitation
    if "wind_providing_relief" in risk_drivers:
        add_action(
            "Encourage natural ventilation in buildings; open windows during cooler hours",
            "building_cooling",
            "ongoing",
            ["indoor_workers_no_ac", "urban_residents", "elderly"],
            "Available wind can enhance evaporative and convective cooling"
        )

    # Elevated ward vulnerability - specific to dominant component
    if "elevated_ward_vulnerability" in risk_drivers:
        if dominant_vuln == "outdoor_exposure" or outdoor_exposure_norm >= 50:
            add_action(
                "Target heat-health messaging to industrial zones and construction sites",
                "communication",
                "immediate",
                ["outdoor_workers", "construction_workers", "industrial_workers"],
                "High outdoor workforce fraction requires workplace-focused interventions"
            )
            add_action(
                "Coordinate with labor department for heat-safety compliance inspections",
                "occupational_health",
                "short_term",
                ["construction_workers", "industrial_workers"],
                "High outdoor exposure fraction warrants regulatory oversight"
            )

        elif dominant_vuln == "builtup_exposure" or builtup_exposure_norm >= 50:
            add_action(
                "Promote cool-roof/green-roof initiatives for municipal buildings",
                "urban_cooling",
                "long_term",
                ["urban_residents", "indoor_workers_no_ac"],
                "High built-up ratio amplifies urban heat island; structural mitigation needed"
            )
            add_action(
                "Increase tree canopy and green corridors in dense built-up zones",
                "urban_cooling",
                "long_term",
                ["urban_residents", "elderly_urban", "children"],
                "Vegetation reduces surface temperatures and provides shade"
            )
            add_action(
                "Audit building codes for passive cooling requirements in new construction",
                "policy",
                "long_term",
                ["indoor_workers_no_ac", "future_residents"],
                "Prevent lock-in of heat-vulnerable building stock"
            )

        elif dominant_vuln == "population_density" or pop_density_norm >= 50:
            add_action(
                "Establish neighborhood cooling hubs within walking distance in dense wards",
                "cooling_infrastructure",
                "immediate",
                ["dense_community_residents", "elderly", "low_income_households"],
                "High density limits home cooling; community access essential"
            )
            add_action(
                "Coordinate with community leaders for door-to-door welfare checks",
                "community_engagement",
                "immediate",
                ["elderly", "socially_isolated", "low_income_households"],
                "Dense communities may have hidden vulnerable individuals"
            )

    # Remove duplicates (same action text)
    seen = set()
    unique_actions = []
    for a in actions:
        key = a["action"]
        if key not in seen:
            seen.add(key)
            unique_actions.append(a)

    # Sort by priority: immediate > short_term > ongoing > long_term
    priority_order = {"immediate": 0, "short_term": 1, "ongoing": 2, "long_term": 3}
    unique_actions.sort(key=lambda x: priority_order.get(x["priority"], 99))

    return unique_actions


def get_action_summary(actions: List[Dict[str, Any]]) -> str:
    """Generates a brief human-readable action summary."""
    if not actions:
        return "No specific actions recommended"
    
    immediate = [a["action"] for a in actions if a["priority"] == "immediate"]
    return f"{len(immediate)} immediate action{'s' if len(immediate) != 1 else ''} required"