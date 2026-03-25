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
    get_patient_evolution  # 🔥 NUEVO
)

# Librerías necesarias
import tempfile
import zipfile
from utils.gli import get_gli_reference
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

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


def ensure_session_defaults() -> None:
    defaults = {
        "include_post": False,
        "show_preview": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ----------------------------
# GLI
# ----------------------------
def calcular_predichos_lln(rows_data, edad, sexo, talla, etnia):
    if edad is None or sexo not in ["Femenino", "Masculino"] or talla is None:
        return rows_data

    rows_updated = {}

    for name, row in rows_data.items():
        pred = row.get("pred")
        lln = row.get("lln")

        gli = get_gli_reference(name, edad, talla, sexo, etnia)

        if pred is None:
            pred = gli["pred"]

        if lln is None:
            lln = gli["lln"]

        updated = row.copy()
        updated["pred"] = pred
        updated["lln"] = lln

        rows_updated[name] = updated

    return rows_updated


ensure_session_defaults()

# ----------------------------
# UI
# ----------------------------
st.title("🫁 Reporte profesional de espirometría")

with st.form("spirometry_form"):

    nombre = st.text_input("Nombre")
    identificacion = st.text_input("Documento")
    fecha_nacimiento = st.date_input("Fecha nacimiento", value=None)
    sexo = st.selectbox("Sexo", ["", "Femenino", "Masculino"])
    talla = st.number_input("Talla (cm)", value=None)
    etnia = st.selectbox("Etnia", ["", "Mestizo", "Afrodescendiente"])
    fumador = st.selectbox("Tabaquismo", ["", "No fumador", "Fumador activo"])

    submitted = st.form_submit_button("Generar")

if submitted:

    edad = age_in_years(fecha_nacimiento)

    rows_data = {
        "FEV1": {"pre": 2.5, "pred": None, "lln": None},
        "FVC": {"pre": 3.0, "pred": None, "lln": None},
        "FEV1/FVC": {"pre": 80, "pred": None, "lln": None},
    }

    rows_data = calcular_predichos_lln(rows_data, edad, sexo, talla, etnia)

    params = {}
    for k, v in rows_data.items():
        params[k] = ParameterResult(
            name=k,
            unit="",
            measured_pre=v["pre"],
            measured_post=None,
            predicted=v["pred"],
            lln=v["lln"],
            zscore_pre=None,
            zscore_post=None,
        )

    interpretation = build_interpretation(
        edad,
        params,
        "Calidad adecuada",
        fumador=fumador
    )

    patient_id = save_patient(
        nombre,
        identificacion,
        fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else "",
        sexo
    )

    # 🔥 CORREGIDO
    save_spirometry(patient_id, interpretation, params)

    st.success("Guardado correctamente")

# ----------------------------
# HISTORIAL
# ----------------------------
st.divider()
st.subheader("🧑‍⚕️ Historial de pacientes")

patients = get_all_patients()

if patients:
    opciones = {f"{p[1]} ({p[2]})": p[0] for p in patients}
    paciente_sel = st.selectbox("Seleccionar paciente", list(opciones.keys()))

    if paciente_sel:
        patient_id = opciones[paciente_sel]

        reports = get_patient_reports(patient_id)

        for r in reports:
            st.write(r)

        # ----------------------------
        # 📈 EVOLUCIÓN
        # ----------------------------
        st.markdown("### 📈 Evolución de FEV1")

        try:
            evolucion = get_patient_evolution(patient_id)
            valores = [e[1] for e in evolucion if e[1] is not None]

            if len(valores) >= 2:
                st.line_chart(valores)

                if valores[-1] > valores[0]:
                    st.success("Mejoría 📈")
                elif valores[-1] < valores[0]:
                    st.error("Deterioro 📉")
                else:
                    st.info("Sin cambios")
            else:
                st.info("Se requieren 2 estudios")
        except:
            st.warning("Error en base de datos. Reiniciar.")

else:
    st.info("No hay pacientes")