"""
generate_population_density.py
-------------------------------
Generates data/haldia_population_density.json from:
  - Census of India 2011 ward-level population records for Haldia (M)
  - GIS polygon areas from Haldia Municipality 2012 KMZ boundary file

Run this script to regenerate the JSON if source data changes.
Population density = population_2011 / area_km2
"""

import json
import os

# ---------------------------------------------------------------------------
# SOURCE: Census of India 2011 — Haldia (M) ward record
# Values are EXACT census counts. Do NOT modify.
# ---------------------------------------------------------------------------
POPULATION_2011 = {
    1:  6308,
    2:  9919,
    3:  8095,
    4:  10834,
    5:  9253,
    6:  6708,
    7:  9095,
    8:  5659,
    9:  12315,
    10: 8258,
    11: 7310,
    12: 6985,
    13: 6143,
    14: 8082,
    15: 7916,
    16: 6647,
    17: 4666,
    18: 7795,
    19: 7012,
    20: 6649,
    21: 6024,
    22: 7038,
    23: 6566,
    24: 9396,
    25: 8293,
    26: 7861,
}

# ---------------------------------------------------------------------------
# SOURCE: Haldia Municipality — Haldia Municipal Boundary 2012 KMZ
# Areas are GIS polygon calculations in km².
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GIS_AREAS_FILE = os.path.join(BASE_DIR, "data", "haldia_ward_areas_gis.json")

with open(GIS_AREAS_FILE, "r", encoding="utf-8") as f:
    gis_data = json.load(f)

AREA_KM2 = {ward["ward_number"]: ward["area_km2"] for ward in gis_data["wards"]}

# ---------------------------------------------------------------------------
# Build population density records
# ---------------------------------------------------------------------------
records = []
for ward_num in range(1, 27):
    pop = POPULATION_2011[ward_num]
    area = AREA_KM2[ward_num]
    density = pop / area  # exact calculation
    density_rounded = round(density, 2)

    records.append({
        "ward_number": ward_num,
        "population_2011": pop,
        "area_km2": area,
        "population_density_2011": density_rounded,
        "data_year": 2011,
        "population_source": "Census of India 2011 — Haldia (M) ward record",
        "boundary_source": "Haldia Municipality — Haldia Municipal Boundary 2012 KMZ",
    })

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUT_FILE = os.path.join(BASE_DIR, "data", "haldia_population_density.json")
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"Generated {OUT_FILE}")
print(f"Total wards: {len(records)}")
for r in records:
    print(
        f"  Ward {r['ward_number']:2d}: pop={r['population_2011']:6d}, "
        f"area={r['area_km2']:.2f} km2, "
        f"density={r['population_density_2011']:.2f} /km2"
    )
