from fractions import Fraction
from math import isfinite


def positive_number(value, maximum=None):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and isfinite(value) and 0 < value
            and (maximum is None or value <= maximum))


def is_below_lln(param, maximum=None):
    if (not param or not positive_number(param.measured_pre, maximum)
            or not positive_number(param.lln, maximum)):
        return None
    if maximum == 100 and min(param.measured_pre, param.lln) <= 1:
        return None  # The form requires percentages, not ratios in [0, 1].
    return param.measured_pre < param.lln


def change_over_predicted(param):
    if not param or not all(positive_number(v) for v in
                            (param.measured_pre, param.measured_post, param.predicted)):
        return None
    # Work from the entered decimal values so exact threshold cases are stable.
    pre, post, predicted = (Fraction(str(v)) for v in
                            (param.measured_pre, param.measured_post, param.predicted))
    return (post - pre) / predicted


def bronchodilator_response(fev1, fvc, age_years, quality_ok):
    if not any(p and p.measured_post is not None for p in (fev1, fvc)):
        return "No realizado", "No se ingresaron mediciones posbroncodilatador."
    if not quality_ok:
        return "No evaluable", "Respuesta broncodilatadora no evaluable: calidad o referencias no confirmadas."

    changes = {"FEV1": change_over_predicted(fev1), "FVC": change_over_predicted(fvc)}
    positives = [name for name, change in changes.items()
                 if change is not None and change > Fraction(1, 10)]
    if positives:
        status = "Positiva (ERS/ATS)"
        detail = "Aumento >10% del predicho en " + " y ".join(positives) + "."
    elif None in changes.values():
        status = "No evaluable (ERS/ATS)"
        detail = "Datos pre, post o predichos insuficientes para descartar el criterio ERS/ATS."
    else:
        status = "No cumple el criterio (ERS/ATS)"
        detail = "Ni FEV1 ni FVC aumentaron >10% de su valor predicho."

    if isinstance(age_years, (int, float)) and 6 <= age_years < 18:
        change = changes["FEV1"]
        if change is None:
            gina = "no evaluable por datos insuficientes"
        elif change >= Fraction(12, 100):
            gina = "cumple el criterio de aumento de FEV1 ≥12% del predicho"
        else:
            gina = "no cumple el criterio de aumento de FEV1 ≥12% del predicho"
        detail += (" GINA 2026 (6–17 años), criterio espirométrico: " + gina
                   + ". Por sí solo no diagnostica ni descarta asma.")
    return status, detail


def build_interpretation(age_years, params, quality_text, fumador=None,
                         calidad=None, reproducibilidad=None, cooperacion=None,
                         referencia_verificada=False, calidad_post_confirmada=False):
    fev1, fvc, ratio = (params.get(k) for k in ("FEV1", "FVC", "FEV1/FVC"))
    quality_ok = (calidad == "Aceptable" and reproducibilidad == "Adecuada"
                  and cooperacion == "Buena")
    ratio_low = is_below_lln(ratio, maximum=100)
    fvc_low = is_below_lln(fvc)
    fev1_low = is_below_lln(fev1)

    severity = "No clasificada automáticamente"
    signal = "🟡 REVISIÓN CLÍNICA"
    if not quality_ok:
        pattern = "No clasificable automáticamente"
        comment = "Calidad, reproducibilidad o cooperación no confirmadas como adecuadas."
    elif not referencia_verificada:
        pattern = "No clasificable automáticamente"
        comment = "No se confirmó la procedencia de los valores de referencia."
    elif ratio_low is None or fvc_low is None or fev1_low is None:
        pattern = "No clasificable automáticamente"
        comment = "Faltan mediciones o LLN válidos para FEV1, FVC o FEV1/FVC."
    elif ratio_low:
        pattern = "Patrón ventilatorio obstructivo"
        comment = "FEV1/FVC por debajo del LLN."
        if fvc_low:
            comment += (" FVC baja; la espirometría no distingue atrapamiento de un componente"
                        " restrictivo. Se requiere TLC para confirmar restricción.")
    elif fvc_low:
        pattern = "FVC baja con relación FEV1/FVC conservada"
        comment = "Sugiere posible restricción, que requiere confirmación con TLC."
    elif fev1_low:
        pattern = "FEV1 bajo con FVC y relación conservadas"
        comment = "Verifique mediciones, maniobras y coherencia de los valores de referencia."
    else:
        pattern = "Espirometría basal dentro de límites normales"
        severity = "No aplica"
        signal = "🟢 NORMAL BASAL"
        comment = "FEV1, FVC y FEV1/FVC no están por debajo de sus LLN ingresados."

    status, detail = bronchodilator_response(
        fev1, fvc, age_years, quality_ok and referencia_verificada and calidad_post_confirmada)
    return {
        "pattern": pattern, "result": pattern, "severity": severity,
        "bronchodilator": status, "technical_report": f"{quality_text.rstrip('.')}. {detail}",
        "medical_comment": comment, "semaforo": signal,
    }
