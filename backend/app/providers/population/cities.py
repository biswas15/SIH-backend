import json
import os
from typing import Optional

from app.schemas.location import LocationContext
from app.schemas.population import PopulationContext
from app.providers.base import PopulationProvider

class IndiaCitiesPopulationProvider(PopulationProvider):
    def __init__(self, data_dir: str):
        self.cities_file = os.path.join(data_dir, "india_cities.json")
        self.cities_db = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.cities_file):
            with open(self.cities_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("cities", []):
                    self.cities_db[item["city_id"]] = item

    def get_population(self, location: LocationContext) -> Optional[PopulationContext]:
        if location.spatial_id in self.cities_db:
            city_data = self.cities_db[location.spatial_id]
            pop = city_data.get("population", 0)
            area = city_data.get("area_km2", 1.0)
            density = pop / area if area > 0 else 0
            
            return PopulationContext(
                population=pop,
                density=density,
                area_km2=area,
                # Defaults for cities
                outdoor_worker_ratio=0.35,
                vulnerable_demographic_ratio=0.25,
                data_year=2011,
                provider="IndiaCitiesPopulationProvider",
                provider_metadata={
                    "population_source": "Census of India 2011",
                    "boundary_source": "Municipal bounds"
                }
            )
        return None
