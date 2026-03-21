# app_v2_2_zscore.py
# Versión con cálculo automático de Z-score (aproximación clínica)

import streamlit as st

st.set_page_config(page_title="Espirometría PRO", layout="centered")

st.title("Espirometría con Z-score automático (v2.2)")

# =========================
# DATOS PACIENTE
# =========================
st.header("Datos del paciente")

edad = st.number_input("Edad (años)", min_value=1, max_value=100, value=30)
sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
talla = st.number_input("Talla (cm)", min_value=50, max_value=220, value=170)

# =========================
# ESPIROMETRÍA
# =========================
st.header("Valores espirométricos")

fev1 = st.number_input("FEV1 (L)", value=2.5)
fvc = st.number_input("FVC (L)", value=3.5)

fev1_fvc = fev1 / fvc if fvc > 0 else 0

# =========================
# FUNCIONES PREDICHAS (APROX)
# =========================
def pred_fev1(edad, talla, sexo):
    base = 0.04 * talla - 0.03 * edad
    return base if sexo == "Masculino" else base * 0.9

def pred_fvc(edad, talla, sexo):
    base = 0.05 * talla - 0.02 * edad
    return base if sexo == "Masculino" else base * 0.9

def z_score(valor, predicho, sd):
    return (valor - predicho) / sd if sd != 0 else 0

# =========================
# CÁLCULOS
# =========================
fev1_pred = pred_fev1(edad, talla, sexo)
fvc_pred = pred_fvc(edad, talla, sexo)

sd_fev1 = fev1_pred * 0.15
sd_fvc = fvc_pred * 0.15

z_fev1 = z_score(fev1, fev1_pred, sd_fev1)
z_fvc = z_score(fvc, fvc_pred, sd_fvc)

# =========================
# INTERPRETACIÓN
# =========================
if edad < 18:
    corte = 0.85
else:
    corte = 0.70

if fev1_fvc < corte:
    patron = "Obstructivo"
elif z_fvc < -1.64:
    patron = "Restrictivo probable"
else:
    patron = "Normal"

# =========================
# RESULTADOS
# =========================
st.header("Resultados")

st.write(f"FEV1 predicho: {fev1_pred:.2f} L")
st.write(f"FVC predicho: {fvc_pred:.2f} L")

st.write(f"Z-score FEV1: {z_fev1:.2f}")
st.write(f"Z-score FVC: {z_fvc:.2f}")

st.write(f"Relación FEV1/FVC: {fev1_fvc:.2f}")

st.subheader("Interpretación")

st.success(f"Patrón: {patron}")

# =========================
# EXPLICACIÓN CLÍNICA
# =========================
st.subheader("Explicación clínica")

if patron == "Obstructivo":
    st.write(
        f"La relación FEV1/FVC ({fev1_fvc:.2f}) se encuentra por debajo del punto de corte ({corte}), "
        "lo que indica limitación al flujo aéreo compatible con patrón obstructivo."
    )

elif patron == "Restrictivo probable":
    st.write(
        f"La FVC presenta un Z-score de {z_fvc:.2f}, por debajo del límite inferior normal (-1.64), "
        "con relación FEV1/FVC conservada, lo que sugiere un patrón restrictivo probable."
    )

else:
    st.write(
        "Los parámetros espirométricos se encuentran dentro de los límites normales para el paciente."
    )
