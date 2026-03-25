from __future__ import annotations

# Módulos propios
from utils.calculations import *
from services.interpretation import build_interpretation
from services.spirometry_logic import ParameterResult
from services.pdf_generator import make_pdf, build_values_dataframe, build_summary_chart

# Librerías necesarias
from utils.gli import get_gli_reference
from datetime import date
from pathlib import Path
from typing import Optional

import streamlit as st

# Configuración
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Espirometría | Dr. Andrés López Ruiz",
    page_icon="🫁",
    layout="wide"
)

# ----------------------------
# Utility helpers
# ----------------------------
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


# ----------------------------
# GLI
# ----------------------------
def calcular_predichos_lln(rows_data, edad, sexo, talla, etnia):

    if edad is None or sexo not in ["Femenino", "Masculino"] or talla is None:
        return rows_data

    rows_updated = {}

    for name, row in rows_data.items():
        gli = get_gli_reference(name, edad, talla, sexo, etnia)

        updated = row.copy()
        updated["pred"] = row.get("pred") or gli["pred"]
        updated["lln"] = row.get("lln") or gli["lln"]

        rows_updated[name] = updated

    return rows_updated


# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

    st.markdown("### Consultorio Dr. Andrés López Ruiz")
    st.caption("Médico Pediatra · Generador de reportes de espirometría")

    st.markdown(
        "Este aplicativo crea un reporte imprimible en PDF con tabla de resultados, "
        "interpretación técnica y comentario médico."
    )

    st.info(
        "La interpretación automática es una ayuda clínica. Debe correlacionarse con la evaluación médica."
    )

# ----------------------------
# UI
# ----------------------------
st.title("🫁 Reporte profesional de espirometría")
st.write("Ingrese los datos del paciente y los parámetros espirométricos.")

# ----------------------------
# FORM
# ----------------------------
with st.form("spirometry_form"):

    st.subheader("Datos del paciente")

    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre completo")
    identificacion = c2.text_input("Documento")
    eps = c3.text_input("EPS")

    c4, c5, c6 = st.columns(3)
    fecha_nacimiento = c4.date_input("Fecha nacimiento", value=None)
    sexo = c5.selectbox("Sexo", ["", "Femenino", "Masculino"])
    remitente = c6.text_input("Médico remitente")

    c7, c8 = st.columns(2)
    etnia = c7.selectbox("Etnia", ["", "Mestizo", "Afrodescendiente", "Indígena"])
    fumador = c8.selectbox("Tabaquismo", ["", "No fumador", "Exfumador", "Fumador activo"])

    c9, c10 = st.columns(2)
    peso = c9.number_input("Peso", value=None)
    talla = c10.number_input("Talla", value=None)

    st.subheader("Valores espirométricos")

    param_config = [
        ("FVC", "L"),
        ("FEV1", "L"),
        ("FEV1/FVC", "%"),
    ]

    rows_data = {}

    for name, unit in param_config:
        pre = st.number_input(f"{name} pre")
        pred = st.number_input(f"{name} pred")
        lln = st.number_input(f"{name} lln")

        rows_data[name] = {
            "unit": unit,
            "pre": safe_float(pre),
            "pred": safe_float(pred),
            "lln": safe_float(lln),
            "post": None,
        }

    submitted = st.form_submit_button("Generar reporte")

# ----------------------------
# PROCESO
# ----------------------------
if submitted:

    edad = age_in_years(fecha_nacimiento)

    rows_data = calcular_predichos_lln(rows_data, edad, sexo, talla, etnia)

    params = {}

    for name, row in rows_data.items():
        params[name] = ParameterResult(
            name=name,
            unit=row["unit"],
            measured_pre=row["pre"],
            measured_post=None,
            predicted=row["pred"],
            lln=row["lln"],
            zscore_pre=None,
            zscore_post=None
        )

    interpretation = build_interpretation(
        edad,
        params,
        "Calidad adecuada",
        fumador=fumador
    )

    st.success("Reporte generado correctamente")

    st.write(interpretation["technical_report"])
    st.write(interpretation["medical_comment"])
