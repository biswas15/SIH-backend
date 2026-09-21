"""
gis_ward_mapping.py
--------------------
Reads the Haldia Municipal Boundary KMZ, extracts ward polygon geometries
(ward number from description HTML CDATA), then performs a true
point-in-polygon test for each H01-H30 coordinate.

Produces a mapping table and DOES NOT modify any project files.
Usage:  python gis_ward_mapping.py
"""

import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Prefer the primary KMZ; fall back to WardBoundary.kmz
PREFERRED_KMZ = os.path.join(DATA_DIR, "HaldiaMunicipalBoundary2012.kmz")
FALLBACK_KMZ  = os.path.join(DATA_DIR, "WardBoundary.kmz")

AREAS_FILE = os.path.join(BASE_DIR, "haldia_areas.json")

# ---------------------------------------------------------------------------
# Utility: Ray-casting Point-in-Polygon
# ---------------------------------------------------------------------------
def point_in_polygon(lat, lon, polygon):
    """polygon: list of (lon, lat) tuples."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]      # lon, lat
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

# ---------------------------------------------------------------------------
# Parse ward number from KML description CDATA HTML
# The KMZ stores ward number in an HTML table:
#   <td>Name</td><td>1</td>
# ---------------------------------------------------------------------------
def extract_ward_number_from_description(desc_text):
    """Return integer ward number (1-26) or None."""
    if not desc_text:
        return None
    # Look for:  <td>Name</td>...<td>NUMBER</td>
    # Allow for arbitrary whitespace / case
    m = re.search(
        r'<td[^>]*>\s*Name\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>',
        desc_text, re.IGNORECASE
    )
    if m:
        n = int(m.group(1))
        if 1 <= n <= 26:
            return n
    # Fallback: look for any standalone 1-26 in the description
    nums = re.findall(r'\b(\d{1,2})\b', desc_text)
    candidates = [int(x) for x in nums if 1 <= int(x) <= 26]
    if len(candidates) == 1:
        return candidates[0]
    return None

# ---------------------------------------------------------------------------
# Parse KML coordinates string
# ---------------------------------------------------------------------------
def parse_coords(coord_text):
    """Return list of (lon, lat) tuples."""
    tuples = []
    for part in coord_text.strip().split():
        parts = part.split(",")
        if len(parts) >= 2:
            try:
                tuples.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return tuples

# ---------------------------------------------------------------------------
# Extract all Placemarks from a KML string
# ---------------------------------------------------------------------------
def extract_placemarks(kml_text):
    root = ET.fromstring(kml_text)
    placemarks = []

    def strip(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    def walk(el):
        if strip(el.tag) == "Placemark":
            desc = ""
            polygons = []
            for child in el.iter():
                t = strip(child.tag)
                if t == "description":
                    desc = child.text or ""
                if t == "coordinates":
                    coords = parse_coords(child.text or "")
                    if coords:
                        polygons.append(coords)
            ward_num = extract_ward_number_from_description(desc)
            if polygons:
                placemarks.append({
                    "ward_number": ward_num,
                    "polygons": polygons,
                    "raw_desc_snippet": desc[:200],
                })
        for child in el:
            walk(child)

    walk(root)
    return placemarks

# ---------------------------------------------------------------------------
# Read KMZ
# ---------------------------------------------------------------------------
def read_kmz(path):
    all_pms = []
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".kml"):
                raw = zf.read(name)
                for enc in ("utf-8", "utf-8-sig", "latin-1"):
                    try:
                        kml_text = raw.decode(enc)
                        break
                    except Exception:
                        continue
                pms = extract_placemarks(kml_text)
                print(f"  {os.path.basename(path)}/{name}: {len(pms)} placemarks")
                all_pms.extend(pms)
    return all_pms

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print("=" * 70)
print("HALDIA WARD GIS MAPPING -- POINT-IN-POLYGON ANALYSIS")
print("=" * 70)

# Load H-areas
with open(AREAS_FILE, "r", encoding="utf-8") as f:
    areas = json.load(f)
print(f"\nH-areas loaded: {len(areas)}")

# Load KMZ
kmz_to_use = PREFERRED_KMZ if os.path.exists(PREFERRED_KMZ) else FALLBACK_KMZ
print(f"\nReading KMZ: {os.path.basename(kmz_to_use)}")
all_pms = read_kmz(kmz_to_use)

print(f"Total placemarks: {len(all_pms)}")

# Build ward_polygons dict  { ward_number: [polygon, ...] }
ward_polygons = {}
unidentified = []
for pm in all_pms:
    wn = pm["ward_number"]
    if wn is not None:
        if wn not in ward_polygons:
            ward_polygons[wn] = []
        ward_polygons[wn].extend(pm["polygons"])
    else:
        unidentified.append(pm["raw_desc_snippet"][:80])

print(f"\nWard polygons identified: {sorted(ward_polygons.keys())}")
print(f"Unidentified placemarks:  {len(unidentified)}")
if unidentified:
    for u in unidentified[:3]:
        print(f"  Sample: {u!r}")

# Verify we have all 26
missing = [w for w in range(1, 27) if w not in ward_polygons]
if missing:
    print(f"\nWARNING: Missing ward polygons for: {missing}")
else:
    print(f"All 26 ward polygons present.")

# ---------------------------------------------------------------------------
# Point-in-Polygon test
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("POINT-IN-POLYGON RESULTS")
print("=" * 70)
print(f"{'H-Area':<8} {'Area Name':<30} {'Lat':>9} {'Lon':>10} {'Ward':>6}  Status")
print("-" * 80)

results = []
gis_verified  = 0
outside_count = 0

for area in areas:
    aid   = area["area_id"]
    aname = area["area_name"]
    lat   = area["latitude"]
    lon   = area["longitude"]

    matched_ward = None
    for wn in range(1, 27):
        if wn not in ward_polygons:
            continue
        for poly in ward_polygons[wn]:
            if point_in_polygon(lat, lon, poly):
                matched_ward = wn
                break
        if matched_ward is not None:
            break

    if matched_ward is not None:
        status = "gis_verified"
        gis_verified += 1
    else:
        status = "outside_municipal_boundary"
        outside_count += 1

    results.append({
        "area_id":        aid,
        "area_name":      aname,
        "latitude":       lat,
        "longitude":      lon,
        "matched_ward":   matched_ward,
        "mapping_status": status,
    })

    ward_str = str(matched_ward) if matched_ward is not None else "--"
    print(f"{aid:<8} {aname:<30} {lat:>9.4f} {lon:>10.4f} {ward_str:>6}  {status}")

print("-" * 80)
print(f"\nSummary:")
print(f"  GIS-verified (inside a ward polygon): {gis_verified}")
print(f"  Outside municipal boundary:           {outside_count}")
print(f"  Total:                                {len(results)}")

# Save for review
out_file = os.path.join(DATA_DIR, "ward_mapping_analysis.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nFull results saved to: {out_file}")
print("No project files modified -- awaiting approval.")
