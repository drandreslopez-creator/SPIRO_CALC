# app_v3_0_GLI_ready.py
# Versión avanzada con estructura tipo GLI (Z-score clínico)

import streamlit as st

st.set_page_config(page_title="Espirometría PRO GLI", layout="centered")

st.title("Espirometría PRO – Nivel GLI (v3.0)")

# =========================
# DATOS PACIENTE
# =========================
st.header("Datos del paciente")

edad = st.number_input("Edad (años)", min_value=3, max_value=100, value=30)
sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
talla = st.number_input("Talla (cm)", min_value=80, max_value=220, value=170)

# =========================
# VALORES ESPIROMETRÍA
# =========================
st.header("Valores espirométricos")

fev1 = st.number_input("FEV1 (L)", value=2.5)
fvc = st.number_input("FVC (L)", value=3.5)

fev1_fvc = fev1 / fvc if fvc > 0 else 0

# =========================
# FUNCIONES TIPO GLI (APROXIMACIÓN)
# =========================
def pred_fev1(edad, talla, sexo):
    base = (0.04 * talla) - (0.025 * edad)
    return base if sexo == "Masculino" else base * 0.92

def pred_fvc(edad, talla, sexo):
    base = (0.05 * talla) - (0.02 * edad)
    return base if sexo == "Masculino" else base * 0.92

def sd(valor_pred):
    return valor_pred * 0.12

def z_score(valor, pred, sd):
    return (valor - pred) / sd if sd != 0 else 0

# =========================
# CÁLCULOS
# =========================
fev1_pred = pred_fev1(edad, talla, sexo)
fvc_pred = pred_fvc(edad, talla, sexo)

z_fev1 = z_score(fev1, fev1_pred, sd(fev1_pred))
z_fvc = z_score(fvc, fvc_pred, sd(fvc_pred))

# =========================
# INTERPRETACIÓN CLÍNICA
# =========================
if edad < 18:
    corte = 0.85
else:
    corte = 0.70

if fev1_fvc < corte:
    patron = "Patrón ventilatorio obstructivo"
elif z_fvc < -1.64:
    patron = "Patrón ventilatorio restrictivo probable"
else:
    patron = "Espirometría dentro de límites normales"

# =========================
# SEVERIDAD POR Z-SCORE
# =========================
if z_fev1 >= -1.64:
    severidad = "Normal"
elif -2.5 < z_fev1 < -1.64:
    severidad = "Leve"
elif -4 < z_fev1 <= -2.5:
    severidad = "Moderado"
else:
    severidad = "Severo"

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

st.success(patron)
st.info(f"Severidad funcional: {severidad}")

# =========================
# EXPLICACIÓN CLÍNICA
# =========================
st.subheader("Explicación clínica")

if "obstructivo" in patron:
    st.write(
        f"La relación FEV1/FVC ({fev1_fvc:.2f}) se encuentra por debajo del punto de corte esperado ({corte}), "
        "lo que indica limitación al flujo aéreo compatible con patrón obstructivo."
    )

elif "restrictivo" in patron:
    st.write(
        f"La FVC presenta un Z-score de {z_fvc:.2f}, inferior al límite inferior de normalidad (-1.64), "
        "con relación FEV1/FVC conservada, lo que sugiere un patrón restrictivo."
    )

else:
    st.write(
        "Los parámetros espirométricos se encuentran dentro de los valores normales para la edad, talla y sexo del paciente."
    )