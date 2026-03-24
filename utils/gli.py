# utils/gli.py

from typing import Dict, Optional

def get_gli_reference(param: str, edad: float, talla: float, sexo: str, etnia: str) -> Dict:
    """
    Retorna valores predichos, LLN y z-score basados en GLI (simulado inicial).
    Luego lo reemplazamos por tablas reales.
    """

    # 🔴 TEMPORAL (placeholder clínico mejorado)
    if param in ["FEV1", "FVC"]:
        if sexo == "Masculino":
            pred = (0.041 * talla) - (0.024 * edad) - 2.19
        else:
            pred = (0.034 * talla) - (0.025 * edad) - 1.578

        lln = pred * 0.8

    elif param == "FEV1/FVC":
        pred = 0.82 if edad < 40 else 0.78
        lln = pred - 0.07

    else:
        pred = None
        lln = None

    return {
        "pred": pred,
        "lln": lln
    }