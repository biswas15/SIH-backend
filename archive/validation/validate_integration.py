import json
import urllib.request
import sys

def check(condition, message):
    if not condition:
        print(f"❌ FAIL: {message}")
        sys.exit(1)
    else:
        print(f"✅ PASS: {message}")

try:
    print("Fetching /api/areas ...")
    url_areas = "http://127.0.0.1:8000/api/areas"
    with urllib.request.urlopen(url_areas, timeout=15) as r:
        areas_data = json.loads(r.read())
        
    print(f"Fetching /api/weather?area_id=H23 ...")
    url_weather = "http://127.0.0.1:8000/api/weather?area_id=H23"
    with urllib.request.urlopen(url_weather, timeout=15) as r:
        weather_data = json.loads(r.read())

    # Validation
    check(len(areas_data) == 30, "All 30 H-areas are present")
    
    # Load original areas to verify lat/lon unchanged
    with open("haldia_areas.json", "r", encoding="utf-8") as f:
        original_areas = json.load(f)
    
    # Check no latitude/longitude values changed
    all_coords_match = True
    for orig in original_areas:
        mapped = next((a for a in areas_data if a["area_id"] == orig["area_id"]), None)
        if mapped:
            if mapped["latitude"] != orig["latitude"] or mapped["longitude"] != orig["longitude"]:
                all_coords_match = False
    check(all_coords_match, "No latitude/longitude values changed")
    
    # Check mapped ward numbers are only 1-26
    mapped_wards = set()
    for a in areas_data:
        wn = a.get("ward", {}).get("ward_number")
        if wn is not None:
            mapped_wards.add(wn)
            if not (1 <= wn <= 26):
                print(f"Invalid ward number found: {wn}")
                sys.exit(1)
    check(True, "Mapped ward numbers are only 1-26")
    
    # Check Ward 1 population and density
    ward1_entry = next((a for a in areas_data if a.get("ward", {}).get("ward_number") == 1), None)
    if ward1_entry and ward1_entry.get("demographics"):
        check(ward1_entry["demographics"]["population_2011"] == 6308, "Ward 1 population = 6308")
        check(abs(ward1_entry["demographics"]["population_density_2011"] - 2083.05) < 0.1, "Ward 1 density = 2083.05")
    else:
        check(False, "Could not find Ward 1 entry to verify demographics")

    # Check Ward 26 population and density (from H23)
    ward26_entry = weather_data
    if ward26_entry.get("ward", {}).get("ward_number") == 26 and ward26_entry.get("demographics"):
        check(ward26_entry["demographics"]["population_2011"] == 7861, "Ward 26 population = 7861")
        check(abs(ward26_entry["demographics"]["population_density_2011"] - 2568.87) < 0.1, "Ward 26 density = 2568.87")
    else:
        check(False, "Could not verify Ward 26 demographics from /api/weather?area_id=H23")

    # Verify total Census population across 26 wards = 200827
    with open("data/haldia_population_density.json", "r", encoding="utf-8") as f:
        pop_db = json.load(f)
    total_pop = sum(item["population_2011"] for item in pop_db)
    check(total_pop == 200827, f"Total Census population across 26 wards = 200827 (Found: {total_pop})")

except Exception as e:
    print(f"Validation script failed: {e}")
    sys.exit(1)
