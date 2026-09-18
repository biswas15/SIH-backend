from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class MacroWeatherInput(BaseModel):
    temp_c: float = Field(..., description="Temperature in degrees Celsius")
    rh: float = Field(..., description="Relative humidity percentage (0-100)")
    wind_speed: float = Field(..., description="Wind speed in km/h")

    @field_validator("rh")
    @classmethod
    def validate_rh(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("Relative humidity (rh) must be between 0 and 100.")
        return v


class ThermalMetricsOutput(BaseModel):
    heat_index: float = Field(..., description="Calculated heat index in degrees Celsius")
    downscaled_temp: float = Field(..., description="Ward-level downscaled temperature in degrees Celsius")
    wbgt_proxy: Optional[float] = Field(None, description="Optional Wet Bulb Globe Temperature proxy")


class RiskDriver(BaseModel):
    code: str = Field(..., description="Identifier code for the risk driver")
    message: str = Field(..., description="Human-readable description of the risk driver")
    contribution_pct: Optional[float] = Field(None, description="Optional percentage contribution (0-100)")

    @field_validator("contribution_pct")
    @classmethod
    def validate_contribution_pct(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("contribution_pct must be between 0 and 100 when present.")
        return v


class WardRiskResponse(BaseModel):
    area_id: str = Field(..., description="Unique ward identifier (e.g. H01)")
    area_name: str = Field(..., description="Name of the ward")
    valid_at: str = Field(..., description="Timestamp for which the risk assessment is valid")
    htr_score: Optional[float] = Field(None, description="HeatSense Thermal Risk score")
    risk_level: Optional[str] = Field(None, description="HeatSense risk classification level")
    thermal_metrics: ThermalMetricsOutput = Field(..., description="Thermal stress metrics")
    top_drivers: List[RiskDriver] = Field(default_factory=list, description="List of key risk drivers")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended advisory actions")
    disclaimer: str = Field(
        default="Population-level decision support indicator only; not a medical diagnosis or mortality prediction.",
        description="Standard medical/decision support disclaimer"
    )
