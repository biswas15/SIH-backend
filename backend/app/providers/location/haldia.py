import json
import os
from typing import List, Optional

from app.schemas.location import LocationContext
from app.providers.base import LocationProvider

class HaldiaDemoLocationProvider(LocationProvider):
    """
    Location provider that wraps the static Haldia JSON files for backward compatibility.
    """
    def __init__(self, data_dir: str):
        self.areas_file = os.path.join(data_dir, "..", "haldia_areas.json")
        self.ward_map_file = os.path.join(data_dir, "haldia_h_area_ward_map.json")
        self.areas_db = {}
        self.ward_map_db = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.areas_file):
            with open(self.areas_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    self.areas_db[item["area_id"]] = item
                    
        if os.path.exists(self.ward_map_file):
            with open(self.ward_map_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.ward_map_db = data.get("mapping", {})

    def _build_context(self, area_data: dict) -> LocationContext:
        area_id = area_data["area_id"]
        
        # Determine ward and mapping status
        ward_number = None
        mapping_status = "unmapped"
        if area_id in self.ward_map_db:
            mapping = self.ward_map_db[area_id]
            status = mapping.get("mapping_status")
            if status == "gis_verified":
                mapping_status = "mapped"
                ward_number = mapping.get("ward_number")
            elif status == "outside_municipal_boundary":
                mapping_status = "outside_boundary"
            else:
                mapping_status = status
                
        provider_metadata = {
            "area_name": area_data.get("area_name"),
            "ward_number": ward_number,
            "mapping_status": mapping_status
        }
        
        return LocationContext(
            latitude=area_data["latitude"],
            longitude=area_data["longitude"],
            country="India",
            state="West Bengal",
            district="Purba Medinipur",
            city="Haldia",
            locality=area_data.get("area_name"),
            spatial_id=area_id,
            provider="HaldiaDemoLocationProvider",
            provider_metadata=provider_metadata
        )

    def get_location(self, query: str) -> Optional[LocationContext]:
        # Treat query as area_id
        if query in self.areas_db:
            return self._build_context(self.areas_db[query])
        return None

    def get_all_locations(self) -> List[LocationContext]:
        return [self._build_context(item) for item in self.areas_db.values()]
