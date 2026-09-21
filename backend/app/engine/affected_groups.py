"""
app/engine/affected_groups.py

Determines affected/vulnerable population groups from risk drivers
and vulnerability components.

All groups are qualitative/rule-based categories derived from available
prototype indicators. No fabricated demographic statistics.
"""

from typing import List, Dict, Any


def derive_affected_groups(
    risk_level: str,
    risk_drivers: List[str],
    vulnerability: Dict[str, Any],
    thermal_stress: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Derives affected population groups from available risk/vulnerability data.

    Returns a list of group objects with:
    - group: identifier
    - label: human-readable name
    - rationale: why this group is affected (based on drivers/vulnerability)
    - priority: "primary" | "secondary"
    """
    groups = []

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

    # Track which groups we've added
    added_groups = set()

    def add_group(group_id: str, label: str, rationale: str, priority: str = "primary"):
        if group_id not in added_groups:
            groups.append({
                "group": group_id,
                "label": label,
                "rationale": rationale,
                "priority": priority,
            })
            added_groups.add(group_id)

    # === DRIVER-BASED GROUPS ===

    # High heat index → affects everyone, but especially outdoor-exposed
    if "high_heat_index" in risk_drivers:
        add_group(
            "outdoor_workers",
            "Outdoor workers",
            "High heat index compounds physiological strain during outdoor physical activity",
            "primary"
        )
        add_group(
            "construction_workers",
            "Construction workers",
            "Prolonged exertion in direct sun with limited shade access",
            "primary"
        )
        add_group(
            "street_vendors",
            "Street vendors & informal workers",
            "Extended outdoor exposure with minimal cooling options",
            "secondary"
        )

    # High solar exposure → affects outdoor workers and those without shade
    if "high_solar_exposure" in risk_drivers:
        add_group(
            "outdoor_workers",
            "Outdoor workers",
            "High solar radiation increases heat load beyond air temperature alone",
            "primary"
        )
        if "construction_workers" not in added_groups:
            add_group(
                "construction_workers",
                "Construction workers",
                "Direct sun exposure on open sites with reflective surfaces",
                "secondary"
            )

    # Elevated ward vulnerability → depends on dominant component
    if "elevated_ward_vulnerability" in risk_drivers:
        if dominant_vuln == "outdoor_exposure" or outdoor_exposure_norm >= 50:
            add_group(
                "outdoor_workers",
                "Outdoor workers",
                "High outdoor workforce fraction in this area",
                "primary"
            )
            add_group(
                "transport_workers",
                "Transport workers",
                "Extended vehicle/outdoor exposure during peak heat",
                "secondary"
            )
        elif dominant_vuln == "builtup_exposure" or builtup_exposure_norm >= 50:
            add_group(
                "urban_residents",
                "Dense urban residents",
                "High built-up ratio amplifies urban heat island effect",
                "primary"
            )
            add_group(
                "elderly_urban",
                "Elderly in urban areas",
                "Reduced thermoregulation compounded by limited green space",
                "secondary"
            )
            add_group(
                "indoor_workers_no_ac",
                "Indoor workers without adequate cooling",
                "High indoor temperatures in poorly ventilated buildings",
                "secondary"
            )
        elif dominant_vuln == "population_density" or pop_density_norm >= 50:
            add_group(
                "dense_community_residents",
                "High-density community residents",
                "Crowded living conditions limit personal cooling capacity",
                "primary"
            )
            add_group(
                "low_income_households",
                "Low-income households",
                "Limited access to active cooling and healthcare",
                "secondary"
            )

    # Wind providing relief (negative driver) - note which groups benefit less
    if "wind_providing_relief" in risk_drivers:
        # Wind helps everyone, but less so for those in sheltered/built-up areas
        if dominant_vuln == "builtup_exposure":
            add_group(
                "indoor_workers_no_ac",
                "Indoor workers in sheltered buildings",
                "Limited natural ventilation benefit in dense built-up areas",
                "secondary"
            )

    # === RISK-LEVEL ESCALATION ===

    if risk_level in ["HIGH", "EXTREME"]:
        # At high/extreme risk, elderly and chronic illness groups become primary
        if "elderly_urban" not in added_groups:
            add_group(
                "elderly",
                "Elderly population",
                "Reduced thermoregulatory capacity at extreme heat levels",
                "primary"
            )
        if "chronic_illness" not in added_groups:
            add_group(
                "chronic_illness",
                "People with chronic conditions",
                "Cardiovascular, respiratory, and renal conditions exacerbated by heat stress",
                "primary"
            )
        if "children" not in added_groups:
            add_group(
                "children",
                "Young children",
                "Higher metabolic heat production and lower sweating capacity",
                "secondary"
            )

    # Ensure we always have at least some groups
    if not groups:
        add_group(
            "general_population",
            "General population",
            "Baseline heat exposure — monitor for symptoms",
            "secondary"
        )

    return groups


def get_group_summary(groups: List[Dict[str, Any]]) -> str:
    """Generates a human-readable summary of affected groups."""
    if not groups:
        return "No specific groups identified"
    
    primary = [g["label"] for g in groups if g["priority"] == "primary"]
    secondary = [g["label"] for g in groups if g["priority"] == "secondary"]
    
    parts = []
    if primary:
        parts.append(f"Most at risk: {', '.join(primary)}")
    if secondary:
        parts.append(f"Also affected: {', '.join(secondary)}")
    
    return ". ".join(parts) if parts else "General population"