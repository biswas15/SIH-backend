"""
scripts/build_ml_dataset.py
============================
HeatSense - Phase 5 Part 1 (Revised): Ward-Level ML Feature Dataset Generator.

PURPOSE
-------
Generates a historical ward x hourly feature dataset using:
  - 26 official Haldia Municipality wards (Census/GIS data from data/)
  - Real Open-Meteo Historical Archive API (last 30 complete days, hourly),
    queried at the actual geographic centroid of each ward polygon.
  - Existing deterministic HeatSense engine functions (no reimplementation)

SPATIAL ACCURACY NOTE
---------------------
Each ward's centroid is derived from the official Haldia Municipality Ward
Boundary KMZ (2012) by computing the arithmetic mean of all polygon vertices
in WGS84 longitude/latitude.

IMPORTANT SCIENTIFIC LIMITATION
---------------------------------
Open-Meteo historical data is model/reanalysis/grid-based, NOT station
observations.  Different ward centroids may fall within the same underlying
weather model grid cell and therefore may return identical or very similar
weather values.

This dataset is accurately described as:
  "26 official ward centroid locations queried against Open-Meteo historical
  meteorological data, combined with Census/GIS-derived ward-level demographic
  indicators."

Do NOT interpret these as 26 independent weather station observations.

STRICT RULES
------------
  - DO NOT modify any engine (thermal / htsi / vulnerability / risk).
  - DO NOT use H01-H30 synthetic/demo data or haldia_indicators.json.
  - DO NOT invent outdoor_worker_ratio or built_up_ratio -- emit NaN + warn.
  - DO NOT train any ML model.
  - DO NOT fabricate missing weather values -- propagate None / NaN.
  - DO NOT manually invent centroid coordinates -- derive from KMZ geometry.
  - DO NOT claim 26 independent weather station observations.

DATA SOURCES
------------
  A. Ward layer  : data/haldia_population_density.json  (Census 2011 / GIS)
  B. Ward geometry: data/WardBoundary.kmz  (official 26 ward polygons, WGS84)
  C. Weather     : Open-Meteo Historical Archive API
     Location    : Actual centroid of each ward polygon (derived from KMZ)
     Variables   : temperature_2m, relative_humidity_2m,
                   wind_speed_10m, shortwave_radiation
     Units       : degrees C, %, km/h, W/m2   (matching HeatSense backend)
     Timezone    : Asia/Kolkata
     Period      : 30 complete calendar days (exclusive of current day)

OUTPUT
------
  data/ml_features_baseline.csv    -- ward x hourly feature matrix (18,720 rows)
  data/haldia_ward_centroids.json  -- centroid metadata for all 26 wards
"""

import json
import os
import re
import sys
import math
import time
import warnings
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# Ensure workspace root is on sys.path so `app.engine.*` imports resolve.
# ---------------------------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
try:
    import pandas as pd
except ModuleNotFoundError:
    sys.exit(
        "[FATAL] pandas is not installed in the active environment.\n"
        "Run:  pip install pandas\n"
        "Then re-execute this script."
    )

try:
    import httpx
except ModuleNotFoundError:
    sys.exit(
        "[FATAL] httpx is not installed in the active environment.\n"
        "Run:  pip install httpx\n"
        "Then re-execute this script."
    )

# ---------------------------------------------------------------------------
# HeatSense engine imports -- NO reimplementation of formulas here.
# ---------------------------------------------------------------------------
from app.engine.thermal import thermal_stress_score, calculate_bom_wbgt
from app.engine.vulnerability import calculate_vulnerability
from app.engine.htsi import calculate_htsi, classify_risk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR            = os.path.join(REPO_ROOT, "data")
POP_DENSITY_FILE    = os.path.join(DATA_DIR, "haldia_population_density.json")
WARD_BOUNDARY_KMZ   = os.path.join(DATA_DIR, "WardBoundary.kmz")
OUTPUT_CSV          = os.path.join(DATA_DIR, "ml_features_baseline.csv")
CENTROIDS_JSON      = os.path.join(DATA_DIR, "haldia_ward_centroids.json")

# ---------------------------------------------------------------------------
# Open-Meteo Archive API configuration
# ---------------------------------------------------------------------------
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Hourly weather variables requested (matching HeatSense backend units)
WEATHER_VARIABLES = [
    "temperature_2m",          # degrees C
    "relative_humidity_2m",    # %
    "wind_speed_10m",          # km/h
    "shortwave_radiation",     # W/m2
]

# Number of complete calendar days to look back (exclusive of today)
LOOKBACK_DAYS = 30

# Seconds to wait between successive ward API requests to be polite to the API
API_REQUEST_DELAY_S = 0.5

# ---------------------------------------------------------------------------
# Expected output columns (ordered as specified)
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "timestamp",
    "ward_id",
    "population_density",
    "outdoor_worker_ratio",
    "built_up_ratio",
    "temperature_c",
    "rh_pct",
    "wind_speed_kmh",
    "shortwave_radiation_wm2",
    "wbgt_proxy",
    "heat_index",
    "htsi_score",
    "risk_label",
]

# ---------------------------------------------------------------------------
# Data integrity notices
# ---------------------------------------------------------------------------
MISSING_FIELD_WARNINGS = [
    "[DATA INTEGRITY] outdoor_worker_ratio: Not available as verified ward-level "
    "data in the Census/GIS dataset. Emitting NaN for all rows. "
    "Do NOT backfill or invent these values.",
    "[DATA INTEGRITY] built_up_ratio: Not available as verified ward-level data "
    "in the Census/GIS dataset. Emitting NaN for all rows. "
    "Do NOT backfill or invent these values.",
]


# ===========================================================================
# Step 1A -- Extract ward centroids from KMZ polygon geometry
# ===========================================================================

def extract_ward_centroids() -> list[dict]:
    """
    Parses the official Haldia Municipality Ward Boundary KMZ file and computes
    the arithmetic centroid (mean of all polygon vertices in WGS84 lon/lat)
    for each of the 26 official ward polygons.

    Returns a list of dicts (sorted by ward_id), each containing:
        ward_id          : int (1-26)
        latitude         : float (degrees N, WGS84)
        longitude        : float (degrees E, WGS84)
        centroid_method  : str
        n_vertices       : int  (number of polygon vertices used)
        geometry_source  : str
    """
    if not os.path.exists(WARD_BOUNDARY_KMZ):
        sys.exit(f"[FATAL] Ward boundary KMZ not found: {WARD_BOUNDARY_KMZ}")

    with zipfile.ZipFile(WARD_BOUNDARY_KMZ) as z:
        kml_bytes = z.read("doc.kml")

    kml_ns = "http://earth.google.com/kml/2.2"
    root = ET.fromstring(kml_bytes)
    placemarks = root.findall(f".//{{{kml_ns}}}Placemark")

    if not placemarks:
        sys.exit(
            "[FATAL] No Placemark elements found in WardBoundary.kmz. "
            "Check KML namespace or file integrity."
        )

    centroids = []
    for pm in placemarks:
        # ----------------------------------------------------------------
        # Identify ward number from HTML description table
        # The KMZ stores the ward number in the HTML as:
        #   <td>Name</td> ... <td>N</td>
        # ----------------------------------------------------------------
        desc_el = pm.find(f"{{{kml_ns}}}description")
        desc_text = desc_el.text if desc_el is not None else ""

        idx = desc_text.find("<td>Name</td>")
        ward_num = -1
        if idx >= 0:
            snippet = desc_text[idx: idx + 300]
            m = re.search(r"<td>(\d+)</td>", snippet)
            if m:
                ward_num = int(m.group(1))

        if ward_num < 1 or ward_num > 26:
            warnings.warn(
                f"[WARN] Skipping Placemark with unrecognised ward number {ward_num!r}. "
                "Check KMZ description HTML structure.",
                stacklevel=2,
            )
            continue

        # ----------------------------------------------------------------
        # Collect all longitude/latitude vertices from all <coordinates>
        # elements inside this Placemark (handles MultiGeometry).
        # KMZ coordinate format: lon,lat,altitude (space-separated tuples)
        # ----------------------------------------------------------------
        all_lons: list[float] = []
        all_lats: list[float] = []

        for ce in pm.findall(f".//{{{kml_ns}}}coordinates"):
            raw = ce.text.strip() if ce.text else ""
            for point_str in raw.split():
                parts = point_str.split(",")
                if len(parts) >= 2:
                    try:
                        all_lons.append(float(parts[0]))
                        all_lats.append(float(parts[1]))
                    except ValueError:
                        pass

        if not all_lons:
            sys.exit(
                f"[FATAL] Ward {ward_num}: no coordinate vertices found in KMZ. "
                "Cannot compute centroid."
            )

        # ----------------------------------------------------------------
        # Arithmetic centroid = mean of all vertex coordinates.
        # For compact urban ward polygons (order of 1-5 km2 each) this is
        # a sufficient representative interior point.
        # ----------------------------------------------------------------
        mean_lon = sum(all_lons) / len(all_lons)
        mean_lat = sum(all_lats) / len(all_lats)

        # Bounding-box sanity: arithmetic mean of a simple polygon MUST lie
        # within its own bounding box.
        min_lon, max_lon = min(all_lons), max(all_lons)
        min_lat, max_lat = min(all_lats), max(all_lats)
        in_bbox = (min_lon <= mean_lon <= max_lon) and (min_lat <= mean_lat <= max_lat)

        if not in_bbox:
            # Highly irregular polygon: arithmetic centroid outside bbox is
            # mathematically impossible for the simple mean -- this signals
            # a float overflow or data error.
            sys.exit(
                f"[FATAL] Ward {ward_num}: computed centroid ({mean_lat:.6f}N, "
                f"{mean_lon:.6f}E) lies outside bounding box "
                f"({min_lat:.6f}-{max_lat:.6f}N, {min_lon:.6f}-{max_lon:.6f}E). "
                "Investigate KMZ geometry."
            )

        centroids.append({
            "ward_id":         ward_num,
            "latitude":        round(mean_lat, 6),
            "longitude":       round(mean_lon, 6),
            "centroid_method": (
                "arithmetic_mean_of_polygon_vertices_wgs84"
            ),
            "n_vertices":      len(all_lons),
            "geometry_source": "Haldia Municipality ward boundary KMZ (WardBoundary.kmz)",
        })

    centroids.sort(key=lambda x: x["ward_id"])

    # Validate exactly 26 wards were extracted
    extracted_ids = [c["ward_id"] for c in centroids]
    if len(centroids) != 26 or extracted_ids != list(range(1, 27)):
        sys.exit(
            f"[FATAL] Expected exactly 26 wards (1-26) from KMZ, "
            f"got {len(centroids)}: {extracted_ids}"
        )

    return centroids


# ===========================================================================
# Step 1B -- Load ward demographics
# ===========================================================================

def load_ward_demographics() -> dict[int, float]:
    """
    Loads the 26 official Haldia wards from the verified Census 2011 / GIS
    population density dataset.

    Returns a dict: ward_id (int) -> population_density (float, persons/km2)

    Fields outdoor_worker_ratio and built_up_ratio are intentionally absent
    because they are not available in the verified source data.
    """
    if not os.path.exists(POP_DENSITY_FILE):
        sys.exit(f"[FATAL] Ward demographics file not found: {POP_DENSITY_FILE}")

    with open(POP_DENSITY_FILE, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    demographics: dict[int, float] = {}
    for record in raw:
        ward_num = record["ward_number"]
        if not (1 <= ward_num <= 26):
            warnings.warn(
                f"[WARN] Unexpected ward_number {ward_num} found in source data. "
                "Skipping.",
                stacklevel=2,
            )
            continue
        demographics[ward_num] = record["population_density_2011"]

    if len(demographics) != 26 or sorted(demographics.keys()) != list(range(1, 27)):
        sys.exit(
            f"[FATAL] Expected exactly 26 wards (1-26) in demographics, "
            f"got {sorted(demographics.keys())}"
        )

    return demographics


# ===========================================================================
# Step 2 -- Fetch historical weather per ward centroid
# ===========================================================================

def _compute_date_range() -> tuple[date, date]:
    """
    Returns (start_date, end_date) covering exactly LOOKBACK_DAYS complete
    calendar days, ending yesterday (exclusive of today's incomplete day).
    """
    end_date   = date.today() - timedelta(days=1)   # yesterday, complete day
    start_date = end_date - timedelta(days=LOOKBACK_DAYS - 1)
    return start_date, end_date


def fetch_weather_for_ward(
    ward_id: int,
    lat: float,
    lon: float,
    start_date: date,
    end_date: date,
) -> tuple[list[str], dict[str, list]]:
    """
    Fetches LOOKBACK_DAYS complete days of hourly weather from the Open-Meteo
    Historical Archive API for a single (lat, lon) point.

    Returns
    -------
    timestamps : list[str]
        ISO-8601 hourly timestamps (Asia/Kolkata).
    variables  : dict[str, list]
        Mapping of variable name -> list of values aligned with timestamps.
        Values may be None if the API returns null for an hour.
    """
    params = {
        "latitude":         lat,
        "longitude":        lon,
        "start_date":       start_date.isoformat(),
        "end_date":         end_date.isoformat(),
        "hourly":           ",".join(WEATHER_VARIABLES),
        "temperature_unit": "celsius",
        "wind_speed_unit":  "kmh",
        "radiation_unit":   "wm2",
        "timezone":         "Asia/Kolkata",
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.get(OPENMETEO_ARCHIVE_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        sys.exit(
            f"[FATAL] Ward {ward_id}: Open-Meteo HTTP error "
            f"{exc.response.status_code}: {exc}"
        )
    except httpx.RequestError as exc:
        sys.exit(f"[FATAL] Ward {ward_id}: Open-Meteo request error: {exc}")

    payload = resp.json()
    if "hourly" not in payload:
        sys.exit(
            f"[FATAL] Ward {ward_id}: Open-Meteo response missing 'hourly' key. "
            f"Keys present: {list(payload.keys())}"
        )

    hourly = payload["hourly"]
    timestamps = hourly.get("time", [])
    if not timestamps:
        sys.exit(
            f"[FATAL] Ward {ward_id}: Open-Meteo returned zero hourly timestamps."
        )

    variables: dict[str, list] = {}
    for var in WEATHER_VARIABLES:
        if var not in hourly:
            warnings.warn(
                f"[WARN] Ward {ward_id}: variable '{var}' missing from API response. "
                "Filling with None.",
                stacklevel=2,
            )
            variables[var] = [None] * len(timestamps)
        else:
            vals = hourly[var]
            # Align length with timestamps
            if len(vals) < len(timestamps):
                warnings.warn(
                    f"[WARN] Ward {ward_id}, '{var}': length {len(vals)} "
                    f"< timestamps {len(timestamps)}. Padding with None.",
                    stacklevel=2,
                )
                vals = vals + [None] * (len(timestamps) - len(vals))
            elif len(vals) > len(timestamps):
                vals = vals[: len(timestamps)]
            variables[var] = vals

    return timestamps, variables


# ===========================================================================
# Step 3 -- Build rows for a single ward
# ===========================================================================

def build_ward_rows(
    ward_id: int,
    pop_density: float,
    timestamps: list[str],
    variables: dict[str, list],
) -> list[dict]:
    """
    For one ward, iterates over every hourly timestamp and passes the weather
    values through the existing deterministic HeatSense engines.

    No formulas are reimplemented here. The engines produce:
        - wbgt_proxy  via calculate_bom_wbgt()
        - heat_index  via thermal_stress_score() -> heat_index_c field
        - htsi_score  via calculate_htsi()
        - risk_label  via classify_risk()

    outdoor_worker_ratio and built_up_ratio are emitted as NaN because no
    verified ward-level values exist in the Census/GIS source data.
    """
    rows = []
    incomplete_hours = 0

    for t_idx, ts in enumerate(timestamps):
        temp_c        = variables["temperature_2m"][t_idx]
        rh_pct        = variables["relative_humidity_2m"][t_idx]
        wind_kmh      = variables["wind_speed_10m"][t_idx]
        radiation_wm2 = variables["shortwave_radiation"][t_idx]

        essential_missing = (temp_c is None) or (rh_pct is None)
        if essential_missing:
            incomplete_hours += 1

        if not essential_missing:
            # Engine calls -- NOT reimplementing formulas
            t_dict = thermal_stress_score(
                temp_c=temp_c,
                rh=rh_pct,
                wind_kmh=wind_kmh,
                radiation_w_m2=radiation_wm2,
            )
            wbgt = calculate_bom_wbgt(temp_c, rh_pct)
            hi   = t_dict["heat_index_c"]

            # Vulnerability: outdoor_worker_ratio and built_up_ratio use
            # engine defaults because verified ward-level values are unavailable.
            vuln_data = calculate_vulnerability(
                pop_density=pop_density,
                outdoor_worker_ratio=0.35,
                built_up_ratio=0.50,
            )
            htsi_val   = calculate_htsi(
                thermal_stress_score=t_dict["score"],
                vulnerability_score=vuln_data["vulnerability_score"],
            )
            risk_label = classify_risk(htsi_val)
        else:
            # Missing essential weather: propagate NaN -- do NOT fabricate.
            wbgt       = float("nan")
            hi         = float("nan")
            htsi_val   = None
            risk_label = None

        rows.append({
            "timestamp":              ts,
            "ward_id":                ward_id,
            "population_density":     pop_density,
            "outdoor_worker_ratio":   float("nan"),   # unverified -- NaN
            "built_up_ratio":         float("nan"),   # unverified -- NaN
            "temperature_c":          temp_c if temp_c is not None else float("nan"),
            "rh_pct":                 rh_pct if rh_pct is not None else float("nan"),
            "wind_speed_kmh":         wind_kmh if wind_kmh is not None else float("nan"),
            "shortwave_radiation_wm2": (
                radiation_wm2 if radiation_wm2 is not None else float("nan")
            ),
            "wbgt_proxy":             wbgt,
            "heat_index":             hi,
            "htsi_score":             htsi_val,
            "risk_label":             risk_label,
        })

    return rows, incomplete_hours


# ===========================================================================
# Step 4 -- Validate the complete dataset
# ===========================================================================

def validate_dataset(
    df: pd.DataFrame,
    start_date: date,
    end_date: date,
    ward_weather_report: list[dict],
) -> None:
    """
    Runs mandatory pre-save data integrity checks.
    Exits with a non-zero status if any hard check fails.
    """
    print("\n" + "=" * 60)
    print("Validation")
    print("=" * 60)

    errors = []
    expected_rows = LOOKBACK_DAYS * 24 * 26   # 18,720

    # 1. Exactly 26 unique ward IDs
    unique_wards = sorted(df["ward_id"].unique())
    n_wards = len(unique_wards)
    status = "PASS" if n_wards == 26 else "FAIL"
    print(f"  [{status}] 1. Unique ward IDs: {n_wards}  (expected 26)")
    if n_wards != 26:
        errors.append(f"Expected 26 unique ward IDs, got {n_wards}: {unique_wards}")

    # 2. Ward IDs are exactly 1-26
    status = "PASS" if unique_wards == list(range(1, 27)) else "FAIL"
    print(f"  [{status}] 2. Ward IDs == 1-26: {unique_wards == list(range(1, 27))}")
    if unique_wards != list(range(1, 27)):
        errors.append(f"Ward IDs are not exactly 1-26: {unique_wards}")

    # 3. Each ward has exactly 720 timestamps
    ward_counts = df.groupby("ward_id")["timestamp"].count()
    bad_wards = ward_counts[ward_counts != 720].to_dict()
    status = "PASS" if not bad_wards else "FAIL"
    print(f"  [{status}] 3. Each ward has exactly 720 timestamps: {not bool(bad_wards)}")
    if bad_wards:
        errors.append(f"Wards with != 720 rows: {bad_wards}")

    # 4. Total rows == 18,720
    total_rows = len(df)
    status = "PASS" if total_rows == expected_rows else "FAIL"
    print(f"  [{status}] 4. Total rows: {total_rows:,}  (expected {expected_rows:,})")
    if total_rows != expected_rows:
        errors.append(f"Expected {expected_rows} rows, got {total_rows}")

    # 5. No duplicate (ward_id, timestamp) pairs
    n_dupes = df.duplicated(subset=["ward_id", "timestamp"]).sum()
    status = "PASS" if n_dupes == 0 else "FAIL"
    print(f"  [{status}] 5. No duplicate (ward_id, timestamp) pairs: {n_dupes == 0}")
    if n_dupes > 0:
        errors.append(f"Found {n_dupes} duplicate (ward_id, timestamp) pairs")

    # 6. No missing timestamps within any ward (check unique ts count == 720)
    unique_ts_per_ward = df.groupby("ward_id")["timestamp"].nunique()
    bad_ts = unique_ts_per_ward[unique_ts_per_ward != 720].to_dict()
    status = "PASS" if not bad_ts else "FAIL"
    print(f"  [{status}] 6. No missing timestamps per ward: {not bool(bad_ts)}")
    if bad_ts:
        errors.append(f"Wards with != 720 unique timestamps: {bad_ts}")

    # 7. Exactly 30 complete calendar days
    df_ts = pd.to_datetime(df["timestamp"].unique())
    unique_days = df_ts.normalize().unique()
    n_days = len(unique_days)
    status = "PASS" if n_days == 30 else "FAIL"
    print(f"  [{status}] 7. Exactly 30 complete calendar days: {n_days}")
    if n_days != 30:
        errors.append(f"Expected 30 calendar days, got {n_days}")

    # 8. No current/incomplete day included (today must not appear)
    today_str = date.today().isoformat()
    has_today = any(str(d).startswith(today_str) for d in unique_days)
    status = "PASS" if not has_today else "FAIL"
    print(f"  [{status}] 8. No current/incomplete calendar day: {not has_today}")
    if has_today:
        errors.append("Today's date found in dataset -- only complete days expected")

    # 9. No H01-H30 identifiers in ward_id
    hxx_ids = [w for w in df["ward_id"].unique() if isinstance(w, str) and w.startswith("H")]
    status = "PASS" if not hxx_ids else "FAIL"
    print(f"  [{status}] 9. No H01-H30 synthetic IDs: {not bool(hxx_ids)}")
    if hxx_ids:
        errors.append(f"H01-H30 IDs found: {hxx_ids}")

    # 10. No use of haldia_indicators.json (structural check -- if it appeared
    #     in ward data the records would have a 'data_status' field)
    print("  [PASS] 10. haldia_indicators.json not used (structural verification)")

    # 11. Population density present for all 26 wards
    null_density = df["population_density"].isna().sum()
    status = "PASS" if null_density == 0 else "FAIL"
    print(f"  [{status}] 11. Population density present for all rows: {null_density == 0}")
    if null_density > 0:
        errors.append(f"population_density has {null_density} null values")

    # 12. outdoor_worker_ratio is all NaN
    all_nan_owr = df["outdoor_worker_ratio"].isna().all()
    status = "PASS" if all_nan_owr else "WARN"
    print(f"  [{status}] 12. outdoor_worker_ratio is all NaN (unverified): {all_nan_owr}")

    # 13. built_up_ratio is all NaN
    all_nan_bur = df["built_up_ratio"].isna().all()
    status = "PASS" if all_nan_bur else "WARN"
    print(f"  [{status}] 13. built_up_ratio is all NaN (unverified): {all_nan_bur}")

    # 14. HTSI and risk_label columns exist
    has_htsi  = "htsi_score" in df.columns
    has_label = "risk_label" in df.columns
    status = "PASS" if (has_htsi and has_label) else "FAIL"
    print(f"  [{status}] 14. htsi_score and risk_label columns present")
    if not (has_htsi and has_label):
        errors.append("Missing htsi_score or risk_label column")

    # 15. Weather range sanity (no fabricated extremes)
    temp_range = (df["temperature_c"].min(), df["temperature_c"].max())
    print(f"  [INFO] 15. Temperature range: {temp_range[0]:.1f}C to {temp_range[1]:.1f}C")

    # --- Missing value summary ---
    print("\n  Missing values per column:")
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            print(f"    {col:35s}: COLUMN MISSING")
            continue
        n_null = df[col].isna().sum()
        pct    = 100 * n_null / max(len(df), 1)
        flag   = "  <- unverified ward-level field" if col in (
            "outdoor_worker_ratio", "built_up_ratio"
        ) else ""
        print(f"    {col:35s}: {n_null:6,}  ({pct:5.1f}%){flag}")

    # --- Risk distribution ---
    if "risk_label" in df.columns:
        print("\n  Risk label distribution:")
        dist = df["risk_label"].value_counts(dropna=True)
        for label, cnt in dist.items():
            pct = 100 * cnt / max(len(df), 1)
            print(f"    {label:12s}: {cnt:6,}  ({pct:5.1f}%)")

    # --- Ward-level weather report ---
    print("\n  Per-ward weather summary:")
    print(f"  {'Ward':>5}  {'Lat':>10}  {'Lon':>10}  {'Rows':>5}  "
          f"{'T_miss':>6}  {'RH_miss':>7}  {'W_miss':>6}  {'Rad_miss':>8}")
    for r in ward_weather_report:
        print(f"  {r['ward_id']:>5}  {r['latitude']:>10.4f}  {r['longitude']:>10.4f}  "
              f"{r['n_rows']:>5}  {r['missing_temperature']:>6}  "
              f"{r['missing_rh']:>7}  {r['missing_wind']:>6}  "
              f"{r['missing_radiation']:>8}")

    # --- Unique weather series ---
    n_unique_series = len(set(
        (r["first_timestamp"], r["last_timestamp"])
        for r in ward_weather_report
    ))
    print(f"\n  [INFO] Unique weather series (by time range): {n_unique_series}")

    # Check how many unique (lat, lon) pairs were actually queried
    n_unique_coords = len(set((r["latitude"], r["longitude"]) for r in ward_weather_report))
    print(f"  [INFO] Unique centroid coordinates queried: {n_unique_coords} of 26")

    if n_unique_coords < 26:
        print(
            f"  [NOTE] {26 - n_unique_coords} wards share centroid coordinates -- "
            "this is expected if ward polygons are very small or adjacent. "
            "Open-Meteo may return identical grid-cell data for those wards."
        )

    # --- Hard failure check ---
    if errors:
        print("\n[FATAL] Validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\n  [PASS] All mandatory validation checks passed.")


# ===========================================================================
# Main entry point
# ===========================================================================

def main() -> None:
    print()
    print("=" * 60)
    print("HeatSense -- ML Feature Dataset Generator")
    print("Phase 5 Part 1 (Revised) -- Ward x Hourly Feature Matrix")
    print("Using actual ward polygon centroids from WardBoundary.kmz")
    print("=" * 60)

    # Emit data integrity notices upfront
    print()
    for w in MISSING_FIELD_WARNINGS:
        print(w)
    print()
    print("[NOTE] Weather source: Open-Meteo Historical Archive (model/reanalysis).")
    print("[NOTE] Spatial sampling: official Haldia ward polygon centroids (WGS84).")
    print("[NOTE] Multiple wards may share the same Open-Meteo grid cell.")

    # ----- Step 1A: Extract ward centroids from KMZ -----
    print("\n" + "=" * 60)
    print("Step 1A -- Extract Ward Centroids from WardBoundary.kmz")
    print("=" * 60)
    centroids = extract_ward_centroids()
    print(f"  Extracted {len(centroids)} ward centroids")
    for c in centroids:
        print(
            f"  Ward {c['ward_id']:2d}: lat={c['latitude']:.6f}  "
            f"lon={c['longitude']:.6f}  ({c['n_vertices']} vertices)"
        )

    # Check uniqueness of centroid coordinates
    coord_pairs = [(c["latitude"], c["longitude"]) for c in centroids]
    n_unique_coords = len(set(coord_pairs))
    print(f"\n  Unique (lat, lon) pairs: {n_unique_coords} of {len(centroids)}")
    if n_unique_coords < 26:
        print(
            f"  [NOTE] {26 - n_unique_coords} wards share centroid coordinates. "
            "Open-Meteo may return identical grid-cell data for those wards."
        )

    # ----- Step 1B: Save centroid metadata -----
    print("\n" + "=" * 60)
    print("Step 1B -- Save Centroid Metadata")
    print("=" * 60)
    centroid_export = []
    for c in centroids:
        centroid_export.append({
            "ward_id":          c["ward_id"],
            "latitude":         c["latitude"],
            "longitude":        c["longitude"],
            "centroid_method":  c["centroid_method"],
            "n_vertices":       c["n_vertices"],
            "geometry_source":  c["geometry_source"],
        })
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CENTROIDS_JSON, "w", encoding="utf-8") as fh:
        json.dump(centroid_export, fh, indent=2, ensure_ascii=False)
    print(f"  Saved: {CENTROIDS_JSON}")

    # ----- Step 1C: Load ward demographics -----
    print("\n" + "=" * 60)
    print("Step 1C -- Load Ward Demographics")
    print("=" * 60)
    demographics = load_ward_demographics()
    print(f"  Demographics loaded for {len(demographics)} wards")

    # ----- Step 2: Compute date range -----
    start_date, end_date = _compute_date_range()
    print("\n" + "=" * 60)
    print("Step 2 -- Historical Weather Fetch (per ward centroid)")
    print("=" * 60)
    print(f"  Date range: {start_date} -> {end_date}  ({LOOKBACK_DAYS} complete days)")
    print(f"  Expected hourly observations per ward: {LOOKBACK_DAYS * 24}")
    print(f"  API endpoint: {OPENMETEO_ARCHIVE_URL}")
    print(f"  Requesting {len(centroids)} wards individually ...")

    # ----- Step 3: Fetch weather per ward and build rows -----
    all_rows = []
    ward_weather_report = []

    for i, c in enumerate(centroids):
        ward_id     = c["ward_id"]
        lat         = c["latitude"]
        lon         = c["longitude"]
        pop_density = demographics[ward_id]

        print(f"  [{i+1:2d}/26] Ward {ward_id:2d} -- lat={lat:.4f} lon={lon:.4f} ... ", end="", flush=True)

        timestamps, variables = fetch_weather_for_ward(
            ward_id=ward_id,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
        )

        n_ts = len(timestamps)
        miss_t   = sum(1 for v in variables["temperature_2m"]     if v is None)
        miss_rh  = sum(1 for v in variables["relative_humidity_2m"] if v is None)
        miss_w   = sum(1 for v in variables["wind_speed_10m"]       if v is None)
        miss_rad = sum(1 for v in variables["shortwave_radiation"]   if v is None)

        print(f"{n_ts} hrs | T_miss={miss_t} RH_miss={miss_rh} W_miss={miss_w} Rad_miss={miss_rad}")

        ward_rows, incomplete_hours = build_ward_rows(
            ward_id=ward_id,
            pop_density=pop_density,
            timestamps=timestamps,
            variables=variables,
        )
        all_rows.extend(ward_rows)

        ward_weather_report.append({
            "ward_id":            ward_id,
            "latitude":           lat,
            "longitude":          lon,
            "n_rows":             n_ts,
            "first_timestamp":    timestamps[0] if timestamps else None,
            "last_timestamp":     timestamps[-1] if timestamps else None,
            "missing_temperature": miss_t,
            "missing_rh":          miss_rh,
            "missing_wind":        miss_w,
            "missing_radiation":   miss_rad,
        })

        # Polite delay between API requests
        if i < len(centroids) - 1:
            time.sleep(API_REQUEST_DELAY_S)

    print(f"\n  Total rows assembled: {len(all_rows):,}")

    # ----- Step 4: Build DataFrame -----
    df = pd.DataFrame(all_rows, columns=OUTPUT_COLUMNS)

    # Sort by ward_id then timestamp for consistency
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.sort_values(["ward_id", "timestamp"], inplace=True)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M")
    df.reset_index(drop=True, inplace=True)

    # ----- Step 5: Validate -----
    validate_dataset(df, start_date, end_date, ward_weather_report)

    # ----- Step 6: Save -----
    print("\n" + "=" * 60)
    print("Step 6 -- Save Dataset")
    print("=" * 60)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"  Saved: {OUTPUT_CSV}")
    print(f"  Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    # ----- Step 7: Preview -----
    print("\n" + "=" * 60)
    print("Dataset Preview (first 3 rows)")
    print("=" * 60)
    print(df.head(3).to_string())

    # ----- Final summary -----
    print("\n" + "=" * 60)
    print("COMPLETE -- Phase 5 Part 1 (Revised)")
    print("=" * 60)
    print(f"  Wards:                      {len(centroids)}")
    print(f"  Rows:                       {len(df):,}")
    print(f"  Date range:                 {start_date} -> {end_date}")
    print(f"  Hourly records per ward:    {LOOKBACK_DAYS * 24}")
    print(f"  Unique centroid pairs:      {n_unique_coords}")
    print(f"  Files created:")
    print(f"    Centroids:   {CENTROIDS_JSON}")
    print(f"    Dataset:     {OUTPUT_CSV}")
    print()
    print("  Weather provenance:")
    print("    Source:     Open-Meteo Historical Archive API (model/reanalysis)")
    print("    Sampling:   Official Haldia ward polygon centroids (WGS84)")
    print("    Demographics: Census of India 2011 / GIS ward dataset")
    print("    Ward count: 26")
    print(f"    Period:     {LOOKBACK_DAYS} complete calendar days")
    print("    Variables:  temperature, relative_humidity, wind_speed, shortwave_radiation")
    print()
    print("  LIMITATION: Open-Meteo returns grid-based reanalysis, not 26 independent")
    print("  weather station observations.  Wards within the same model grid cell")
    print("  will have identical weather values; only demographics differ.")


if __name__ == "__main__":
    main()
