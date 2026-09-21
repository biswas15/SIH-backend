"""
app/engine/gis.py

Parses KML/KMZ ward boundary data and converts to GeoJSON
for frontend map rendering.

Run extract_ward_polygons.py once to generate data/haldia_ward_polygons.geojson
"""

import json
import os
import zipfile
from typing import Dict, List, Any, Optional
from xml.etree import ElementTree as ET

KML_NS_OGC = "{http://www.opengis.net/kml/2.2}"
KML_NS_GOOGLE = "{http://earth.google.com/kml/2.2}"
GX_NS = "{http://www.google.com/kml/ext/2.2}"


def parse_coordinates(coord_str: str) -> List[List[float]]:
    """Parse KML coordinate string into list of [lon, lat] pairs."""
    coords = []
    for part in coord_str.strip().split():
        if part:
            try:
                lon, lat, *_ = map(float, part.split(","))
                coords.append([lon, lat])
            except ValueError:
                continue
    return coords


def _extract_polygons_from_root(root, ns: str) -> Dict[int, List[List[List[float]]]]:
    """Extract ward polygons from KML root element with given namespace."""
    ward_polygons = {}

    for placemark in root.iter(f"{ns}Placemark"):
        ward_num = None
        
        name_elem = placemark.find(f"{ns}name")
        if name_elem is not None and name_elem.text:
            try:
                ward_num = int(name_elem.text.strip())
            except ValueError:
                pass
        
        if ward_num is None:
            desc_elem = placemark.find(f"{ns}description")
            if desc_elem is not None and desc_elem.text:
                import re
                match = re.search(r"<td>Name</td>\s*<td>(\d+)</td>", desc_elem.text)
                if match:
                    ward_num = int(match.group(1))

        if ward_num is None:
            continue

        polygons = []
        
        for geom in placemark.iter(f"{ns}Polygon"):
            outer = geom.find(f"{ns}outerBoundaryIs")
            if outer is not None:
                linear_ring = outer.find(f"{ns}LinearRing")
                if linear_ring is not None:
                    coords_elem = linear_ring.find(f"{ns}coordinates")
                    if coords_elem is not None and coords_elem.text:
                        coords = parse_coordinates(coords_elem.text)
                        if coords:
                            if coords[0] != coords[-1]:
                                coords.append(coords[0])
                            polygons.append(coords)

        if polygons:
            ward_polygons[ward_num] = polygons

    return ward_polygons


def extract_polygons_from_kml(kml_content: bytes) -> Dict[int, List[List[List[float]]]]:
    """Extract ward polygons from KML content, trying both common namespaces."""
    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse KML: {e}")

    # Try Google Earth namespace first (WardBoundary.kmz)
    result = _extract_polygons_from_root(root, KML_NS_GOOGLE)
    if result:
        return result
    
    # Try OGC namespace (HaldiaMunicipalBoundary2012.kmz)
    return _extract_polygons_from_root(root, KML_NS_OGC)


def extract_municipal_boundary(kml_content: bytes) -> Optional[List[List[float]]]:
    """Extract the municipal boundary polygon from KML."""
    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError:
        return None

    # Try both namespaces
    for ns in [KML_NS_GOOGLE, KML_NS_OGC]:
        for placemark in root.iter(f"{ns}Placemark"):
            for geom in placemark.iter(f"{ns}Polygon"):
                outer = geom.find(f"{ns}outerBoundaryIs")
                if outer is not None:
                    linear_ring = outer.find(f"{ns}LinearRing")
                    if linear_ring is not None:
                        coords_elem = linear_ring.find(f"{ns}coordinates")
                        if coords_elem is not None and coords_elem.text:
                            coords = parse_coordinates(coords_elem.text)
                            if coords and coords[0] != coords[-1]:
                                coords.append(coords[0])
                            return coords
    return None


def kmz_to_geojson(kmz_path: str, output_path: str) -> Dict[str, Any]:
    """
    Convert KMZ ward boundaries to GeoJSON FeatureCollection.
    
    Output structure:
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {"ward_number": 1, "area_km2": 3.028, ...},
          "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
        },
        ...
      ],
      "municipal_boundary": {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
    }
    """
    # Load ward area data for properties (area only)
    ward_areas_path = os.path.join(os.path.dirname(kmz_path), "haldia_ward_areas_gis.json")
    ward_areas = {}
    if os.path.exists(ward_areas_path):
        with open(ward_areas_path, "r") as f:
            data = json.load(f)
            for w in data.get("wards", []):
                ward_areas[w["ward_number"]] = w

    # Load population data
    pop_path = os.path.join(os.path.dirname(kmz_path), "haldia_population_density.json")
    pop_data = {}
    if os.path.exists(pop_path):
        with open(pop_path, "r") as f:
            for item in json.load(f):
                pop_data[item["ward_number"]] = item

    # Load H-area mapping
    mapping_path = os.path.join(os.path.dirname(kmz_path), "haldia_h_area_ward_map.json")
    h_area_mapping = {}
    if os.path.exists(mapping_path):
        with open(mapping_path, "r") as f:
            data = json.load(f)
            for h_id, info in data.get("mapping", {}).items():
                ward = info.get("ward_number")
                if ward:
                    h_area_mapping.setdefault(ward, []).append(h_id)

    # Parse ward boundary KMZ
    with zipfile.ZipFile(kmz_path, "r") as z:
        kml_name = [n for n in z.namelist() if n.endswith(".kml")][0]
        with z.open(kml_name) as f:
            kml_content = f.read()

    ward_polygons = extract_polygons_from_kml(kml_content)

    # Parse municipal boundary
    municipal_boundary = None
    municipal_kmz = os.path.join(os.path.dirname(kmz_path), "HaldiaMunicipalBoundary2012.kmz")
    if os.path.exists(municipal_kmz):
        with zipfile.ZipFile(municipal_kmz, "r") as z:
            kml_name = [n for n in z.namelist() if n.endswith(".kml")][0]
            with z.open(kml_name) as f:
                municipal_boundary = extract_municipal_boundary(f.read())

    # Build GeoJSON
    features = []
    for ward_num, polygons in sorted(ward_polygons.items()):
        if not polygons:
            continue
        
        # Use the first (largest) polygon ring
        coords = polygons[0]
        
        props = {"ward_number": ward_num}
        if ward_num in ward_areas:
            wa = ward_areas[ward_num]
            props.update({
                "area_km2": wa.get("area_km2"),
            })
        if ward_num in pop_data:
            pd = pop_data[ward_num]
            props.update({
                "population_2011": pd.get("population_2011"),
                "population_density_2011": pd.get("population_density_2011"),
                "population_source": pd.get("population_source"),
                "boundary_source": pd.get("boundary_source"),
            })
        if ward_num in h_area_mapping:
            props["h_areas"] = h_area_mapping[ward_num]

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        })

    result = {
        "type": "FeatureCollection",
        "features": features,
    }
    
    if municipal_boundary:
        result["municipal_boundary"] = {
            "type": "Polygon",
            "coordinates": [municipal_boundary]
        }

    # Write output
    with open(output_path, "w") as f:
        json.dump(result, f, separators=(",", ":"))

    return result


if __name__ == "__main__":
    import sys
    kmz_path = "data/WardBoundary.kmz"
    output_path = "data/haldia_ward_polygons.geojson"
    
    if not os.path.exists(kmz_path):
        print(f"KMZ not found: {kmz_path}", file=sys.stderr)
        sys.exit(1)
    
    result = kmz_to_geojson(kmz_path, output_path)
    print(f"Extracted {len(result['features'])} ward polygons to {output_path}")
    if "municipal_boundary" in result:
        print("Municipal boundary included")