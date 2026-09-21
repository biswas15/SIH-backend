from typing import Optional
from datetime import datetime
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class WeatherCurrent(BaseModel):
    """
    Provider-neutral representation of current weather conditions.
    """
    timestamp: Optional[datetime] = Field(None, description="Observation or forecast timestamp")
    temperature_c: Optional[float] = Field(None, description="Air temperature in degrees Celsius")
    relative_humidity: Optional[float] = Field(None, description="Relative humidity percentage (0-100)")
    wind_speed_kmh: Optional[float] = Field(None, description="Wind speed in km/h")
    shortwave_radiation_w_m2: Optional[float] = Field(None, description="Shortwave solar radiation in W/m²")

class WeatherForecastPoint(BaseModel):
    """
    Provider-neutral representation of a forecasted weather data point.
    """
    timestamp: Optional[datetime] = Field(None, description="Forecast timestamp")
    temperature_c: Optional[float] = Field(None, description="Air temperature in degrees Celsius")
    relative_humidity: Optional[float] = Field(None, description="Relative humidity percentage (0-100)")
    wind_speed_kmh: Optional[float] = Field(None, description="Wind speed in km/h")
    shortwave_radiation_w_m2: Optional[float] = Field(None, description="Shortwave solar radiation in W/m²")
