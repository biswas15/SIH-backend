import json
import os
import re
import unicodedata
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
        normalized_query = str(query or "").strip().upper()
        if normalized_query in self.cities_db:
            return self._build_context(self.cities_db[normalized_query])
        return None

    @staticmethod
    def _normalize_name(value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()

    def resolve_location(self, state: str, district: str) -> Optional[LocationContext]:
        """Resolve the frontend's State -> District selection to a supported city.

        The prototype dataset is intentionally limited. Returning ``None`` for an
        unsupported district lets the API expose an honest data-unavailable state
        instead of attaching another city's weather or population to it.
        """
        state_key = self._normalize_name(state)
        district_key = self._normalize_name(district)
        if not state_key or not district_key:
            return None

        aliases = {
            ("west bengal", "purba medinipur"): "HALDIA",
            ("west bengal", "east medinipur"): "HALDIA",
            ("west bengal", "haldia"): "HALDIA",
            ("delhi", "new delhi"): "DELHI",
        }
        alias_id = aliases.get((state_key, district_key))
        if alias_id:
            return self.get_location(alias_id)

        for city_data in self.cities_db.values():
            if self._normalize_name(city_data.get("state", "")) != state_key:
                continue
            city_name = self._normalize_name(city_data.get("name", ""))
            if district_key == city_name:
                return self._build_context(city_data)
        return None

    def get_all_locations(self) -> List[LocationContext]:
        return [self._build_context(item) for item in self.cities_db.values()]
