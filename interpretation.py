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


def clasificar_gold(fev1_pct):
    if fev1_pct is None:
        return None
    if fev1_pct >= 80:
        return "GOLD 1 (leve)"
    elif 50 <= fev1_pct < 80:
        return "GOLD 2 (moderado)"
    elif 30 <= fev1_pct < 50:
        return "GOLD 3 (severo)"
    else:
        return "GOLD 4 (muy severo)"


def clasificar_semaforo(pattern, severity):

    if pattern and "normal" in pattern.lower():
        return "🟢 NORMAL"

    if severity:
        sev = severity.lower()

        if "leve" in sev:
            return "🟡 ALTERACIÓN LEVE"

        if "moderado" in sev:
            return "🟡 ALTERACIÓN MODERADA"

        if "severo" in sev:
            return "🔴 ALTERACIÓN SEVERA"

    return "🟡 RESULTADO A INTERPRETAR"


def evaluar_calidad(calidad, reproducibilidad, cooperacion):
    if calidad == "No aceptable":
        return "Estudio no aceptable según criterios ATS/ERS. Interpretación no confiable."
    if reproducibilidad == "No adecuada":
        return "Reproducibilidad no adecuada, interpretar con precaución."
    if cooperacion == "Limitada":
        return "Cooperación limitada, posible subestimación de los valores."
    if calidad == "Aceptable con limitaciones":
        return "Estudio aceptable con limitaciones técnicas."
    return "Calidad adecuada según criterios ATS/ERS."


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
    age_years,
    params,
    quality_text,
    fumador=None,
    calidad=None,
    reproducibilidad=None,
    cooperacion=None
):

    fev1 = params["FEV1"]
    fvc = params["FVC"]
    ratio = params["FEV1/FVC"]
    fef2575 = params.get("FEF25-75")

    fev1_pct = fev1.pct_pred_pre

    ratio_cutoff = lower_limit_ratio(age_years)

    ratio_low = is_below_lln(ratio.measured_pre, ratio.lln, ratio_cutoff)
    fvc_low = is_below_lln(fvc.measured_pre, fvc.lln) or ((fvc.pct_pred_pre or 999) < 80)
    fev1_low = is_below_lln(fev1.measured_pre, fev1.lln) or ((fev1.pct_pred_pre or 999) < 80)

    pattern = "Espirometría dentro de límites normales"
    severity = "No aplica"
    comments = []

    if calidad:
        comments.append(evaluar_calidad(calidad, reproducibilidad, cooperacion))

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
        severity = severity_from_percent(
            min(filter(lambda x: x is not None, [fev1.pct_pred_pre, fvc.pct_pred_pre]), default=None)
        )
        comments.append("Disminución simultánea de FEV1/FVC y FVC.")

    else:
        comments.append("No se evidencian alteraciones ventilatorias significativas.")

    if fef2575 and fef2575.pct_pred_pre is not None and fef2575.pct_pred_pre < 65:
        comments.append("Disminución de flujos de vías aéreas pequeñas (FEF25-75 reducido - hallazgo inespecífico que debe interpretarse con cautela y en contexto clínico.")

    broncho_status = "No realizado"
    broncho_note = "No se realizó prueba broncodilatadora."

    if fev1.measured_post is not None or fvc.measured_post is not None:
        broncho_status, broncho_note = bronchodilator_response(fev1, fvc, age_years)

    if ratio_low:
        if fumador == "Fumador activo":
            gold = clasificar_gold(fev1_pct)
            if gold:
                comments.append(
                    f"Patrón obstructivo en contexto de tabaquismo, compatible con EPOC {gold} según severidad funcional."
                )
            else:
                comments.append(
                    "Patrón obstructivo en contexto de tabaquismo, considerar EPOC según clínica."
                )

        elif broncho_status == "Significativa":
            comments.append(
                "Obstrucción con respuesta broncodilatadora significativa, compatible con asma."
            )

    if fumador == "Fumador activo" and not ratio_low:
        comments.append(
            "Antecedente de tabaquismo, se recomienda seguimiento funcional periódico."
        )

    if fumador == "Exfumador":
        comments.append(
            "Antecedente de tabaquismo, considerar riesgo residual de enfermedad obstructiva."
        )

    technical_lines = [quality_text.strip()] if quality_text.strip() else []
    technical_lines.append(pattern)

    if severity != "No aplica":
        technical_lines.append(f"Severidad funcional: {severity}.")

    if broncho_status != "No realizado":
        technical_lines.append(f"Respuesta broncodilatadora: {broncho_status.lower()}.")

    if ratio_low and fumador == "Fumador activo":
        gold = clasificar_gold(fev1_pct)
        if gold:
            technical_lines.append(f"Clasificación GOLD: {gold}.")

    technical_report = " ".join(technical_lines)
    medical_comment = " ".join(comments + [broncho_note])

    semaforo = clasificar_semaforo(pattern, severity)

    return {
        "pattern": pattern,
        "result": pattern,
        "severity": severity,
        "bronchodilator": broncho_status,
        "technical_report": technical_report,
        "medical_comment": medical_comment,
        "semaforo": semaforo
    }
