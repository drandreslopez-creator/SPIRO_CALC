# services/interpretation.py

from typing import Dict, List, Optional, Tuple
from services.spirometry_logic import ParameterResult

# pega aquí todas las funciones
def lower_limit_ratio(age_years: Optional[float]) -> float:
    if age_years is None:
        return 0.75
    if age_years < 18:
        return 0.85
    if age_years < 40:
        return 0.75
    return 0.70


def is_below_lln(value: Optional[float], lln: Optional[float], fallback: Optional[float] = None) -> bool:
    if value is None:
        return False
    if lln is not None:
        return value < lln
    if fallback is not None:
        return value < fallback
    return False


def severity_from_percent(pct: Optional[float]) -> str:
    if pct is None:
        return "No clasificable"
    if pct >= 80:
        return "Leve"
    if 60 <= pct < 80:
        return "Moderado"
    if 40 <= pct < 60:
        return "Severo"
    return "Muy severo"


def bronchodilator_response(fev1: ParameterResult, fvc: ParameterResult, age_years: Optional[float]) -> Tuple[str, str]:
    notes: List[str] = []

def build_interpretation(age_years: Optional[float], params: Dict[str, ParameterResult], quality_text: str) -> Dict[str, str]:
    fev1 = params["FEV1"]
    fvc = params["FVC"]
    ratio = params["FEV1/FVC"]
    fef2575 = params.get("FEF25-75")
