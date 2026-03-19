import streamlit as st
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from PIL import Image
import io

st.set_page_config(layout="wide")

# =========================
# FUNCIONES
# =========================

def calcular_edad(fecha_nac):
    hoy = date.today()
    años = hoy.year - fecha_nac.year
    meses = hoy.month - fecha_nac.month

    if hoy.day < fecha_nac.day:
        meses -= 1

    if meses < 0:
        años -= 1
        meses += 12

    return f"{años} años y {meses} meses"

def interpretar(fev1, fvc, relacion):
    if relacion >= 70 and fev1 >= 80:
        return "Espirometría dentro de límites normales", "No aplica"
    elif relacion < 70:
        if fev1 >= 80:
            return "Patrón ventilatorio obstructivo leve", "Leve"
        elif 50 <= fev1 < 80:
            return "Patrón ventilatorio obstructivo moderado", "Moderado"
        else:
            return "Patrón ventilatorio obstructivo severo", "Severo"
    elif fvc < 80:
        return "Patrón ventilatorio restrictivo probable", "No aplica"
    else:
        return "Patrón ventilatorio no concluyente", "No aplica"

def crear_pdf(datos, resultado, severidad, comentario, imagenes):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", size=10)

    # Encabezado
    pdf.cell(0, 5, "Consultorio Dr. Andrés López Ruiz", ln=True)
    pdf.cell(0, 5, "Médico Pediatra", ln=True)
    pdf.cell(0, 5, "Sogamoso, Boyacá", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "REPORTE DE ESPIROMETRÍA", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Arial", size=10)

    # Identificación
    pdf.cell(0, 6, f"Nombre: {datos['nombre']}", ln=True)
    pdf.cell(0, 6, f"Edad: {datos['edad']}", ln=True)
    pdf.cell(0, 6, f"IDx: {datos['idx']}", ln=True)
    pdf.ln(5)

    # Resultados
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Interpretación", ln=True)

    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, "Reporte técnico: Calidad aceptable, reproducibilidad adecuada y cooperación buena.")
    pdf.multi_cell(0, 6, f"Resultado: {resultado}")
    pdf.multi_cell(0, 6, f"Severidad: {severidad}")
    pdf.multi_cell(0, 6, f"Comentario médico: {comentario}")

    pdf.ln(5)

    # Gráficas
    if imagenes:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 6, "Resumen gráfico", ln=True)

        for img in imagenes:
            pdf.image(img, w=120)  # tamaño ajustado
            pdf.ln(5)

    # Pie
    pdf.ln(10)
    pdf.cell(0, 5, "Dr. Andrés López Ruiz", ln=True)
    pdf.cell(0, 5, "Médico Pediatra", ln=True)
    pdf.cell(0, 5, "RETHUS: 1082877373", ln=True)

    return pdf.output(dest='S').encode('latin1')

# =========================
# APP
# =========================

st.title("App Espirometría")

# Datos paciente
st.header("Datos del paciente")

col1, col2 = st.columns(2)

with col1:
    nombre = st.text_input("Nombre")
    fecha_nac = st.date_input("Fecha de nacimiento", value=date(2000,1,1))

with col2:
    edad = calcular_edad(fecha_nac)
    st.write(f"Edad: {edad}")
    idx = st.text_input("IDx")

# Datos espirometría
st.header("Valores")

col1, col2, col3 = st.columns(3)

with col1:
    fev1 = st.number_input("FEV1 (% predicho)", value=80.0)

with col2:
    fvc = st.number_input("FVC (% predicho)", value=80.0)

with col3:
    relacion = st.number_input("FEV1/FVC (%)", value=75.0)

# Interpretación
resultado, severidad = interpretar(fev1, fvc, relacion)

if resultado == "Espirometría dentro de límites normales":
    comentario = "No se identifican alteraciones obstructivas o restrictivas evidentes en los parámetros ingresados."
else:
    comentario = "Se evidencian alteraciones funcionales que requieren correlación clínica."

# Subida de imágenes
st.header("Adjuntar curvas")
imagenes = []
files = st.file_uploader("Subir imágenes", accept_multiple_files=True)

if files:
    for file in files:
        image = Image.open(file)
        st.image(image, width=300)
        path = f"/tmp/{file.name}"
        image.save(path)
        imagenes.append(path)

# Generar PDF
if st.button("Generar reporte"):
    datos = {
        "nombre": nombre,
        "edad": edad,
        "idx": idx
    }

    pdf_bytes = crear_pdf(datos, resultado, severidad, comentario, imagenes)

    st.download_button(
        label="Descargar PDF",
        data=pdf_bytes,
        file_name="reporte_espirometria.pdf",
        mime="application/pdf"
    )
