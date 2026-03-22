from __future__ import annotations

import io
import math
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(page_title="Espirometría | Dr. Andrés López Ruiz", page_icon="🫁", layout="wide")


# ----------------------------
# UTILIDADES
# ----------------------------
def safe_float(v):
    try:
        return float(v)
    except:
        return None


def age_in_years(dob):
    if not dob:
        return None
    return round((date.today() - dob).days / 365.25, 2)


def age_text(dob):
    if not dob:
        return ""
    today = date.today()
    y = today.year - dob.year
    m = today.month - dob.month
    if today.day < dob.day:
        m -= 1
    if m < 0:
        y -= 1
        m += 12
    return f"{y} años {m} meses"


# ----------------------------
# FORMULARIO
# ----------------------------
with st.form("form"):
    st.subheader("Datos paciente")

    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre")
    identificacion = c2.text_input("Documento")
    eps = c3.text_input("EPS")

    c4, c5, c6 = st.columns(3)
    fecha_nacimiento = c4.date_input("Nacimiento", value=None)
    sexo = c5.selectbox("Sexo", ["", "Femenino", "Masculino"])
    remitente = c6.text_input("Remitente")

    # 🔥 FILA CORRECTA
    c7, c8, c9, c10 = st.columns(4)

    peso = c7.number_input("Peso", value=None)
    talla = c8.number_input("Talla", value=None)

    grupo_etnico = c9.selectbox(
        "Grupo étnico",
        ["", "Latino", "Caucásico", "Afrodescendiente", "Asiático", "Otro"]
    )

    fumador = c10.selectbox(
        "Tabaquismo",
        ["No", "Exfumador", "Sí"]
    )

    # 🔥 NUEVA FILA
    c11, c12 = st.columns(2)

    fecha_estudio = c11.date_input("Fecha estudio", value=date.today())
    id_tipo = c12.selectbox("Tipo doc", ["CC", "TI", "RC", "CE"])

    submitted = st.form_submit_button("Generar")


# ----------------------------
# PROCESAMIENTO
# ----------------------------
if submitted:

    edad_num = age_in_years(fecha_nacimiento)
    edad_txt = age_text(fecha_nacimiento)

    patient_dict = {
        "nombre": nombre,
        "identificacion": f"{id_tipo} {identificacion}",
        "fecha_nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if fecha_nacimiento else "",
        "edad": edad_txt,
        "sexo": sexo,
        "eps": eps,
        "peso": f"{peso} kg" if peso else "",
        "talla": f"{talla} cm" if talla else "",
        "remitente": remitente,
        "grupo_etnico": grupo_etnico,
        "fumador": fumador,
    }

    st.success("Datos cargados correctamente")

    st.write(patient_dict)