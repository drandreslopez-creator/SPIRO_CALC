# ===============================
# ESPIROMETRÍA PRO - VERSIÓN FINAL LIMPIA
# ===============================

from __future__ import annotations
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Espirometría PRO", layout="wide")

# ===============================
# FUNCIONES
# ===============================
def best_of_three(a, b, c):
    vals = [v for v in [a, b, c] if v not in (None, 0)]
    return max(vals) if vals else None

def interpretar(edad, fev1, fvc, fev1_fvc, fev1_pct, fvc_pct, delta):
    
    # Corte dinámico
    corte = 0.85 if edad < 18 else 0.70

    # Patrón (SIN MIXTO)
    if fev1_fvc < corte:
        patron = "Patrón ventilatorio obstructivo"
        
        if fev1_pct >= 80:
            severidad = "Leve"
        elif fev1_pct >= 50:
            severidad = "Moderado"
        elif fev1_pct >= 30:
            severidad = "Severo"
        else:
            severidad = "Muy severo"

    elif fvc_pct < 80:
        patron = "Patrón ventilatorio restrictivo probable"
        severidad = "Moderado"

    else:
        patron = "Espirometría dentro de límites normales"
        severidad = "No aplica"

    # Broncodilatador
    bronco = "Significativa" if delta >= 12 else "No significativa"

    # Comentario clínico
    if "obstructivo" in patron:
        comentario = "Disminución de la relación FEV1/FVC compatible con patrón obstructivo."
    elif "restrictivo" in patron:
        comentario = "Disminución de la FVC con relación conservada, sugiere restricción."
    else:
        comentario = "Parámetros dentro de límites normales."

    if bronco == "Significativa":
        comentario += " Se evidencia respuesta broncodilatadora significativa."
    else:
        comentario += " No se evidencia respuesta broncodilatadora significativa."

    return patron, severidad, bronco, comentario

# ===============================
# INTERFAZ
# ===============================
st.title("🫁 Espirometría Clínica PRO")

edad = st.number_input("Edad", 0, 100, 30)

# ===============================
# FEV1
# ===============================
st.subheader("FEV1 (PRE)")
fev1_1 = st.number_input("FEV1 PRE1", 0.0)
fev1_2 = st.number_input("FEV1 PRE2", 0.0)
fev1_3 = st.number_input("FEV1 PRE3", 0.0)

# ===============================
# FVC
# ===============================
st.subheader("FVC (PRE)")
fvc_1 = st.number_input("FVC PRE1", 0.0)
fvc_2 = st.number_input("FVC PRE2", 0.0)
fvc_3 = st.number_input("FVC PRE3", 0.0)

# BEST automático
fev1 = best_of_three(fev1_1, fev1_2, fev1_3)
fvc = best_of_three(fvc_1, fvc_2, fvc_3)

fev1_fvc = fev1 / fvc if fvc else 0

# ===============================
# VALORES %
# ===============================
st.subheader("Valores porcentuales")

fev1_pct = st.number_input("FEV1 % predicho", 0, 150, 80)
fvc_pct = st.number_input("FVC % predicho", 0, 150, 90)
delta = st.number_input("Δ FEV1 % post broncodilatador", 0, 100, 0)

# ===============================
# RESULTADO
# ===============================
if st.button("Generar interpretación"):

    patron, severidad, bronco, comentario = interpretar(
        edad, fev1, fvc, fev1_fvc, fev1_pct, fvc_pct, delta
    )

    st.success("Resultado generado")

    st.write("**Resultado:**", patron)
    st.write("**Severidad:**", severidad)
    st.write("**Respuesta broncodilatadora:**", bronco)
    st.write("**Comentario clínico:**", comentario)

    # Fecha correcta Colombia
    now = datetime.now(ZoneInfo("America/Bogota"))
    st.caption("Fecha: " + now.strftime("%d/%m/%Y %H:%M"))
