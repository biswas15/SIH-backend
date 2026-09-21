"""
validate_population_density.py
--------------------------------
Validation script for data/haldia_population_density.json

Checks:
  1. Exactly 26 wards exist
  2. Ward numbers 1 through 26 all present
  3. No duplicate ward numbers
  4. All population values are positive
  5. All area values are positive
  6. Calculated density matches population / area (within float tolerance)
  7. No missing/null values in required fields

Run with: python validate_population_density.py
Exit code 0 = all checks passed, non-zero = failure.
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "haldia_population_density.json")
OUT_FILE = os.path.join(BASE_DIR, "validate_population_density_result.txt")

REQUIRED_FIELDS = [
    "ward_number",
    "population_2011",
    "area_km2",
    "population_density_2011",
    "data_year",
    "population_source",
    "boundary_source",
]

DENSITY_TOLERANCE = 0.01  # Allow rounding difference of up to 0.01 /km2

results = []
passed = 0
failed = 0


def log(msg: str, level: str = "INFO"):
    tag = f"[{level}]"
    line = f"{tag} {msg}"
    print(line)
    results.append(line)


def check(condition: bool, pass_msg: str, fail_msg: str) -> bool:
    global passed, failed
    if condition:
        log(pass_msg, "PASS")
        passed += 1
        return True
    else:
        log(fail_msg, "FAIL")
        failed += 1
        return False


# ---------------------------------------------------------------------------
# Load file
# ---------------------------------------------------------------------------
log(f"Loading: {DATA_FILE}")
if not os.path.exists(DATA_FILE):
    log(f"File not found: {DATA_FILE}", "ERROR")
    sys.exit(1)

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# ---------------------------------------------------------------------------
# CHECK 1: Exactly 26 wards
# ---------------------------------------------------------------------------
check(
    len(data) == 26,
    f"Exactly 26 ward records found.",
    f"Expected 26 wards, found {len(data)}.",
)

# ---------------------------------------------------------------------------
# CHECK 2: Ward numbers 1–26 all present
# ---------------------------------------------------------------------------
ward_numbers = [r["ward_number"] for r in data]
expected_set = set(range(1, 27))
found_set = set(ward_numbers)

check(
    found_set == expected_set,
    "Ward numbers 1 through 26 all present.",
    f"Missing ward numbers: {expected_set - found_set}. "
    f"Extra: {found_set - expected_set}.",
)

# ---------------------------------------------------------------------------
# CHECK 3: No duplicate ward numbers
# ---------------------------------------------------------------------------
check(
    len(ward_numbers) == len(set(ward_numbers)),
    "No duplicate ward numbers.",
    f"Duplicates found: {[n for n in ward_numbers if ward_numbers.count(n) > 1]}",
)

# ---------------------------------------------------------------------------
# CHECK 4: All population values positive
# ---------------------------------------------------------------------------
bad_pop = [r["ward_number"] for r in data if r.get("population_2011", 0) <= 0]
check(
    len(bad_pop) == 0,
    "All population_2011 values are positive.",
    f"Non-positive population in wards: {bad_pop}",
)

# ---------------------------------------------------------------------------
# CHECK 5: All area values positive
# ---------------------------------------------------------------------------
bad_area = [r["ward_number"] for r in data if r.get("area_km2", 0) <= 0]
check(
    len(bad_area) == 0,
    "All area_km2 values are positive.",
    f"Non-positive area in wards: {bad_area}",
)

# ---------------------------------------------------------------------------
# CHECK 6: Calculated density matches population / area
# ---------------------------------------------------------------------------
density_errors = []
for r in data:
    wn = r["ward_number"]
    pop = r.get("population_2011")
    area = r.get("area_km2")
    stored = r.get("population_density_2011")
    if pop is None or area is None or stored is None:
        density_errors.append(f"Ward {wn}: missing fields for density check")
        continue
    expected = round(pop / area, 2)
    if abs(stored - expected) > DENSITY_TOLERANCE:
        density_errors.append(
            f"Ward {wn}: stored={stored}, expected={expected} "
            f"(pop={pop}/area={area})"
        )

check(
    len(density_errors) == 0,
    "Density = population / area verified for all 26 wards (within tolerance).",
    "Density mismatch in:\n" + "\n".join(f"  {e}" for e in density_errors),
)

# ---------------------------------------------------------------------------
# CHECK 7: No missing/null values in required fields
# ---------------------------------------------------------------------------
missing_fields = []
for r in data:
    wn = r.get("ward_number", "?")
    for field in REQUIRED_FIELDS:
        val = r.get(field)
        if val is None or val == "":
            missing_fields.append(f"Ward {wn}: missing field '{field}'")

check(
    len(missing_fields) == 0,
    "No missing or null values in required fields.",
    "Missing values:\n" + "\n".join(f"  {m}" for m in missing_fields),
)

# ---------------------------------------------------------------------------
# Sample records
# ---------------------------------------------------------------------------
log("---")
for wn in [1, 26]:
    record = next((r for r in data if r["ward_number"] == wn), None)
    if record:
        log(f"Sample Ward {wn}: {json.dumps(record, ensure_ascii=False)}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log("---")
log(f"Validation complete: {passed} passed, {failed} failed.")

# Write results to file
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(results) + "\n")

log(f"Results written to: {OUT_FILE}")

if failed > 0:
    sys.exit(1)
else:
    log("ALL CHECKS PASSED.")
    sys.exit(0)
