import pytest
from app.engine.risk import calculate_risk_category, generate_risk_drivers, compute_ward_risk

def test_extreme_risk_wbgt_override():
    # A WBGT of 33.0 returns "Extreme" risk regardless of Heat Index.
    assert calculate_risk_category(wbgt=33.0, heat_index=30.0) == "Extreme"

def test_high_lst_anomaly():
    # High LST anomalies correctly append the Urban Heat Island driver string.
    drivers = generate_risk_drivers(wbgt=25.0, heat_index=28.0, lst_anomaly=1.6, rh=40.0)
    assert "Severe Urban Heat Island effect amplifying local temperature" in drivers

def test_safe_conditions():
    # Safe conditions (WBGT 25.0, HI 28.0, LST 0.5, RH 40.0) return "Low" risk and an empty drivers list.
    risk = compute_ward_risk(wbgt=25.0, heat_index=28.0, lst_anomaly=0.5, rh=40.0)
    assert risk["risk_category"] == "Low"
    assert len(risk["primary_drivers"]) == 0
