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

    # 🔥 EVITAR ERROR CON "N/A"
    if isinstance(lln, str):
        lln = None

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


def bronchodilator_response(fev1: ParameterResult, fvc: ParameterResult, age_years: Optional[float]) -> Tuple[str, str]:

    notes: List[str] = []

    def eval_param(param: ParameterResult, label: str):
        if param.delta_abs is None or param.delta_pct_baseline is None:
            return False

        delta_abs_ml = param.delta_abs * 1000 if param.unit.lower() == "l" else param.delta_abs
        classic = param.delta_pct_baseline >= 12 and delta_abs_ml >= 200
        pediatric = age_years is not None and age_years < 18 and param.delta_pct_baseline >= 12

        if classic or pediatric:
            notes.append(f"Respuesta significativa en {label}.")
            return True

        return False

    if eval_param(fev1, "FEV1") or eval_param(fvc, "FVC"):
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

    fev1 = params.get("FEV1")
    fvc = params.get("FVC")
    ratio = params.get("FEV1/FVC")
    fef2575 = params.get("FEF25-75")

    fev1_pct = fev1.pct_pred_pre if fev1 else None
    ratio_cutoff = lower_limit_ratio(age_years)

    ratio_low = is_below_lln(ratio.measured_pre if ratio else None, ratio.lln if ratio else None, ratio_cutoff)
    fvc_low = is_below_lln(fvc.measured_pre if fvc else None, fvc.lln if fvc else None) or ((fvc.pct_pred_pre or 999) < 80 if fvc else False)
    fev1_low = is_below_lln(fev1.measured_pre if fev1 else None, fev1.lln if fev1 else None) or ((fev1.pct_pred_pre or 999) < 80 if fev1 else False)

    pattern = "Espirometría dentro de límites normales"
    severity = "No aplica"
    comments = []

    if calidad:
        comments.append(evaluar_calidad(calidad, reproducibilidad, cooperacion))

    if ratio_low and not fvc_low:
        pattern = "Patrón ventilatorio obstructivo"
        severity = severity_from_percent(fev1_pct)
        comments.append("Relación FEV1/FVC disminuida.")

    elif not ratio_low and fvc_low:
        pattern = "Patrón restrictivo probable"
        severity = severity_from_percent(fvc.pct_pred_pre if fvc else None)

    elif ratio_low and fvc_low:
        pattern = "Patrón mixto"
        severity = severity_from_percent(min([x for x in [fev1_pct, fvc.pct_pred_pre if fvc else None] if x is not None], default=None))

    else:
        comments.append("No se evidencian alteraciones ventilatorias significativas.")

    # 🔥 BLOQUE CORREGIDO (BIEN INDENTADO)
    try:
        pct_fef = getattr(fef2575, "pct_pred_pre", None)

        if pct_fef is not None and pct_fef < 65:
            comments.append(
                "Disminución de flujos de vías aéreas pequeñas (hallazgo inespecífico)."
            )

            if not ratio_low and not fvc_low and not fev1_low:
                comments.append(
                    "Hallazgo aislado sin valor diagnóstico independiente."
                )
    except:
        pass

    broncho_status = "No realizado"
    broncho_note = "No se realizó prueba broncodilatadora."

    if fev1 and fvc and (fev1.measured_post or fvc.measured_post):
        broncho_status, broncho_note = bronchodilator_response(fev1, fvc, age_years)

    technical_report = f"{quality_text.rstrip('.')}.\n{pattern.upper()}"
    medical_comment = " ".join(comments + [broncho_note])

    return {
        "pattern": pattern,
        "result": pattern,
        "severity": severity,
        "bronchodilator": broncho_status,
        "technical_report": technical_report,
        "medical_comment": medical_comment,
        "semaforo": clasificar_semaforo(pattern, severity)
    }