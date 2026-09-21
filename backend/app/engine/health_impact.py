"""
app/engine/health_impact.py

Prototype health impact indicator for the presentation.
"""

def generate_prototype_health_impact(htsi: int, vulnerability_score: float) -> dict:
    """
    Generates a prototype health impact indicator based purely on HTSI and vulnerability.
    """
    if htsi >= 76:
        level = "EXTREME"
    elif htsi >= 51:
        level = "HIGH"
    elif htsi >= 26:
        level = "MODERATE"
    else:
        level = "LOW"
        
    score = (htsi * 0.7) + (vulnerability_score * 0.3)

    return {
        "level": level,
        "score": round(score, 1),
        "status": "PROTOTYPE_ESTIMATED",
        "disclaimer": "Prototype heat-health impact indicator. Not a validated mortality or hospitalization prediction."
    }
