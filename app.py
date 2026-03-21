# app_v3_gli.py
# Espirometría PRO con Z-score GLI real

import streamlit as st
import numpy as np
from pyspirometry import spirometry

st.set_page_config(page_title="Espirometría PRO GLI", layout="centered")

st.title("Espirometría con Z-score (GLI REAL)")

# =========================
# DATOS PACIENTE
# =========================
st.header("Datos del paciente")

edad = st.number_input("Edad (años)", 1, 95, 30)
sexo = st.selectbox("Sexo", ["Male", "Female"])
talla = st.number_input("Talla (cm)", 50, 220, 170)
etnia = st.selectbox("Etnia", ["Caucasian", "African American", "Other"])

# =========================
# DATOS ESPIROMETRÍA
# =========================
st.header("Valores espirométricos")

fev1 = st.number_input("FEV1 (L)", value=2.5)
fvc = st.number_input("FVC (L)", value=3.5)

fev1_fvc = fev1 / fvc if fvc > 0 else 0

# =========================
# CALCULO GLI REAL
# =========================
try:
    result = spirometry(
        age=edad,
        height=talla,
        gender=sexo,
        ethnicity=etnia,
        fev1=fev1,
        fvc=fvc
    )

    z_fev1 = result["fev1_z"]
    z_fvc = result["fvc_z"]
    z_ratio = result["fev1_fvc_z"]

    lln_ratio = result["fev1_fvc_lln"]

except:
    st.error("Error calculando GLI. Revisa datos.")
    st.stop()

# =========================
# INTERPRETACIÓN ATS/ERS
# =========================
if z_ratio < -1.64:
    patron = "Obstructivo"
elif z_fvc < -1.64:
    patron = "Restrictivo probable"
else:
    patron = "Normal"

# =========================
# SEVERIDAD (FEV1 Z)
# =========================
if patron == "Obstructivo":
    if z_fev1 >= -1.64:
        severidad = "Leve"
    elif -3 <= z_fev1 < -1.64:
        severidad = "Moderado"
    elif -4 <= z_fev1 < -3:
        severidad = "Severo"
    else:
        severidad = "Muy severo"
else:
    severidad = "No aplica"

# =========================
# RESULTADOS
# =========================
st.header("Resultados")

st.write(f"Z-score FEV1: {z_fev1:.2f}")
st.write(f"Z-score FVC: {z_fvc:.2f}")
st.write(f"Z-score FEV1/FVC: {z_ratio:.2f}")

st.write(f"LLN FEV1/FVC: {lln_ratio:.2f}")

st.subheader("Interpretación")

st.success(f"Patrón: {patron}")
st.write(f"Severidad: {severidad}")

# =========================
# EXPLICACIÓN CLÍNICA PRO
# =========================
st.subheader("Explicación clínica")

if patron == "Obstructivo":
    st.write(
        f"La relación FEV1/FVC presenta un Z-score de {z_ratio:.2f}, por debajo del límite inferior normal (-1.64), "
        "lo que confirma limitación al flujo aéreo según criterios GLI/ATS. "
        f"La severidad se clasifica como {severidad} según el compromiso del FEV1."
    )

elif patron == "Restrictivo probable":
    st.write(
        f"La FVC presenta un Z-score de {z_fvc:.2f}, por debajo del límite inferior normal (-1.64), "
        "con relación FEV1/FVC conservada, lo que sugiere restricción pulmonar. "
        "Se recomienda confirmar con volúmenes pulmonares."
    )

else:
    st.write(
        "Todos los parámetros se encuentran dentro de los límites normales según ecuaciones GLI. "
        "No hay evidencia de alteración ventilatoria."
    )