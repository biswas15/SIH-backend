import json
import os
from typing import List, Optional

from app.schemas.location import LocationContext
from app.providers.base import LocationProvider

class IndiaCitiesLocationProvider(LocationProvider):
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

    def _build_context(self, city_data: dict) -> LocationContext:
        return LocationContext(
            latitude=city_data["latitude"],
            longitude=city_data["longitude"],
            country="India",
            state=city_data["state"],
            district=city_data["name"],
            city=city_data["name"],
            locality=city_data["name"],
            spatial_id=city_data["city_id"],
            provider="IndiaCitiesLocationProvider",
            provider_metadata={
                "area_name": city_data["name"]
            }
        )

    def get_location(self, query: str) -> Optional[LocationContext]:
        if query in self.cities_db:
            return self._build_context(self.cities_db[query])
        return None

    def get_all_locations(self) -> List[LocationContext]:
        return [self._build_context(item) for item in self.cities_db.values()]
