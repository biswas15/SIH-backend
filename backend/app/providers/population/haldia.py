import json
import os
from typing import Optional

from app.schemas.location import LocationContext
from app.schemas.population import PopulationContext
from app.providers.base import PopulationProvider

class HaldiaDemoPopulationProvider(PopulationProvider):
    """
    Population provider that wraps the static Haldia JSON density file.
    """
    def __init__(self, data_dir: str):
        self.pop_density_file = os.path.join(data_dir, "haldia_population_density.json")
        self.pop_density_db = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.pop_density_file):
            with open(self.pop_density_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.pop_density_db = {item["ward_number"]: item for item in data}

    def get_population(self, location: LocationContext) -> Optional[PopulationContext]:
        # We extract ward_number from provider_metadata if it came from Haldia location provider
        metadata = location.provider_metadata
        ward_number = metadata.get("ward_number")
        
        if ward_number is None or ward_number not in self.pop_density_db:
            return None
            
        pop_data = self.pop_density_db[ward_number]
        
        return PopulationContext(
            population=pop_data.get("population_2011"),
            density=pop_data.get("population_density_2011"),
            area_km2=pop_data.get("area_km2"),
            data_year=pop_data.get("data_year"),
            provider="HaldiaDemoPopulationProvider",
            confidence_status="provisionally_verified",
            provider_metadata={
                "population_source": pop_data.get("population_source"),
                "boundary_source": pop_data.get("boundary_source"),
                "ward_number": ward_number
            }
        )
