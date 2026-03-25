from __future__ import annotations

# Módulos propios
from utils.calculations import *
from services.interpretation import build_interpretation
from services.spirometry_logic import ParameterResult  # 🔥 AQUÍ
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
# Función para calcular predichos y LLN
# ----------------------------
def calcular_predichos_lln(rows_data: dict, edad: Optional[float], sexo: str, talla: Optional[float], etnia: str) -> dict:

    if edad is None or sexo not in ["Femenino", "Masculino"] or talla is None:
        return rows_data

    rows_updated = {}

    for name, row in rows_data.items():

        pred = row.get("pred")
        lln = row.get("lln")

        # 🔥 GLI BIEN UBICADO
        gli = get_gli_reference(name, edad, talla, sexo, etnia)

        if pred is None:
            pred = gli["pred"]

        if lln is None:
            lln = gli["lln"]

        updated_row = row.copy()
        updated_row["pred"] = pred
        updated_row["lln"] = lln

        rows_updated[name] = updated_row

    return rows_updated


# ----------------------------
# Sidebar / static content
# ----------------------------
ensure_session_defaults()

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    st.markdown("### Consultorio Dr. Andrés López Ruiz")
    st.caption("Médico Pediatra · Generador de reportes de espirometría")
    st.markdown(
        "Este aplicativo crea un reporte imprimible en PDF con tabla de resultados, "
        "interpretación técnica, comentario médico y anexos opcionales."
    )
    st.info(
        "La interpretación automática es una ayuda clínica. Debe correlacionarse con la evaluación médica, "
        "la calidad de la maniobra y el contexto del paciente."
    )

st.title("🫁 Reporte profesional de espirometría")
st.write("Ingrese los datos del paciente, los parámetros espirométricos y los anexos opcionales del equipo.")


# ----------------------------
# Form fields
# ----------------------------
with st.form("spirometry_form"):
    st.subheader("Datos del paciente")

    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre completo")
    identificacion = c2.text_input("Documento")
    eps = c3.text_input("EPS")

    c4, c5, c6 = st.columns(3)

    fecha_nacimiento = c4.date_input(
        "Fecha de nacimiento",
        value=None,
        min_value=date(1900,1,1),
        max_value=date.today(),
        format="DD/MM/YYYY"
    )

    sexo = c5.selectbox("Sexo", ["", "Femenino", "Masculino", "Otro"])

    remitente = c6.text_input("Médico remitente")

    # 🔥 NUEVO BLOQUE BIEN INDENTADO
    c_etnia, c_tabaco = st.columns(2)

    etnia = c_etnia.selectbox(
        "Etnia",
        ["", "Mestizo", "Afrodescendiente", "Indígena", "Blanco", "Otro"]
    )

    fumador = c_tabaco.selectbox(
        "Tabaquismo",
        ["", "No fumador", "Exfumador", "Fumador activo"]
    )

    # 🔥 ESTO TAMBIÉN DEBE ESTAR DENTRO
    c7, c8, c9, c10 = st.columns(4)

    peso = c7.number_input("Peso (kg)", min_value=0.0, step=0.1, value=None, placeholder="Ej. 18.5")
    talla = c8.number_input("Talla (cm)", min_value=0.0, step=0.1, value=None, placeholder="Ej. 108")
    fecha_estudio = c9.date_input("Fecha del estudio", value=date.today(), min_value=date(1900,1,1), max_value=date.today(), format="DD/MM/YYYY")
    id_tipo = c10.selectbox("Tipo de documento", ["CC", "TI", "RC", "CE", "Pasaporte", "Otro"])

    st.subheader("Datos clínicos y técnicos")
    d1, d2 = st.columns(2)
    indicacion = d1.text_area("Indicación clínica", placeholder="Ej. Asma en seguimiento, tos crónica, sospecha de alteración funcional respiratoria")
    diagnostico = d2.text_area("IDx", placeholder="Ej. Asma persistente, rinitis y tos de esfuerzo")

    d3, d4, d5, d6 = st.columns(4)
    tipo_estudio = d3.selectbox("Tipo de estudio", ["Espirometría simple", "Espirometría pre y post broncodilatador"])
    calidad = d4.selectbox("Calidad / aceptabilidad", ["Aceptable", "Aceptable con limitaciones", "No aceptable"])
    reproducibilidad = d5.selectbox("Reproducibilidad", ["Adecuada", "Parcial", "No adecuada"])
    cooperacion = d6.selectbox("Cooperación del paciente", ["Buena", "Regular", "Limitada"])

    d7, d8 = st.columns(2)
    broncodilatador = d7.text_input("Broncodilatador", value="Salbutamol" if tipo_estudio == "Espirometría pre y post broncodilatador" else "")
    tiempo_post = d8.text_input("Tiempo post-BD", value="15 minutos" if tipo_estudio == "Espirometría pre y post broncodilatador" else "")

    st.subheader("Valores espirométricos")
    st.caption("Ingrese medición basal, predicho, LLN y Z-score si los tiene disponibles. Los campos post son opcionales.")

    param_config = [
        ("FVC", "L"),
        ("FEV1", "L"),
        ("FEV1/FVC", "%"),
        ("PEF", "L/s"),
        ("FEF25", "L/s"),
        ("FEF50", "L/s"),
        ("FEF75", "L/s"),
        ("FEF25-75", "L/s"),
    ]

    rows_data = {}
    header_cols = st.columns([1.8, 1.2, 1.2, 1.1, 1.0, 1.0, 1.2, 1.0])
    headers = ["Parámetro", "Pre", "Predicho", "% auto", "LLN", "Z Pre", "Post", "Z Post"]

    for col, head in zip(header_cols, headers):
        col.markdown(f"**{head}**")

    for name, unit in param_config:
        cols = st.columns([1.8, 1.2, 1.2, 1.1, 1.0, 1.0, 1.2, 1.0])

        cols[0].markdown(f"{name} ({unit})")

        measured_pre = cols[1].number_input(f"{name}_pre", label_visibility="collapsed", value=None, step=0.01)
        predicted = cols[2].number_input(f"{name}_pred", label_visibility="collapsed", value=None, step=0.01)

        pct_auto = None
        if measured_pre is not None and predicted not in (None, 0):
            pct_auto = (float(measured_pre) / float(predicted)) * 100

        cols[3].markdown(f"{fmt_num(pct_auto, 1)}")

        lln = cols[4].number_input(f"{name}_lln", label_visibility="collapsed", value=None, step=0.01)

        cols[5].markdown("Auto")

        post = cols[6].number_input(f"{name}_post", label_visibility="collapsed", value=None, step=0.01)

        cols[7].markdown("Auto")

        rows_data[name] = {
            "unit": unit,
            "pre": safe_float(measured_pre),
            "pred": safe_float(predicted),
            "lln": safe_float(lln),
            "zpre": None,
            "post": safe_float(post),
            "zpost": None,
        }

    st.subheader("Anexos del estudio")
    a1, a2, a3 = st.columns(3)
    curve_pdf = a1.file_uploader("PDF exportado del equipo (opcional)", type=["pdf"])
    curve_image_1 = a2.file_uploader("Imagen curva flujo-volumen (opcional)", type=["png", "jpg", "jpeg"])
    curve_image_2 = a3.file_uploader("Imagen curva volumen-tiempo (opcional)", type=["png", "jpg", "jpeg"])

    st.subheader("Comentario adicional")
    nota_medica_manual = st.text_area(
        "Comentario complementario del médico (opcional)",
        placeholder="Este texto se agregará al comentario médico automático si lo deseas.",
    )

    submitted = st.form_submit_button("Generar reporte e interpretación", use_container_width=True)

if submitted:
    edad_num = age_in_years(fecha_nacimiento) if isinstance(fecha_nacimiento, date) else None
    edad_txt = age_text(fecha_nacimiento) if isinstance(fecha_nacimiento, date) else ""

    # Calcular predichos
    rows_data = calcular_predichos_lln(rows_data, edad_num, sexo, talla, etnia)

    params = {}
    for name, row in rows_data.items():
        z_pre_auto = calculate_zscore(row["pre"], row["pred"], name)
        z_post_auto = calculate_zscore(row["post"], row["pred"], name)

        params[name] = ParameterResult(
            name=name,
            unit=row["unit"],
            measured_pre=row["pre"],
            measured_post=row["post"],
            predicted=row["pred"],
            lln=row["lln"],
            zscore_pre=z_pre_auto,
            zscore_post=z_post_auto,
        )

    quality_text = f"Calidad {calidad.lower()}, reproducibilidad {reproducibilidad.lower()} y cooperación {cooperacion.lower()}."

    interpretation = build_interpretation(
        edad_num,
        params,
        quality_text,
        fumador=fumador,
        calidad=calidad,
        reproducibilidad=reproducibilidad,
        cooperacion=cooperacion
    )

    # 🔥 GUARDAR PACIENTE (CORRECTO)
    patient_id = save_patient(
        nombre,
        identificacion,
        fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else "",
        sexo
    )

    save_spirometry(patient_id, interpretation, params)

    # 🔥 COMENTARIO MANUAL
    if nota_medica_manual.strip():
        interpretation["medical_comment"] += " " + nota_medica_manual.strip()

    # ---------------- DATOS ----------------
    patient_dict = {
        "nombre": nombre,
        "identificacion": f"{id_tipo} {identificacion}".strip(),
        "fecha_nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if isinstance(fecha_nacimiento, date) else "",
        "edad": edad_txt,
        "sexo": sexo,
        "etnia": etnia,
        "fumador": fumador,
        "eps": eps,
        "peso": f"{peso:.1f} kg" if peso is not None else "",
        "talla": f"{talla:.1f} cm" if talla is not None else "",
        "remitente": remitente,
    }

    study_dict = {
        "fecha_estudio": fecha_estudio.strftime("%d/%m/%Y") if isinstance(fecha_estudio, date) else "",
        "indicacion": indicacion,
        "diagnostico": diagnostico,
        "tipo_estudio": tipo_estudio,
        "calidad": calidad,
        "reproducibilidad": reproducibilidad,
        "cooperacion": cooperacion,
        "broncodilatador": broncodilatador,
        "tiempo_post": tiempo_post,
    }

    attachments = {
        "curve_pdf": curve_pdf,
        "curve_image_1": curve_image_1,
        "curve_image_2": curve_image_2,
    }

    # ---------------- GENERAR ----------------
    pdf_bytes = make_pdf(patient_dict, study_dict, params, interpretation, attachments)
    csv_bytes = build_values_dataframe(params).to_csv(index=False).encode("utf-8-sig")

    st.success("Reporte generado correctamente.")

    tab1, tab2, tab3 = st.tabs(["Reporte técnico", "Interpretación médica", "Datos tabulados"])

    with tab1:
        st.markdown("### Texto sugerido para el reporte")
        st.write(interpretation["technical_report"])
        st.write(f"**Resultado:** {interpretation['result']}")

        if curve_image_1:
            st.image(curve_image_1, caption="Curva flujo-volumen")
        if curve_image_2:
            st.image(curve_image_2, caption="Curva volumen-tiempo")

    with tab2:
        semaforo = interpretation.get("semaforo") or "⚠️ SIN CLASIFICAR"

        if "🟢" in semaforo:
            st.success(semaforo)
        elif "🟡" in semaforo:
            st.warning(semaforo)
        elif "🔴" in semaforo:
            st.error(semaforo)
        else:
            st.info(semaforo)

        st.markdown("### Lectura médica orientativa")
        st.write(f"**Patrón:** {interpretation['pattern']}")
        st.write(f"**Severidad:** {interpretation['severity']}")
        st.write(f"**Respuesta broncodilatadora:** {interpretation['bronchodilator']}")
        st.write(interpretation["medical_comment"])

    with tab3:
        df = build_values_dataframe(params)
        st.dataframe(df, use_container_width=True)

    dl1, dl2 = st.columns(2)

    dl1.download_button(
        "Descargar PDF del reporte",
        data=pdf_bytes,
        file_name=f"espirometria_{nombre.replace(' ', '_') if nombre else 'paciente'}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    dl2.download_button(
        "Descargar tabla CSV",
        data=csv_bytes,
        file_name=f"espirometria_{nombre.replace(' ', '_') if nombre else 'paciente'}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    chart_buffer = build_summary_chart(params)
    st.image(chart_buffer, caption="Resumen gráfico de % del predicho", use_container_width=True)

else:
    st.info("Completa el formulario y pulsa “Generar reporte e interpretación”.")

# ----------------------------
# 🧑‍⚕️ HISTORIAL DE PACIENTES
# ----------------------------

st.divider()
st.subheader("🧑‍⚕️ Historial de pacientes")

patients = get_all_patients()

if patients:
    opciones = {f"{p[1]} ({p[2]})": p[0] for p in patients}

    paciente_sel = st.selectbox("Seleccionar paciente", list(opciones.keys()))

    if paciente_sel:
        patient_id = opciones[paciente_sel]

        # ----------------------------
        # 📋 REPORTES
        # ----------------------------
        reports = get_patient_reports(patient_id)

        if reports:
            for r in reports:
                st.markdown("---")
                st.write(f"📅 Fecha: {r[0]}")
                st.write(f"🫁 Patrón: {r[1]}")
                st.write(f"📊 Severidad: {r[2]}")
                st.write(f"🚦 Semáforo: {r[3]}")
                st.write(f"🧾 Resultado: {r[4]}")
                st.write(f"💬 Comentario: {r[5]}")
        else:
            st.info("Este paciente no tiene estudios registrados.")

        # ----------------------------
        # 📈 EVOLUCIÓN DE FEV1
        # ----------------------------
        st.markdown("### 📈 Evolución de FEV1")

        try:
            evolucion = get_patient_evolution(patient_id)

            valores = [e[1] for e in evolucion if e[1] is not None]

            if len(valores) >= 2:
                st.line_chart(valores)

                if valores[-1] > valores[0]:
                    st.success("Mejoría funcional del FEV1 📈")
                elif valores[-1] < valores[0]:
                    st.error("Deterioro funcional del FEV1 📉")
                else:
                    st.info("Sin cambios significativos")
            else:
                st.info("Se requieren al menos 2 estudios válidos para evaluar evolución.")

        except Exception as e:
            st.error("Error al cargar evolución. Probablemente debes reiniciar la base de datos.")

else:
    st.info("No hay pacientes guardados aún.")