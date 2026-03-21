# ==========================================
# ESPIROMETRÍA PRO - BASE CORREGIDA
# Dr. Andrés López Ruiz
# ==========================================

from __future__ import annotations
import streamlit as st
from datetime import date, datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Espirometría PRO", layout="wide")

# ----------------------------
# HELPERS
# ----------------------------
def best_of_three(v1, v2, v3):
    vals = [v for v in [v1, v2, v3] if v not in (None, 0)]
    return max(vals) if vals else None

def calcular_edad(fn):
    if not fn:
        return ""
    hoy = date.today()
    años = hoy.year - fn.year
    meses = hoy.month - fn.month
    if hoy.day < fn.day:
        meses -= 1
    if meses < 0:
        años -= 1
        meses += 12
    return f"{años} años y {meses} meses"

# ----------------------------
# MOTOR CLÍNICO
# ----------------------------
def interpretar(edad, fev1, fvc, fev1_fvc, fev1_pct, fvc_pct, delta):

    corte = 0.85 if edad and edad < 18 else 0.70

    if fev1_fvc and fev1_fvc < corte:
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

    bronco = "Significativa" if delta >= 12 else "No significativa"

    if "obstructivo" in patron:
        comentario = "Relación FEV1/FVC disminuida compatible con obstrucción."
    elif "restrictivo" in patron:
        comentario = "FVC disminuida con relación conservada, sugiere restricción."
    else:
        comentario = "Parámetros dentro de límites normales."

    if bronco == "Significativa":
        comentario += " Respuesta broncodilatadora significativa."
    else:
        comentario += " Sin respuesta broncodilatadora significativa."

    return patron, severidad, bronco, comentario

# ----------------------------
# UI
# ----------------------------
st.title("🫁 Espirometría Profesional")

# DATOS PACIENTE
st.subheader("Datos del paciente")
c1, c2, c3 = st.columns(3)
nombre = c1.text_input("Nombre")
documento = c2.text_input("Documento")
sexo = c3.selectbox("Sexo", ["", "Femenino", "Masculino"])

c4, c5 = st.columns(2)
fecha_nacimiento = c4.date_input("Fecha nacimiento", value=None, format="DD/MM/YYYY")
edad_txt = calcular_edad(fecha_nacimiento)
edad_num = (date.today() - fecha_nacimiento).days / 365.25 if fecha_nacimiento else None
c5.text_input("Edad", edad_txt, disabled=True)

# ----------------------------
# ESPIROMETRÍA
# ----------------------------
st.subheader("FEV1 (PRE)")
f1, f2, f3 = st.columns(3)
fev1_1 = f1.number_input("PRE1", value=0.0)
fev1_2 = f2.number_input("PRE2", value=0.0)
fev1_3 = f3.number_input("PRE3", value=0.0)

st.subheader("FVC (PRE)")
c1, c2, c3 = st.columns(3)
fvc_1 = c1.number_input("PRE1 ", value=0.0)
fvc_2 = c2.number_input("PRE2 ", value=0.0)
fvc_3 = c3.number_input("PRE3 ", value=0.0)

fev1 = best_of_three(fev1_1, fev1_2, fev1_3)
fvc = best_of_three(fvc_1, fvc_2, fvc_3)

fev1_fvc = (fev1 / fvc) if fvc else 0

# ----------------------------
# VALORES %
# ----------------------------
st.subheader("Valores porcentuales")
c1, c2, c3 = st.columns(3)
fev1_pct = c1.number_input("FEV1 % predicho", 0, 150, 80)
fvc_pct = c2.number_input("FVC % predicho", 0, 150, 90)
delta = c3.number_input("Δ FEV1 post (%)", 0, 100, 0)

# ----------------------------
# RESULTADO
# ----------------------------
if st.button("Generar interpretación"):

    patron, severidad, bronco, comentario = interpretar(
        edad_num, fev1, fvc, fev1_fvc, fev1_pct, fvc_pct, delta
    )

    st.success("Resultado generado")

    st.markdown(f"**Resultado:** {patron}")
    st.markdown(f"**Severidad:** {severidad}")
    st.markdown(f"**Respuesta broncodilatadora:** {bronco}")
    st.markdown(f"**Comentario médico:** {comentario}")

    now = datetime.now(ZoneInfo("America/Bogota"))
    st.caption("Fecha: " + now.strftime("%d/%m/%Y %H:%M"))
