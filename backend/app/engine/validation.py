import math


def finite_float(value, field_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite number")
    return result


def finite_optional_float(value, field_name: str) -> float | None:
    if value is None:
        return None
    return finite_float(value, field_name)
