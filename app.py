
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Espirometría PRO v2.2", layout="centered")

st.title("Espirometría Clínica PRO v2.2")

st.header("Datos del paciente")
edad = st.number_input("Edad", 0, 120, 30)
sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
talla = st.number_input("Talla (cm)", 50, 220, 170)

st.header("Maniobras PRE")
fev1_1 = st.number_input("FEV1 Pre1 (L)", 0.0, 10.0, 0.0)
fev1_2 = st.number_input("FEV1 Pre2 (L)", 0.0, 10.0, 0.0)
fev1_3 = st.number_input("FEV1 Pre3 (L)", 0.0, 10.0, 0.0)

fvc_1 = st.number_input("FVC Pre1 (L)", 0.0, 10.0, 0.0)
fvc_2 = st.number_input("FVC Pre2 (L)", 0.0, 10.0, 0.0)
fvc_3 = st.number_input("FVC Pre3 (L)", 0.0, 10.0, 0.0)

fev1_vals = [v for v in [fev1_1, fev1_2, fev1_3] if v > 0]
fvc_vals = [v for v in [fvc_1, fvc_2, fvc_3] if v > 0]

fev1 = max(fev1_vals) if fev1_vals else 0
fvc = max(fvc_vals) if fvc_vals else 0
fev1_fvc = fev1 / fvc if fvc > 0 else 0

st.header("Valores %")
fev1_pct = st.number_input("FEV1 % predicho", 0, 150, 80)
fvc_pct = st.number_input("FVC % predicho", 0, 150, 90)
fef2575 = st.number_input("FEF25-75 %", 0, 150, 80)
delta_fev1_pct = st.number_input("Δ FEV1 % post broncodilatador", -50, 100, 0)

if edad < 18:
    grupo = "pediátrico"
    corte = 0.85
else:
    grupo = "adulto"
    corte = 0.70

if fev1_fvc < corte:
    patron = "obstructivo"
elif fvc_pct < 80:
    patron = "restrictivo"
else:
    patron = "normal"

if patron == "obstructivo":
    resultado = "Patrón ventilatorio obstructivo"
elif patron == "restrictivo":
    resultado = "Patrón ventilatorio restrictivo probable"
else:
    resultado = "Espirometría dentro de límites normales"

if patron == "obstructivo":
    if fev1_pct >= 80:
        severidad = "Leve"
    elif fev1_pct >= 50:
        severidad = "Moderado"
    elif fev1_pct >= 30:
        severidad = "Severo"
    else:
        severidad = "Muy severo"
else:
    severidad = "No aplica"

bronco = "Significativa" if delta_fev1_pct >= 12 else "No significativa"

comentario = ""
if patron == "obstructivo":
    comentario = "Disminución de FEV1/FVC compatible con patrón obstructivo. "
    if fef2575 < 60:
        comentario += "Compromiso de vías aéreas pequeñas. "
elif patron == "restrictivo":
    comentario = "Disminución de FVC con relación conservada, sugiere restricción. "
else:
    comentario = "Parámetros dentro de la normalidad. "

comentario += "Respuesta broncodilatadora significativa." if bronco == "Significativa" else "Sin respuesta broncodilatadora significativa."

explicacion = f"Interpretación basada en FEV1/FVC comparado con punto de corte para {grupo} ({corte})."

st.header("Resultado")
st.write("Resultado:", resultado)
st.write("Severidad:", severidad)
st.write("Broncodilatador:", bronco)
st.write("Comentario:", comentario)
st.write("Explicación clínica:", explicacion)

now = datetime.now(ZoneInfo("America/Bogota"))
st.caption(f"Fecha generación: {now.strftime('%d/%m/%Y %H:%M')}")
