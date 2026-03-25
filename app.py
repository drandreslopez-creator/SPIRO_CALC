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
    get_patient_reports
)

# Librerías necesarias
from utils.gli import get_gli_reference
from datetime import date
from pathlib import Path
from typing import Optional
import streamlit as st
import pandas as pd

# Configuración
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Espirometría | Dr. Andrés López Ruiz",
    page_icon="🫁",
    layout="wide"
)

init_db()

# ----------------------------
# Helpers
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
    return f"{years} años {months} meses"


# ----------------------------
# UI
# ----------------------------
st.title("🫁 Reporte profesional de espirometría")

with st.form("form"):
    nombre = st.text_input("Nombre")
    identificacion = st.text_input("Documento")
    sexo = st.selectbox("Sexo", ["", "Femenino", "Masculino"])

    fecha_nacimiento = st.date_input("Fecha nacimiento", value=None)

    st.subheader("Valores")

    fev1 = st.number_input("FEV1", value=None)
    fvc = st.number_input("FVC", value=None)
    ratio = st.number_input("FEV1/FVC", value=None)

    submitted = st.form_submit_button("Guardar")

if submitted:

    edad = age_in_years(fecha_nacimiento)

    params = {
        "FEV1": ParameterResult("FEV1","L",fev1,None,1,0,None,None),
        "FVC": ParameterResult("FVC","L",fvc,None,1,0,None,None),
        "FEV1/FVC": ParameterResult("FEV1/FVC","%",ratio,None,1,0,None,None),
    }

    interpretation = build_interpretation(
        edad,
        params,
        "Calidad adecuada"
    )

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

        if reports:
            fechas = []
            fev1_vals = []

            for r in reports:
                fechas.append(r[0])
                fev1_vals.append(r[1])

                st.write(f"Fecha: {r[0]} - FEV1: {r[1]}")

            df = pd.DataFrame({"Fecha": fechas, "FEV1": fev1_vals})
            st.line_chart(df.set_index("Fecha"))
        else:
            st.info("Sin estudios")
