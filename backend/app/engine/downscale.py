"""
app/engine/downscale.py

TODO: real satellite LST integration - not implemented in this MVP

The population-density-derived LST anomaly proxy that previously existed here
has been removed from the active pipeline (SIH-backend Step 2 cleanup).
There is NO relationship of population density → LST anomaly in this module.

The downscale_temperature() function is retained only because existing
test_thermal_math.py tests still import and exercise it directly.  It is
NOT called from the active application pipeline (main.py / thermal.py).
"""


def downscale_temperature(
    macro_temp: float,
    lst_anomaly: float,
    alpha: float = 0.35,
) -> float:
    """
    RETAINED FOR EXISTING TESTS ONLY — not used in the active pipeline.

    Applies an LST anomaly offset to downscale macro grid temperature to a
    ward-level estimate.  In the current MVP there is no real satellite LST
    source; this function exists solely so that legacy test assertions that
    import it do not break.

    Formula:
        T_ward = T_macro + (alpha * lst_anomaly)

    Args:
        macro_temp  : Open-Meteo 2 m air temperature (°C).
        lst_anomaly : LST anomaly (°C).
        alpha       : Blending coefficient (default 0.35).

    Returns:
        Downscaled temperature estimate (°C), rounded to 2 d.p.

    Examples:
        >>> downscale_temperature(35.0, 4.0)
        36.4
        >>> downscale_temperature(35.0, -2.0, alpha=0.5)
        34.0
    """
    return round(macro_temp + (alpha * lst_anomaly), 2)
