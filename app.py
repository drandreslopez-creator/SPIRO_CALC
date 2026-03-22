
from __future__ import annotations

import math
from datetime import date
from typing import Optional, Dict
import streamlit as st

st.set_page_config(page_title="Espirometría | Dr. Andrés López Ruiz", page_icon="🫁", layout="wide")

# ----------------------------
# Helpers
# ----------------------------
def safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except:
        return None

def age_in_years(dob: Optional[date]) -> Optional[float]:
    if not dob:
        return None
    today = date.today()
    return round((today - dob).days / 365.25, 2)

def age_text(dob: Optional[date]) -> str:
    if not dob:
        return ""
    today = date.today()
    years = today.year - dob.year
    months = today.month - dob.month
    if today.day < dob.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    parts = []
    if years > 0:
        parts.append(f"{years} año{'s' if years != 1 else ''}")
    if months > 0 or not parts:
        parts.append(f"{months} mes{'es' if months != 1 else ''}")
    return " y ".join(parts)

def estimate_sd(predicted: float, param_name: str):
    if predicted is None:
        return None
    return predicted * 0.15

def calcular_predichos_lln(rows_data: dict, edad, sexo, talla):
    if edad is None or sexo not in ["Femenino", "Masculino"] or talla is None:
        return rows_data
    out = {}
    for k,v in rows_data.items():
        pred = v.get("pred") or (talla * 0.04 if sexo=="Masculino" else talla * 0.035)
        sd = estimate_sd(pred, k) or pred*0.15
        lln = v.get("lln") or (pred - 1.64*sd)
        v2 = v.copy()
        v2["pred"] = pred
        v2["lln"] = lln
        out[k]=v2
    return out

# ----------------------------
# UI
# ----------------------------
st.title("🫁 Reporte profesional de espirometría")

with st.form("spirometry_form"):
    st.subheader("Datos del paciente")

    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre completo")
    identificacion = c2.text_input("Documento")
    eps = c3.text_input("EPS")

    c4, c5, c6 = st.columns(3)
    fecha_nacimiento = c4.date_input("Fecha de nacimiento", value=None)
    sexo = c5.selectbox("Sexo", ["", "Femenino", "Masculino"])
    remitente = c6.text_input("Médico remitente")

    # ✅ BLOQUE CORREGIDO
    c7, c8, c9, c10 = st.columns(4)

    peso = c7.number_input("Peso (kg)", min_value=0.0, step=0.1)
    talla = c8.number_input("Talla (cm)", min_value=0.0, step=0.1)

    grupo_etnico = c9.selectbox(
        "Grupo étnico",
        ["", "Latino", "Caucásico", "Afrodescendiente", "Asiático", "Otro"]
    )

    fumador = c10.selectbox(
        "¿Fuma?",
        ["No", "Exfumador", "Sí"]
    )

    # nueva fila
    c11, c12 = st.columns(2)
    fecha_estudio = c11.date_input("Fecha del estudio", value=date.today())
    id_tipo = c12.selectbox("Tipo de documento", ["CC", "TI", "RC", "CE"])

    # valores básicos
    rows_data = {
        "FEV1": {"pre": 2.5, "pred": None, "lln": None},
        "FVC": {"pre": 3.0, "pred": None, "lln": None},
    }

    submitted = st.form_submit_button("Generar")

if submitted:
    edad_num = age_in_years(fecha_nacimiento)
    edad_txt = age_text(fecha_nacimiento)

    rows_data = calcular_predichos_lln(rows_data, edad_num, sexo, talla)

    patient_dict = {
        "nombre": nombre,
        "identificacion": f"{id_tipo} {identificacion}".strip(),
        "fecha_nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if fecha_nacimiento else "",
        "edad": edad_txt,
        "sexo": sexo,
        "eps": eps,
        "peso": f"{peso:.1f} kg" if peso else "",
        "talla": f"{talla:.1f} cm" if talla else "",
        "remitente": remitente,
        "grupo_etnico": grupo_etnico,
        "fumador": fumador,
    }

    st.success("Funciona correctamente ✅")
    st.write(patient_dict)
