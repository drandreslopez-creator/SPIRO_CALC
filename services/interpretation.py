def severity_from_percent(pct):
    if pct is None:
        return "No clasificable"
    if pct >= 80:
        return "Leve"
    if 60 <= pct < 80:
        return "Moderado"
    if 40 <= pct < 60:
        return "Severo"
    return "Muy severo"

def build_interpretation(age, params):
    fev1 = params["FEV1"]
    fvc = params["FVC"]
    ratio = params["FEV1/FVC"]

    ratio_low = ratio.pct_pred_pre and ratio.pct_pred_pre < 80
    fvc_low = fvc.pct_pred_pre and fvc.pct_pred_pre < 80

    if ratio_low and not fvc_low:
        return "Patrón obstructivo"
    elif not ratio_low and fvc_low:
        return "Patrón restrictivo"
    elif ratio_low and fvc_low:
        return "Patrón mixto"
    else:
        return "Normal"
