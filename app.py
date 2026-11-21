from __future__ import annotations

# Módulos propios
from utils.calculations import fmt_num, safe_float
from services.interpretation import build_interpretation
from services.study_guard import (
    SIMPLE_STUDY, POST_STUDY, has_post_phase, conflicting_study_dates,
    reference_provenance, scoped_rows,
)
from services.spirometry_logic import parameters_from_entered_values
from services.pdf_generator import make_pdf, build_values_dataframe, build_summary_chart

from services.report_review import (MAX_CLINICAL_COMMENT, reviewed_interpretation,
                                    suggest_clinical_comment)

from datetime import date
from pathlib import Path
from typing import Optional

import streamlit as st

# Configuración
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "logo.png"

st.set_page_config(
    page_title="Espirometría | Dr. Andrés López Ruiz",
    page_icon="🫁",
    layout="wide"
)

# ----------------------------
# Utility helpers
# ----------------------------
def age_in_years(dob: Optional[date], study_date: Optional[date]) -> Optional[int]:
    if not dob or not study_date or dob > study_date:
        return None
    return study_date.year - dob.year - ((study_date.month, study_date.day) < (dob.month, dob.day))


def age_text(dob: Optional[date], study_date: Optional[date]) -> str:
    if not dob or not study_date or dob > study_date:
        return ""
    today = study_date
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
st.warning("Versión de prueba. Usa solo datos ficticios; no emitas informes clínicos con esta versión.")
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
    tipo_estudio = d3.selectbox("Tipo de estudio", [SIMPLE_STUDY, POST_STUDY])
    calidad = d4.selectbox("Calidad / aceptabilidad", ["Sin verificar", "Aceptable", "Aceptable con limitaciones", "No aceptable"])
    reproducibilidad = d5.selectbox("Reproducibilidad", ["Sin verificar", "Adecuada", "Parcial", "No adecuada"])
    cooperacion = d6.selectbox("Cooperación del paciente", ["Sin verificar", "Buena", "Regular", "Limitada"])

    d7, d8 = st.columns(2)
    broncodilatador = d7.text_input("Broncodilatador", value="Salbutamol" if has_post_phase(tipo_estudio) else "")
    tiempo_post = d8.text_input("Tiempo post-BD", value="15 minutos" if has_post_phase(tipo_estudio) else "")

    ref1, ref2 = st.columns(2)
    ecuacion_referencia = ref1.text_input(
        "Ecuación o familia de referencia", max_chars=60, placeholder="Ej.: GLI",
        help="Transcriba la ecuación del informe validado del equipo; no la infiera.",
    )
    version_referencia = ref2.text_input(
        "Versión o año de la ecuación", max_chars=30, placeholder="Ej.: 2012",
        help="Use la identificación que aparece en el informe del equipo.",
    )
    referencia_verificada = st.checkbox("Confirmo que los valores de referencia ingresados provienen de un informe validado, con las mismas unidades.")
    calidad_post_confirmada = st.checkbox("Confirmo la calidad y reproducibilidad de las maniobras posbroncodilatador (si aplica).")

    identificador_equipo = st.text_input("Identificación del espirómetro (opcional)",
                                        placeholder="Modelo o código de inventario del equipo realmente usado",
                                        max_chars=100)

    st.subheader("Valores espirométricos")
    st.caption("Transcriba predicho, límite inferior de normalidad (LLN) y Z del informe validado del equipo. No se estiman valores faltantes. Ingrese la relación FEV1/FVC y su LLN como porcentajes (ej.: 78, no 0.78).")

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

        measured_pre = cols[1].number_input(f"{name}_pre", label_visibility="collapsed", value=None, step=0.0001, format="%.4f")
        predicted = cols[2].number_input(f"{name}_pred", label_visibility="collapsed", value=None, step=0.0001, format="%.4f")

        pct_auto = None
        if measured_pre is not None and predicted not in (None, 0):
            pct_auto = (float(measured_pre) / float(predicted)) * 100

        cols[3].markdown(f"{fmt_num(pct_auto, 1)}")

        lln = cols[4].number_input(f"{name}_lln", label_visibility="collapsed", value=None, step=0.0001, format="%.4f")

        zpre = cols[5].number_input(f"{name}_zpre", label_visibility="collapsed", value=None, step=0.01, format="%.3f")

        post = cols[6].number_input(f"{name}_post", label_visibility="collapsed", value=None, step=0.0001, format="%.4f")

        zpost = cols[7].number_input(f"{name}_zpost", label_visibility="collapsed", value=None, step=0.01, format="%.3f")

        rows_data[name] = {
            "unit": unit,
            "pre": safe_float(measured_pre),
            "pred": safe_float(predicted),
            "lln": safe_float(lln),
            "zpre": safe_float(zpre),
            "post": safe_float(post),
            "zpost": safe_float(zpost),
        }

    st.caption("Para un estudio simple, se omiten las mediciones y confirmaciones posbroncodilatador.")
    st.subheader("Anexos del estudio")
    a1, a2, a3 = st.columns(3)
    curve_pdf = a1.file_uploader("PDF exportado del equipo (opcional)", type=["pdf"])
    curve_image_1 = a2.file_uploader("Imagen curva flujo-volumen (opcional)", type=["png", "jpg", "jpeg"])
    curve_image_2 = a3.file_uploader("Imagen curva volumen-tiempo (opcional)", type=["png", "jpg", "jpeg"])

    anexos_solo_basales = st.checkbox(
        "Para un estudio simple, confirmo que los anexos contienen solo información basal."
    )

    submitted = st.form_submit_button("Preparar borrador para revisión", use_container_width=True)

if submitted:
    # Every attempt (including an invalid one) invalidates the previous export.
    st.session_state.pop("report_snapshot", None)
    st.session_state.pop("report_export", None)
    st.session_state.pop("edited_conclusion", None)
    st.session_state["report_revision"] = st.session_state.get("report_revision", 0) + 1
    if conflicting_study_dates(fecha_nacimiento, fecha_estudio):
        st.error("La fecha de nacimiento es posterior a la fecha del estudio. Corrige las fechas antes de generar o guardar el informe.")
        st.stop()

    include_post = has_post_phase(tipo_estudio)
    provenance = reference_provenance(ecuacion_referencia, version_referencia)
    if not provenance:
        st.warning("Indica la ecuación y su versión o año para habilitar la interpretación automática. El informe puede mostrar los datos sin clasificarlos.")
    if not include_post and (calidad_post_confirmada or broncodilatador or tiempo_post
                             or any(row.get("post") is not None or row.get("zpost") is not None
                                    for row in rows_data.values())):
        st.warning("El estudio es simple: se omitieron los datos posbroncodilatador ingresados.")
    edad_num = age_in_years(fecha_nacimiento, fecha_estudio) if isinstance(fecha_nacimiento, date) else None
    edad_txt = age_text(fecha_nacimiento, fecha_estudio) if isinstance(fecha_nacimiento, date) else ""

    params = parameters_from_entered_values(scoped_rows(rows_data, include_post))

    quality_text = f"Calidad {calidad.lower()}, reproducibilidad {reproducibilidad.lower()} y cooperación {cooperacion.lower()}."

    interpretation = build_interpretation(
        edad_num,
        params,
        quality_text,
        fumador=fumador,
        calidad=calidad,
        reproducibilidad=reproducibilidad,
        cooperacion=cooperacion,
        referencia_verificada=referencia_verificada and provenance is not None,
        calidad_post_confirmada=include_post and calidad_post_confirmada,
    )

    if not include_post:
        interpretation["bronchodilator"] = "No aplica (estudio simple)"
        interpretation["technical_report"] = quality_text

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
        "referencia": provenance or "No informada",
        "referencia_verificada": bool(referencia_verificada and provenance is not None),
        "include_post": include_post,
        "identificador_equipo": identificador_equipo.strip(),
        "broncodilatador": broncodilatador if include_post else "",
        "tiempo_post": tiempo_post if include_post else "",
    }

    if not include_post and not anexos_solo_basales and (curve_pdf or curve_image_1 or curve_image_2):
        st.warning("Se omitieron los anexos del estudio simple porque no confirmaste que sean exclusivamente basales.")
        curve_pdf = curve_image_1 = curve_image_2 = None

    attachments = {
        "curve_pdf": curve_pdf,
        "curve_image_1": curve_image_1,
        "curve_image_2": curve_image_2,
    }

    st.session_state["report_snapshot"] = (patient_dict, study_dict, params, interpretation, attachments)

snapshot = st.session_state.get("report_snapshot")
if snapshot is None:
    st.info("Completa el formulario y pulsa «Preparar borrador para revisión».")
else:
    patient_dict, study_dict, params, interpretation, attachments = snapshot
    include_post = study_dict["include_post"]
    revision = st.session_state["report_revision"]
    st.subheader("Revisión del borrador")
    st.text(f"{patient_dict['nombre'] or 'Sin nombre'} | {patient_dict['identificacion']} | "
            f"Estudio: {study_dict['fecha_estudio']}")
    st.caption("Si cambias datos arriba, vuelve a preparar el borrador. Esta revisión corresponde "
               "únicamente al estudio mostrado aquí.")
    st.text(f"Referencia: {study_dict['referencia']} · "
            f"{'Confirmada por el operador' if study_dict['referencia_verificada'] else 'No confirmada'}")

    tab1, tab2, tab3 = st.tabs(["Reporte técnico", "Hallazgos calculados", "Datos tabulados"])
    with tab1:
        st.write(interpretation["technical_report"])
        for key, caption in (("curve_image_1", "Curva flujo-volumen"),
                             ("curve_image_2", "Curva volumen-tiempo")):
            if attachments[key]:
                st.image(attachments[key], caption=caption)
        if attachments["curve_pdf"]:
            st.text(f"PDF del equipo que se anexará: {attachments['curve_pdf'].name}")
    with tab2:
        st.write(f"**Patrón:** {interpretation['pattern']}")
        if include_post:
            st.write(f"**Respuesta broncodilatadora:** {interpretation['bronchodilator']}")
        st.write(interpretation["medical_comment"])
    df = build_values_dataframe(params, include_post=include_post)
    with tab3:
        st.dataframe(
            df, use_container_width=True,
            column_config={
                label: st.column_config.NumberColumn(format=fmt)
                for label, fmt in {
                    "Pre": "%.4f", "Predicho": "%.4f", "LLN": "%.4f",
                    "Post": "%.4f", "Δ Abs": "%.4f",
                    "Z Pre": "%.3f", "Z Post": "%.3f",
                    "%Pred Pre": "%.1f", "%Pred Post": "%.1f",
                }.items()
                if label in df.columns
            },
        )
        st.image(build_summary_chart(params, include_post=include_post),
                 caption="Resumen gráfico de % del predicho", use_container_width=True)

    if "report_export" not in st.session_state:
        with st.form(f"review_{revision}"):
            clinical_comment = st.text_area(
                "Conclusión clínica editable", value=st.session_state.get("edited_conclusion", suggest_clinical_comment(interpretation)),
                max_chars=MAX_CLINICAL_COMMENT, key=f"conclusion_{revision}",
                help="Borrador local, generado sin IA externa. Revisa y edita la conclusión.",
            )
            confirmed = st.checkbox(
                "He revisado la identidad, los valores y anexos del estudio, y la conclusión.",
                key=f"confirm_{revision}",
            )
            export_requested = st.form_submit_button("Confirmar revisión y preparar PDF de prueba")
        if export_requested:
            try:
                reviewed = reviewed_interpretation(interpretation, clinical_comment, confirmed)
                if not patient_dict["nombre"].strip():
                    raise ValueError("Identifica al paciente de prueba antes de generar el PDF.")
                pdf_bytes = make_pdf(patient_dict, study_dict, params, reviewed, attachments)
                st.session_state["report_export"] = (pdf_bytes, reviewed["reviewed_clinical_comment"])
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("No se pudo generar el PDF. Verifica los datos y los anexos y vuelve a intentarlo.")
    else:
        pdf_bytes, conclusion = st.session_state["report_export"]
        st.success("PDF de prueba generado después de la revisión.")
        st.text(conclusion)
        if st.button("Volver a editar la conclusión"):
            st.session_state["edited_conclusion"] = conclusion
            del st.session_state["report_export"]
            st.rerun()

        st.download_button("Descargar PDF de prueba", data=pdf_bytes,
                           file_name="espirometria_prueba.pdf", mime="application/pdf")
        st.download_button("Descargar tabla CSV de prueba", data=df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="espirometria_prueba.csv", mime="text/csv")
