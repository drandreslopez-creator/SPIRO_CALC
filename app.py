from __future__ import annotations

# Módulos propios
from utils.calculations import *
from services.interpretation import build_interpretation
from services.spirometry_logic import ParameterResult
from services.pdf_generator import make_pdf, build_values_dataframe, build_summary_chart
from services.database import (
    init_db,
    save_patient,
    save_spirometry,
    get_all_patients,
    get_patient_reports,
    get_patient_evolution
)

# Librerías
from utils.gli import get_gli_reference
from datetime import date
from pathlib import Path
from typing import Optional

import streamlit as st

# ----------------------------
# CONFIG
# ----------------------------
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Espirometría | Dr. Andrés López Ruiz",
    page_icon="🫁",
    layout="wide"
)

init_db()

# ----------------------------
# HELPERS
# ----------------------------
def age_in_years(dob: Optional[date]) -> Optional[float]:
    if not dob:
        return None
    return round((date.today() - dob).days / 365.25, 2)


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
    return f"{years} años {months} meses"


def calcular_predichos_lln(rows_data, edad, sexo, talla, etnia):
    if edad is None or talla is None:
        return rows_data

    for name, row in rows_data.items():
        gli = get_gli_reference(name, edad, talla, sexo, etnia)
        if row["pred"] is None:
            row["pred"] = gli["pred"]
        if row["lln"] is None:
            row["lln"] = gli["lln"]

    return rows_data


# ----------------------------
# UI
# ----------------------------
st.title("🫁 Reporte de espirometría")

with st.form("form"):
    nombre = st.text_input("Nombre")
    identificacion = st.text_input("Documento")
    fecha_nacimiento = st.date_input("Fecha nacimiento", value=None)
    sexo = st.selectbox("Sexo", ["", "Femenino", "Masculino"])
    talla = st.number_input("Talla cm", value=None)

    fumador = st.selectbox("Tabaquismo", ["", "No fumador", "Exfumador", "Fumador activo"])

    st.subheader("Valores")

    fev1 = st.number_input("FEV1", value=None)
    fvc = st.number_input("FVC", value=None)
    ratio = st.number_input("FEV1/FVC", value=None)

    submitted = st.form_submit_button("Generar")

# ----------------------------
# PROCESAMIENTO
# ----------------------------
if submitted:

    edad = age_in_years(fecha_nacimiento)

    params = {
        "FEV1": ParameterResult("FEV1", "L", fev1, None, None, None, None, None),
        "FVC": ParameterResult("FVC", "L", fvc, None, None, None, None, None),
        "FEV1/FVC": ParameterResult("FEV1/FVC", "%", ratio, None, None, None, None, None),
    }

    interpretation = build_interpretation(
        edad,
        params,
        "Calidad adecuada",
        fumador=fumador
    )

    # 🔥 GUARDAR
    patient_id = save_patient(
        nombre,
        identificacion,
        fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else "",
        sexo
    )

    save_spirometry(patient_id, interpretation, params)

    st.success("Guardado correctamente")

# ----------------------------
# HISTORIAL
# ----------------------------
st.divider()
st.subheader("Historial")

patients = get_all_patients()

if patients:
    opciones = {f"{p[1]} ({p[2]})": p[0] for p in patients}
    paciente_sel = st.selectbox("Paciente", list(opciones.keys()))

    if paciente_sel:
        patient_id = opciones[paciente_sel]

        reports = get_patient_reports(patient_id)

        for r in reports:
            st.write(r)

        # ----------------------------
        # EVOLUCIÓN
        # ----------------------------
        st.subheader("📈 Evolución FEV1")

        try:
            evolucion = get_patient_evolution(patient_id)
            valores = [e[1] for e in evolucion if e[1] is not None]

            if len(valores) >= 2:
                st.line_chart(valores)

                if valores[-1] > valores[0]:
                    st.success("Mejoría")
                elif valores[-1] < valores[0]:
                    st.error("Deterioro")
                else:
                    st.info("Sin cambios")
            else:
                st.info("Necesitas al menos 2 estudios")
        except:
            st.warning("Reinicia la base de datos")
else:
    st.info("No hay pacientes aún")