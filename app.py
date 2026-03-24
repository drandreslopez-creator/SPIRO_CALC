from __future__ import annotations

# Módulos propios
from utils.calculations import *
from services.interpretation import build_interpretation
from services.spirometry_logic import ParameterResult
from services.pdf_generator import make_pdf, build_values_dataframe, build_summary_chart

# Librerías necesarias
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

import streamlit as st


# ----------------------------
# Configuración
# ----------------------------
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Espirometría | Dr. Andrés López Ruiz",
    page_icon="🫁",
    layout="wide"
)


# ----------------------------
# Utilidades
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

    parts = []
    if years > 0:
        parts.append(f"{years} año{'s' if years != 1 else ''}")
    if months > 0 or not parts:
        parts.append(f"{months} mes{'es' if months != 1 else ''}")
    return " y ".join(parts)


# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

    st.markdown("### Consultorio Dr. Andrés López Ruiz")
    st.caption("Médico Pediatra · Generador de reportes de espirometría")

    st.info(
        "La interpretación automática es una ayuda clínica. "
        "Debe correlacionarse con la evaluación médica."
    )


st.title("🫁 Reporte profesional de espirometría")


# ----------------------------
# FORMULARIO
# ----------------------------
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

    c_etnia, c_tabaco = st.columns(2)
    etnia = c_etnia.selectbox("Etnia", ["", "Mestizo", "Afrodescendiente", "Indígena", "Blanco"])
    fumador = c_tabaco.selectbox("Tabaquismo", ["", "No fumador", "Exfumador", "Fumador activo"])

    c7, c8, c9, c10 = st.columns(4)
    peso = c7.number_input("Peso (kg)", value=0.0)
    talla = c8.number_input("Talla (cm)", value=0.0)
    fecha_estudio = c9.date_input("Fecha estudio", value=date.today())
    id_tipo = c10.selectbox("Tipo doc", ["CC", "TI", "CE"])

    st.subheader("Valores espirométricos")

    param_config = [
        ("FVC", "L"),
        ("FEV1", "L"),
        ("FEV1/FVC", "%"),
    ]

    rows_data = {}

    for name, unit in param_config:
        col1, col2, col3 = st.columns(3)

        pre = col1.number_input(f"{name}_pre", key=f"{name}_pre")
        pred = col2.number_input(f"{name}_pred", key=f"{name}_pred")
        post = col3.number_input(f"{name}_post", key=f"{name}_post")

        rows_data[name] = {
            "unit": unit,
            "pre": pre,
            "pred": pred,
            "lln": None,
            "zpre": None,
            "post": post,
            "zpost": None,
        }

    # ---------------- ANEXOS ----------------
    st.subheader("Curvas")

    c1, c2 = st.columns(2)

    curve_image_1 = c1.file_uploader("Flujo-volumen", type=["png", "jpg"])
    curve_image_2 = c2.file_uploader("Volumen-tiempo", type=["png", "jpg"])

    # ---------------- COMENTARIO ----------------
    st.subheader("Comentario adicional")

    nota_medica_manual = st.text_area("Comentario médico")

    # ---------------- SUBMIT ----------------
    submitted = st.form_submit_button("Generar reporte")


# ----------------------------
# PROCESAMIENTO
# ----------------------------
if submitted:

    edad_num = age_in_years(fecha_nacimiento)
    edad_txt = age_text(fecha_nacimiento)

    params = {}
    for name, row in rows_data.items():
        params[name] = ParameterResult(
            name=name,
            unit=row["unit"],
            measured_pre=row["pre"],
            measured_post=row["post"],
            predicted=row["pred"],
            lln=None,
            zscore_pre=None,
            zscore_post=None,
        )

    interpretation = build_interpretation(
        edad_num,
        params,
        "Calidad adecuada",
        fumador=fumador
    )

    patient_dict = {
        "nombre": nombre,
        "edad": edad_txt,
        "sexo": sexo,
        "etnia": etnia,
        "fumador": fumador,
    }

    study_dict = {}

    attachments = {
        "curve_image_1": curve_image_1,
        "curve_image_2": curve_image_2,
    }

    pdf_bytes = make_pdf(patient_dict, study_dict, params, interpretation, attachments)

    st.success("PDF generado")

    st.download_button(
        "Descargar PDF",
        pdf_bytes,
        file_name="reporte.pdf"
    )