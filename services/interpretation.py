# services/interpretation.py

from typing import Dict, List, Optional, Tuple
from services.spirometry_logic import ParameterResult


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


def bronchodilator_response(
    fev1: ParameterResult,
    fvc: ParameterResult,
    age_years: Optional[float]
) -> Tuple[str, str]:

    notes: List[str] = []

    def eval_param(param: ParameterResult, label: str):
        delta_abs = param.delta_abs
        delta_pct = param.delta_pct_baseline

        if delta_abs is None or delta_pct is None:
            return False, delta_abs, delta_pct

        delta_abs_ml = delta_abs * 1000 if param.unit.lower() == "l" else delta_abs
        classic = delta_pct >= 12 and delta_abs_ml >= 200
        pediatric_support = age_years is not None and age_years < 18 and delta_pct >= 12

        positive = classic or pediatric_support

        if positive:
            if classic:
                notes.append(f"Respuesta significativa en {label} (Δ {delta_pct:.1f}% y {delta_abs_ml:.0f} mL).")
            else:
                notes.append(f"Respuesta sugestiva en {label} para contexto pediátrico (Δ {delta_pct:.1f}%).")

        return positive, delta_abs_ml, delta_pct

    pos_fev1, _, _ = eval_param(fev1, "FEV1")
    pos_fvc, _, _ = eval_param(fvc, "FVC")

    if pos_fev1 or pos_fvc:
        return "Significativa", " ".join(notes)

    return "No significativa", "Sin cambios relevantes tras administración de broncodilatador."


def build_interpretation(
    age_years: Optional[float],
    params: Dict[str, ParameterResult],
    quality_text: str
) -> Dict[str, str]:

    fev1 = params["FEV1"]
    fvc = params["FVC"]
    ratio = params["FEV1/FVC"]
    fef2575 = params.get("FEF25-75")

    ratio_cutoff = lower_limit_ratio(age_years)
    ratio_low = is_below_lln(ratio.measured_pre, ratio.lln, ratio_cutoff)
    fvc_low = is_below_lln(fvc.measured_pre, fvc.lln) or ((fvc.pct_pred_pre or 999) < 80)

    pattern = "Espirometría dentro de límites normales"
    severity = "No aplica"
    comments: List[str] = []

    if ratio_low and not fvc_low:
        pattern = "Patrón ventilatorio obstructivo"
        severity = severity_from_percent(fev1.pct_pred_pre)
        comments.append("Relación FEV1/FVC disminuida, compatible con obstrucción al flujo aéreo.")
    elif not ratio_low and fvc_low:
        pattern = "Patrón restrictivo probable"
        severity = severity_from_percent(fvc.pct_pred_pre)
        comments.append("FVC disminuida con relación FEV1/FVC conservada.")
    elif ratio_low and fvc_low:
        pattern = "Patrón ventilatorio mixto"
        comments.append("Patrón mixto.")

    broncho_status = "No realizado"
    broncho_note = "No se realizó medición post broncodilatador."

    if fev1.measured_post is not None or fvc.measured_post is not None:
        broncho_status, broncho_note = bronchodilator_response(fev1, fvc, age_years)

    technical_report = pattern
    medical_comment = " ".join(comments + [broncho_note])

    return {
        "pattern": pattern,
        "result": pattern,
        "severity": severity,
        "bronchodilator": broncho_status,
        "technical_report": technical_report,
        "medical_comment": medical_comment,
    }