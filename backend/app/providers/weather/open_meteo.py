import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from fastapi import HTTPException

from app.schemas.weather import WeatherCurrent, WeatherForecastPoint
from app.providers.base import WeatherProvider

IST = timezone(timedelta(hours=5, minutes=30))

class OpenMeteoProvider(WeatherProvider):
    """
    Weather provider using Open-Meteo API.
    """
    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds

    def _parse_timestamp(self, value) -> Optional[datetime]:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=IST)
            return parsed.astimezone(IST)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid timestamp format: {value}") from e

    async def get_weather(self, lat: float, lon: float) -> Tuple[WeatherCurrent, List[WeatherForecastPoint]]:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation&forecast_days=4&timezone=Asia/Kolkata"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Weather API request timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="Error fetching data from weather API") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"Weather API returned error status: {exc.response.status_code}") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Weather API returned malformed JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
            raise HTTPException(status_code=502, detail="Weather API response is missing current data")
            
        current_data = data["current"]
        try:
            t = current_data.get("temperature_2m")
            rh = current_data.get("relative_humidity_2m")
            w = current_data.get("wind_speed_10m")
            r = current_data.get("shortwave_radiation")
            
            current_weather = WeatherCurrent(
                timestamp=self._parse_timestamp(current_data.get("time")),
                temperature_c=float(t) if t is not None else None,
                relative_humidity=float(rh) if rh is not None else None,
                wind_speed_kmh=float(w) if w is not None else None,
                shortwave_radiation_w_m2=float(r) if r is not None else None
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=502, detail=f"Malformed current weather data: {e}")
            
        forecast_points = []
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])
        winds = hourly.get("wind_speed_10m", [])
        rads = hourly.get("shortwave_radiation", [])
        
        # Open-Meteo usually returns lists of same length, but we handle missing gracefully
        if times:
            for i in range(len(times)):
                try:
                    t = float(temps[i]) if i < len(temps) and temps[i] is not None else None
                    rh = float(rhs[i]) if i < len(rhs) and rhs[i] is not None else None
                    w = float(winds[i]) if i < len(winds) and winds[i] is not None else None
                    r = float(rads[i]) if i < len(rads) and rads[i] is not None else None
                    pt = WeatherForecastPoint(
                        timestamp=self._parse_timestamp(times[i]),
                        temperature_c=t,
                        relative_humidity=rh,
                        wind_speed_kmh=w,
                        shortwave_radiation_w_m2=r
                    )
                    forecast_points.append(pt)
                except (ValueError, TypeError):
                    continue

        return current_weather, forecast_points
