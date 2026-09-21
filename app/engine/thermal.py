"""
app/engine/thermal.py

Deterministic thermodynamic and heat-stress calculation functions for the
HeatSense thermal risk engine.

Formulas implemented:
  - Clausius-Clapeyron saturation vapour pressure (August-Roche-Magnus approx.)
  - NOAA / Rothfusz Heat Index (heat_index_c, validated prototype)
  - BOM WBGT proxy — informational only, no wind subtraction (calculate_bom_wbgt)
  - Prototype 0-100 thermal normalisation (normalize_heat_index)
  - Unified validated thermal stress score (thermal_stress_score)

No ML, no stochastic elements.  All functions are pure and side-effect-free.
"""

import math

from app.engine.validation import finite_float, finite_optional_float


# ---------------------------------------------------------------------------
# 1.  Vapour Pressure
# ---------------------------------------------------------------------------

def calculate_vapor_pressure(temp_c: float, rh: float) -> float:
    """
    Estimates ambient water-vapour pressure using the Clausius-Clapeyron
    (August-Roche-Magnus approximation) equation.

    Formula:
        e = (rh / 100.0) * 6.105 * exp((17.27 * temp_c) / (237.7 + temp_c))

    Args:
        temp_c : Air temperature (°C).
        rh     : Relative humidity (%, 0–100).

    Returns:
        Actual vapour pressure (hPa / mbar), rounded to 4 d.p.

    References:
        August-Roche-Magnus approximation; coefficients from
        Alduchov & Eskridge (1996), J. Appl. Meteor., 35, 601–609.

    Examples:
        >>> round(calculate_vapor_pressure(35.0, 80.0), 2)
        44.74
    """
    temperature = finite_float(temp_c, "temp_c")
    humidity = finite_float(rh, "rh")
    if not 0.0 <= humidity <= 100.0:
        raise ValueError("rh must be between 0 and 100")
    saturation_vp = 6.105 * math.exp((17.27 * temperature) / (237.7 + temperature))
    return round((humidity / 100.0) * saturation_vp, 4)


# ---------------------------------------------------------------------------
# 2.  NOAA / Rothfusz Heat Index  (complete NWS/NOAA procedure)
# ---------------------------------------------------------------------------

def heat_index_c(temp_c: float, rh: float) -> float:
    """
    Complete NOAA/NWS Heat Index calculation.

    Implements the full procedure:
    1. Convert temperature to °F
    2. Calculate preliminary Heat Index using Steadman formula
    3. If preliminary HI < 80°F, return preliminary HI
    4. Otherwise compute Rothfusz regression
    5. Apply low-humidity adjustment if applicable
    6. Apply high-humidity adjustment if applicable
    7. Convert final result back to °C

    Args:
        temp_c : Air temperature (°C).
        rh     : Relative humidity (%, 0–100).

    Returns:
        Heat Index (°C).
    """
    temperature = finite_float(temp_c, "temp_c")
    humidity = finite_float(rh, "rh")
    if not 0.0 <= humidity <= 100.0:
        raise ValueError("rh must be between 0 and 100")

    # Convert to Fahrenheit for NWS calculations
    T_f = temperature * 9.0 / 5.0 + 32.0
    RH = humidity

    # Step 1: Preliminary Heat Index (Steadman formula)
    # HI = 0.5 * [T + 61.0 + (T - 68.0) * 1.2 + RH * 0.094]
    preliminary_hi_f = 0.5 * (T_f + 61.0 + (T_f - 68.0) * 1.2 + RH * 0.094)

    # If preliminary HI is below 80°F, return it (no Rothfusz needed)
    if preliminary_hi_f < 80.0:
        return round((preliminary_hi_f - 32.0) * 5.0 / 9.0, 2)

    # Step 2: Rothfusz regression (valid for HI >= 80°F)
    T = T_f
    hi_f = (
        -42.379
        + 2.04901523 * T
        + 10.14333127 * RH
        - 0.22475541 * T * RH
        - 0.00683783 * T**2
        - 0.05481717 * RH**2
        + 0.00122874 * T**2 * RH
        + 0.00085282 * T * RH**2
        - 0.00000199 * T**2 * RH**2
    )

    # Step 3: Low humidity adjustment
    # Applies when RH < 13% and 80°F <= T <= 112°F
    if RH < 13.0 and 80.0 <= T <= 112.0:
        adjustment = ((13.0 - RH) / 4.0) * math.sqrt((17.0 - abs(T - 95.0)) / 17.0)
        hi_f -= adjustment

    # Step 4: High humidity adjustment
    # Applies when RH > 85% and 80°F <= T <= 87°F
    if RH > 85.0 and 80.0 <= T <= 87.0:
        adjustment = ((RH - 85.0) / 10.0) * ((87.0 - T) / 5.0)
        hi_f += adjustment

    # Convert back to Celsius
    return round((hi_f - 32.0) * 5.0 / 9.0, 2)


# ---------------------------------------------------------------------------
# 3.  BOM WBGT Proxy  (informational only)
# ---------------------------------------------------------------------------

def calculate_bom_wbgt(temp_c: float, rh: float) -> float:
    """
    Simplified BOM WBGT proxy.

    IMPORTANT:
    - No wind subtraction.
    - This is only an informational proxy.
    - Do not describe it as full physical/occupational ISO WBGT.

    Args:
        temp_c : Air temperature (°C).
        rh     : Relative humidity (%, 0–100).

    Returns:
        WBGT proxy (°C), rounded to 2 d.p.
    """
    temperature = finite_float(temp_c, "temp_c")
    humidity = finite_float(rh, "rh")
    if not 0.0 <= humidity <= 100.0:
        raise ValueError("rh must be between 0 and 100")
    vp = calculate_vapor_pressure(temperature, humidity)
    return round(0.567 * temperature + 0.393 * vp + 3.94, 2)


# ---------------------------------------------------------------------------
# 4.  Prototype 0-100 thermal normalisation
# ---------------------------------------------------------------------------

def normalize_heat_index(hi_c: float) -> float:
    """
    Prototype 0-100 thermal normalization using the specified
    Heat Index severity-band boundaries.

    This is NOT an official NOAA 0-100 score.

    Bands:
        [20, 27) → [0,  25)
        [27, 32) → [25, 50)
        [32, 41) → [50, 75)
        [41, 54) → [75, 95)
        [54, 60) → [95, 100)

    Args:
        hi_c : Heat Index (°C).

    Returns:
        Normalized score (0.0 – 100.0).
    """
    bands = [
        (20, 27, 0, 25),
        (27, 32, 25, 50),
        (32, 41, 50, 75),
        (41, 54, 75, 95),
        (54, 60, 95, 100),
    ]

    heat_index = finite_float(hi_c, "hi_c")
    if heat_index <= 20:
        return 0.0

    if heat_index >= 60:
        return 100.0

    for lo, hi, out_lo, out_hi in bands:
        if lo <= heat_index < hi:
            return out_lo + (heat_index - lo) / (hi - lo) * (out_hi - out_lo)

    return 100.0


# ---------------------------------------------------------------------------
# 5.  Unified validated thermal stress score
# ---------------------------------------------------------------------------

def thermal_stress_score(
    temp_c: float,
    rh: float,
    wind_kmh: float | None,
    radiation_w_m2: float | None,
) -> dict:
    """
    Returns the validated prototype thermal-stress score.

    Wind and radiation are optional.

    If either is None:
    - do not error
    - do not fabricate a value
    - apply no adjustment
    - omit that variable from inputs_used

    radiation_bonus and wind_relief are prototype adjustments.
    They must NOT be described as physical WBGT/radiation calculations.

    Args:
        temp_c         : Air temperature (°C).
        rh             : Relative humidity (%, 0–100).
        wind_kmh       : Wind speed (km/h), or None if unavailable.
        radiation_w_m2 : Shortwave radiation (W/m²), or None if unavailable.

    Returns:
        dict with keys:
            score           (float)   : Final clamped score [0, 100].
            method          (str)     : Identifier string.
            base_score      (float)   : Normalized HI component (pre-adjustment).
            heat_index_c    (float)   : Raw Heat Index (°C).
            wbgt_proxy_c    (None)    : Caller may populate via calculate_bom_wbgt().
            radiation_bonus (float)   : Prototype solar adjustment applied.
            wind_relief     (float)   : Prototype wind relief applied.
            inputs_used     (list)    : Variables that contributed to this score.
    """
    temperature = finite_float(temp_c, "temp_c")
    humidity = finite_float(rh, "rh")
    wind = finite_optional_float(wind_kmh, "wind_kmh")
    radiation = finite_optional_float(radiation_w_m2, "radiation_w_m2")
    if not 0.0 <= humidity <= 100.0:
        raise ValueError("rh must be between 0 and 100")
    if wind is not None and wind < 0.0:
        raise ValueError("wind_kmh must be non-negative")
    if radiation is not None and radiation < 0.0:
        raise ValueError("radiation_w_m2 must be non-negative")

    hi = heat_index_c(temperature, humidity)
    base = normalize_heat_index(hi)

    radiation_bonus = 0.0
    wind_relief = 0.0
    inputs_used = ["temperature", "relative_humidity"]

    if radiation is not None:
        radiation_bonus = min(radiation / 800, 1) * 5
        inputs_used.append("radiation")

    if wind is not None:
        wind_relief = min(wind / 20, 1) * 5
        inputs_used.append("wind")

    score = max(0.0, min(100.0, base + radiation_bonus - wind_relief))

    return {
        "score": round(score, 2),
        "method": "heat_index_noaa_normalized_v1",
        # Keep this field so driver generation can distinguish
        # the normalized HI component from the final adjusted score.
        "base_score": round(base, 2),
        "heat_index_c": round(hi, 2),
        # Informational only.
        # Caller may populate this using calculate_bom_wbgt().
        "wbgt_proxy_c": None,
        "radiation_bonus": round(radiation_bonus, 2),
        "wind_relief": round(wind_relief, 2),
        "inputs_used": inputs_used,
    }


# ---------------------------------------------------------------------------
# DEPRECATED — kept only so existing test imports resolve.
# Do NOT call from the active pipeline.  Use thermal_stress_score() instead.
# ---------------------------------------------------------------------------

def calculate_heat_index(temp_c: float, rh: float) -> float:
    """
    DEPRECATED wrapper: delegates to heat_index_c().

    Retained for backward compatibility with test_thermal_math.py imports.
    The old Steadman branch and arid/humid adjustments are removed; the
    validated NOAA Rothfusz regression is now used for all temperatures
    at or above 26.7°C, and temp_c is returned unchanged below that.
    """
    return round(heat_index_c(temp_c, rh), 2)


def compute_thermal_metrics(
    macro_temp: float,
    rh: float,
    wind_speed_kmh: float,
    lst_anomaly: float,
) -> dict:
    """
    DEPRECATED — population-density-derived LST path removed from the active
    pipeline (Step 2).  This wrapper is retained only so that existing
    test_thermal_math.py tests that import it do not break.

    The function still executes its original logic for backward-compatible
    test assertions; it is simply no longer called from main.py or htsi.py.

    TODO: remove in a future cleanup sprint once dependent tests are updated.
    """
    # Import here to avoid circular issues; downscale.py is still present.
    from app.engine.downscale import downscale_temperature  # noqa: PLC0415

    downscaled_temp = downscale_temperature(macro_temp, lst_anomaly)
    # Use old wind-adjusted BOM formula internally so existing test assertions
    # (wind_cap_at_4_ms, higher_wind_gives_lower_wbgt) continue to pass.
    w_ms = wind_speed_kmh / 3.6
    vp = calculate_vapor_pressure(downscaled_temp, rh)
    base_wbgt = 0.567 * downscaled_temp + 0.393 * vp + 3.94
    adjusted_wbgt = round(base_wbgt - (0.75 * min(w_ms, 4.0)), 2)

    return {
        "downscaled_temp": downscaled_temp,
        "wbgt_proxy": adjusted_wbgt,
        "heat_index": calculate_heat_index(downscaled_temp, rh),
    }
