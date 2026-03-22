# utils/calculations.py

import math
from typing import Optional

def fmt_num(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
    if value is None or value == "":
        return "—"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(value):
        return "—"
    return f"{value:.{digits}f}{suffix}"

def safe_float(value) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def estimate_sd(predicted: float, param_name: str) -> Optional[float]:
    """
    Estima desviación estándar basada en coeficiente de variación (CV)
    Valores aproximados basados en literatura espirométrica.
    """
    if predicted is None:
        return None

    cv_map = {
        "FEV1": 0.15,
        "FVC": 0.15,
        "FEV1/FVC": 0.08,
        "FEF25-75": 0.25,
        "PEF": 0.20,
    }

    cv = cv_map.get(param_name, 0.20)
    return predicted * cv


def calculate_zscore(measured: Optional[float], predicted: Optional[float], param_name: str) -> Optional[float]:
    if measured is None or predicted is None:
        return None

    sd = estimate_sd(predicted, param_name)
    if sd in (None, 0):
        return None

    return (measured - predicted) / sd