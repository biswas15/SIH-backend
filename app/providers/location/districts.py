import json
import os
import re
from typing import List, Optional, Tuple

from app.schemas.location import LocationContext
from app.providers.base import LocationProvider


def _norm(s: str) -> str:
    """Normalize string by lowercasing and stripping non-alphanumeric chars."""
    return re.sub(r"[^a-z0-9]", "", s.lower()) if s else ""


class IndiaDistrictsLocationProvider(LocationProvider):
    """
    Location provider for all Indian districts across all states and union territories.
    Reads centroids from india_district_centroids.json.
    Supports case-insensitive, fuzzy-punctuation district and state lookup.
    """

    def __init__(self, data_dir: str):
        self.centroids_file = os.path.join(data_dir, "india_district_centroids.json")
        # Raw map: state -> district -> [lat, lon]
        self.raw_data: dict = {}
        # Lookup key: (norm_state, norm_district) -> (state, district, lat, lon)
        self._exact_map: dict = {}
        # Lookup key: norm_district -> list of (state, district, lat, lon)
        self._district_map: dict = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(self.centroids_file):
            with open(self.centroids_file, "r", encoding="utf-8") as f:
                self.raw_data = json.load(f)

            for state, dists in self.raw_data.items():
                norm_st = _norm(state)
                for district, coords in dists.items():
                    norm_dist = _norm(district)
                    lat, lon = float(coords[0]), float(coords[1])
                    entry = (state, district, lat, lon)
                    self._exact_map[(norm_st, norm_dist)] = entry
                    self._district_map.setdefault(norm_dist, []).append(entry)

    def _build_context(self, state: str, district: str, lat: float, lon: float) -> LocationContext:
        spatial_id = f"DISTRICT_{_norm(state).upper()}_{_norm(district).upper()}"
        return LocationContext(
            latitude=lat,
            longitude=lon,
            country="India",
            state=state,
            district=district,
            city=district,
            locality=district,
            spatial_id=spatial_id,
            provider="IndiaDistrictsLocationProvider",
            provider_metadata={
                "area_name": f"{district}, {state}",
                "district": district,
                "state": state,
                "geography_type": "district",
            },
        )

    def find_district(
        self, district: str, state: Optional[str] = None
    ) -> Optional[LocationContext]:
        if not district:
            return None

        norm_d = _norm(district)
        if state:
            norm_s = _norm(state)
            # 1. Try exact (state, district)
            if (norm_s, norm_d) in self._exact_map:
                st, dist, lat, lon = self._exact_map[(norm_s, norm_d)]
                return self._build_context(st, dist, lat, lon)

            # 2. Try prefix match on state
            for (st_key, dist_key), entry in self._exact_map.items():
                if dist_key == norm_d and (st_key.startswith(norm_s) or norm_s in st_key):
                    st, dist, lat, lon = entry
                    return self._build_context(st, dist, lat, lon)

        # 3. Fallback: match by district name alone
        matches = self._district_map.get(norm_d)
        if matches:
            st, dist, lat, lon = matches[0]
            return self._build_context(st, dist, lat, lon)

        # 4. Partial substring match on district name
        for dist_key, entries in self._district_map.items():
            if norm_d in dist_key or dist_key in norm_d:
                st, dist, lat, lon = entries[0]
                return self._build_context(st, dist, lat, lon)

        return None

    def get_location(self, query: str) -> Optional[LocationContext]:
        return self.find_district(query)

    def get_all_locations(self) -> List[LocationContext]:
        all_locs = []
        for entries in self._district_map.values():
            for st, dist, lat, lon in entries:
                all_locs.append(self._build_context(st, dist, lat, lon))
        return all_locs
