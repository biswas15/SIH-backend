from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

from app.schemas.location import LocationContext
from app.schemas.weather import WeatherCurrent, WeatherForecastPoint
from app.schemas.population import PopulationContext

class LocationProvider(ABC):
    """
    Abstract base class for location and geocoding services.
    """
    @abstractmethod
    def get_location(self, query: str) -> Optional[LocationContext]:
        """
        Retrieves a location context for a given query (e.g. area_id, address).
        Returns None if the location is not found.
        """
        pass

    @abstractmethod
    def get_all_locations(self) -> List[LocationContext]:
        """
        Retrieves all available locations. Useful for batch processing or list endpoints.
        """
        pass

class WeatherProvider(ABC):
    """
    Abstract base class for weather data services.
    """
    @abstractmethod
    async def get_weather(self, lat: float, lon: float) -> Tuple[WeatherCurrent, List[WeatherForecastPoint]]:
        """
        Retrieves current and forecasted weather for the given coordinates.
        Returns a tuple of (current_weather, list_of_forecast_points).
        """
        pass

class PopulationProvider(ABC):
    """
    Abstract base class for demographic data services.
    """
    @abstractmethod
    def get_population(self, location: LocationContext) -> Optional[PopulationContext]:
        """
        Retrieves demographic and exposure metrics for the given location context.
        Returns None if demographic data is unavailable for the location.
        """
        pass
