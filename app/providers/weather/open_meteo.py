import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from fastapi import HTTPException

from app.schemas.weather import WeatherCurrent, WeatherForecastPoint
from app.providers.base import WeatherProvider

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


class OpenMeteoProvider(WeatherProvider):
    """
    Weather provider using Open-Meteo API.

    Responses are cached in-memory for CACHE_TTL_MINUTES (default 15) to
    avoid hammering the upstream API on burst requests for the same location.
    The cache is keyed by (lat rounded to 2dp, lon rounded to 2dp), so
    calls within ~1 km share an entry.
    """

    CACHE_TTL_MINUTES = 15

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds
        # _cache maps (lat_key, lon_key) -> (cached_at, current, forecast_points)
        self._cache: dict = {}

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(lat: float, lon: float) -> tuple:
        """Round to 2 d.p. so nearby coordinates share a cache slot."""
        return (round(lat, 2), round(lon, 2))

    def _cache_get(self, key: tuple) -> Optional[Tuple]:
        """Return (current, forecast_points) if cached and fresh, else None."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        cached_at, current, forecast_points = entry
        age_s = (datetime.now(tz=IST) - cached_at).total_seconds()
        if age_s > self.CACHE_TTL_MINUTES * 60:
            del self._cache[key]
            return None
        logger.debug("Open-Meteo cache HIT for key=%s (age %.0fs)", key, age_s)
        return current, forecast_points

    def _cache_put(self, key: tuple, current, forecast_points) -> None:
        self._cache[key] = (datetime.now(tz=IST), current, forecast_points)

    def clear_cache(self) -> None:
        """Clear all cached weather responses."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def get_weather(
        self, lat: float, lon: float
    ) -> Tuple[WeatherCurrent, List[WeatherForecastPoint]]:
        cache_key = self._cache_key(lat, lon)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation"
            "&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation"
            "&forecast_days=4&timezone=Asia/Kolkata"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error("Open-Meteo TIMEOUT lat=%s lon=%s: %s", lat, lon, exc)
            raise HTTPException(status_code=504, detail="Weather API request timed out") from exc
        except httpx.RequestError as exc:
            logger.error("Open-Meteo REQUEST ERROR lat=%s lon=%s: %s", lat, lon, exc)
            raise HTTPException(status_code=502, detail="Error fetching data from weather API") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Open-Meteo HTTP %s lat=%s lon=%s body=%s",
                exc.response.status_code, lat, lon, exc.response.text[:300],
            )
            raise HTTPException(
                status_code=502,
                detail=f"Weather API returned error status: {exc.response.status_code}",
            ) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Open-Meteo MALFORMED JSON lat=%s lon=%s: %s", lat, lon, exc)
            raise HTTPException(status_code=502, detail="Weather API returned malformed JSON") from exc

        if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
            raise HTTPException(status_code=502, detail="Weather API response is missing current data")

        current_data = data["current"]
        try:
            t  = current_data.get("temperature_2m")
            rh = current_data.get("relative_humidity_2m")
            w  = current_data.get("wind_speed_10m")
            r  = current_data.get("shortwave_radiation")

            current_weather = WeatherCurrent(
                timestamp=self._parse_timestamp(current_data.get("time")),
                temperature_c=float(t) if t is not None else None,
                relative_humidity=float(rh) if rh is not None else None,
                wind_speed_kmh=float(w) if w is not None else None,
                shortwave_radiation_w_m2=float(r) if r is not None else None,
            )
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=502, detail=f"Malformed current weather data: {e}") from e

        forecast_points: List[WeatherForecastPoint] = []
        hourly = data.get("hourly", {})
        times  = hourly.get("time", [])
        temps  = hourly.get("temperature_2m", [])
        rhs    = hourly.get("relative_humidity_2m", [])
        winds  = hourly.get("wind_speed_10m", [])
        rads   = hourly.get("shortwave_radiation", [])

        if times:
            for i in range(len(times)):
                try:
                    t  = float(temps[i]) if i < len(temps) and temps[i] is not None else None
                    rh = float(rhs[i])   if i < len(rhs)   and rhs[i]   is not None else None
                    w  = float(winds[i]) if i < len(winds) and winds[i]  is not None else None
                    r  = float(rads[i])  if i < len(rads)  and rads[i]   is not None else None
                    pt = WeatherForecastPoint(
                        timestamp=self._parse_timestamp(times[i]),
                        temperature_c=t,
                        relative_humidity=rh,
                        wind_speed_kmh=w,
                        shortwave_radiation_w_m2=r,
                    )
                    forecast_points.append(pt)
                except (ValueError, TypeError):
                    continue

        self._cache_put(cache_key, current_weather, forecast_points)
        logger.debug("Open-Meteo cache MISS stored key=%s", cache_key)
        return current_weather, forecast_points
