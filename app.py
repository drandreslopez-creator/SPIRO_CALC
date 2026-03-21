from __future__ import annotations

import io
import math
import tempfile
import zipfile
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
from reportlab.lib.utils import ImageReader
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
# Utility helpers
# ----------------------------
def fmt_num(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
    if value is None or value == "":
        return "—"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(value):
        return "—"
    return f"{value:.{digits}f}{suffix}"


def safe_float(value) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


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

def estimate_sd(predicted: float, param_name: str) -> Optional[float]:
    """
    Estima desviación estándar basada en coeficiente de variación (CV)
    Valores aproximados basados en literatura espirométrica.
    """
    if predicted is None:
        return None

    cv_map = {
        "FEV1": 0.15,
        "FVC": 0.15,
        "FEV1/FVC": 0.08,
        "FEF25-75": 0.25,
        "PEF": 0.20,
    }

    cv = cv_map.get(param_name, 0.20)
    return predicted * cv

def calculate_zscore(measured: Optional[float], predicted: Optional[float], param_name: str) -> Optional[float]:
    if measured is None or predicted is None:
        return None

    sd = estimate_sd(predicted, param_name)
    if sd in (None, 0):
        return None

    return (measured - predicted) / sd

# ----------------------------
# Función para calcular predichos y LLN
# ----------------------------
def calcular_predichos_lln(parametros: Dict[str, dict], edad: Optional[float], sexo: str, altura: Optional[float]) -> Dict[str, dict]:
    """
    Calcula valores predichos y LLN según edad, sexo y altura.
    Retorna un diccionario con 'pred' y 'lln' para cada parámetro.
    """
    resultados = {}
    if altura is None or edad is None or sexo not in ("Femenino", "Masculino"):
        return parametros  # Si no hay datos, devuelve los ingresados

    for nombre, datos in parametros.items():
        h = altura / 100  # convertir cm a m si se requiere
        e = edad
        s = 1 if sexo == "Masculino" else 0

        # Fórmulas simples de predicho aproximadas (puedes ajustar según GLI)
        if nombre == "FVC":
            pred = 3.5 * h - 0.03 * e + 0.2 * s
        elif nombre == "FEV1":
            pred = 2.8 * h - 0.025 * e + 0.15 * s
        elif nombre == "FEV1/FVC":
            pred = 0.8 - 0.002 * e
        elif nombre == "PEF":
            pred = 8.0 * h - 0.1 * e
        elif nombre == "FEF25-75":
            pred = 3.0 * h - 0.03 * e
        else:
            pred = datos.get("pre")  # mantener lo que el usuario ingrese

        # LLN aproximado = predicho - 1.64*SD
        sd = estimate_sd(pred, nombre) or 0
        lln = pred - 1.64 * sd

        resultados[nombre] = {
            **datos,
            "pred": pred,
            "lln": lln,
        }
    return resultados


# ----------------------------
# Clinical engine
# ----------------------------
@dataclass
class ParameterResult:
    name: str
    unit: str
    measured_pre: Optional[float]
    measured_post: Optional[float]
    predicted: Optional[float]
    lln: Optional[float]
    zscore_pre: Optional[float]
    zscore_post: Optional[float]

    @property
    def pct_pred_pre(self) -> Optional[float]:
        if self.measured_pre is None or self.predicted in (None, 0):
            return None
        return (self.measured_pre / self.predicted) * 100

    @property
    def pct_pred_post(self) -> Optional[float]:
        if self.measured_post is None or self.predicted in (None, 0):
            return None
        return (self.measured_post / self.predicted) * 100

    @property
    def delta_abs(self) -> Optional[float]:
        if self.measured_pre is None or self.measured_post is None:
            return None
        return self.measured_post - self.measured_pre

    @property
    def delta_pct_baseline(self) -> Optional[float]:
        if self.measured_pre in (None, 0) or self.measured_post is None:
            return None
        return ((self.measured_post - self.measured_pre) / self.measured_pre) * 100


def lower_limit_ratio(age_years: Optional[float]) -> float:
    if age_years is None:
        return 0.75
    if age_years < 18:
        return 0.85
    if age_years < 40:
        return 0.75
    return 0.70


def is_below_lln(value: Optional[float], lln: Optional[float], fallback: Optional[float] = None) -> bool:
    if value is None:
        return False
    if lln is not None:
        return value < lln
    if fallback is not None:
        return value < fallback
    return False


def severity_from_percent(pct: Optional[float]) -> str:
    if pct is None:
        return "No clasificable"
    if pct >= 80:
        return "Leve"
    if 60 <= pct < 80:
        return "Moderado"
    if 40 <= pct < 60:
        return "Severo"
    return "Muy severo"


def bronchodilator_response(fev1: ParameterResult, fvc: ParameterResult, age_years: Optional[float]) -> Tuple[str, str]:
    notes: List[str] = []

    def eval_param(param: ParameterResult, label: str) -> Tuple[bool, Optional[float], Optional[float]]:
        delta_abs = param.delta_abs
        delta_pct = param.delta_pct_baseline
        if delta_abs is None or delta_pct is None:
            return False, delta_abs, delta_pct
        delta_abs_ml = delta_abs * 1000 if param.unit.lower() == "l" else delta_abs
        classic = delta_pct >= 12 and delta_abs_ml >= 200
        pediatric_support = age_years is not None and age_years < 18 and delta_pct >= 12
        positive = classic or pediatric_support
        if positive:
            if classic:
                notes.append(f"Respuesta significativa en {label} (Δ {delta_pct:.1f}% y {delta_abs_ml:.0f} mL).")
            else:
                notes.append(f"Respuesta sugestiva en {label} para contexto pediátrico (Δ {delta_pct:.1f}%).")
        return positive, delta_abs_ml, delta_pct

    pos_fev1, _, _ = eval_param(fev1, "FEV1")
    pos_fvc, _, _ = eval_param(fvc, "FVC")

    if pos_fev1 or pos_fvc:
        return "Significativa", " ".join(notes)
    return "No significativa", "Sin cambios relevantes tras broncodilatador según los criterios automáticos configurados."


def build_interpretation(age_years: Optional[float], params: Dict[str, ParameterResult], quality_text: str) -> Dict[str, str]:
    fev1 = params["FEV1"]
    fvc = params["FVC"]
    ratio = params["FEV1/FVC"]
    fef2575 = params.get("FEF25-75")

    ratio_cutoff = lower_limit_ratio(age_years)
    ratio_low = is_below_lln(ratio.measured_pre, ratio.lln, ratio_cutoff)
    fvc_low = is_below_lln(fvc.measured_pre, fvc.lln) or ((fvc.pct_pred_pre or 999) < 80)
    fev1_low = is_below_lln(fev1.measured_pre, fev1.lln) or ((fev1.pct_pred_pre or 999) < 80)

    pattern = "Espirometría dentro de límites normales"
    severity = "No aplica"
    comments: List[str] = []

    if ratio_low and not fvc_low:
        pattern = "Patrón ventilatorio obstructivo"
        severity = severity_from_percent(fev1.pct_pred_pre)
        comments.append("Relación FEV1/FVC disminuida, compatible con obstrucción al flujo aéreo.")
    elif not ratio_low and fvc_low:
        pattern = "Patrón restrictivo probable"
        severity = severity_from_percent(fvc.pct_pred_pre)
        comments.append("FVC disminuida con relación FEV1/FVC conservada; considerar correlación clínica y, si aplica, confirmación con volúmenes pulmonares.")
    elif ratio_low and fvc_low:
        pattern = "Patrón ventilatorio mixto"
        severity = severity_from_percent(min(filter(lambda x: x is not None, [fev1.pct_pred_pre, fvc.pct_pred_pre]), default=None))
        comments.append("Relación FEV1/FVC y FVC disminuidas, compatible con patrón mixto.")
    else:
        comments.append("No se identifican alteraciones obstructivas o restrictivas evidentes en los parámetros ingresados.")

    if fef2575 and fef2575.pct_pred_pre is not None and fef2575.pct_pred_pre < 65:
        comments.append("Flujos de vías aéreas medias disminuidos (FEF25-75 reducido).")

    broncho_status = "No realizado"
    broncho_note = "No se ingresaron valores post broncodilatador."
    if fev1.measured_post is not None or fvc.measured_post is not None:
        broncho_status, broncho_note = bronchodilator_response(fev1, fvc, age_years)

    technical_lines = [quality_text.strip()] if quality_text.strip() else []
    technical_lines.append(pattern)
    if severity != "No aplica":
        technical_lines.append(f"Severidad funcional: {severity}.")
    if broncho_status != "No realizado":
        technical_lines.append(f"Respuesta broncodilatadora: {broncho_status.lower()}.")

    technical_report = " ".join(technical_lines)
    medical_comment = " ".join(comments + [broncho_note])

    return {
        "pattern": pattern,
        "result": pattern,
        "severity": severity,
        "bronchodilator": broncho_status,
        "technical_report": technical_report,
        "medical_comment": medical_comment,
    }


# ----------------------------
# PDF generation
# ----------------------------
def build_summary_chart(params: Dict[str, ParameterResult]) -> io.BytesIO:
    labels = ["FVC", "FEV1", "FEV1/FVC", "PEF", "FEF25-75"]
    pre = [params[k].pct_pred_pre if k in params else None for k in labels]
    post = [params[k].pct_pred_post if k in params else None for k in labels]

    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8, 4))
    pre_vals = [0 if v is None else v for v in pre]
    post_vals = [0 if v is None else v for v in post]
    ax.bar(x - width / 2, pre_vals, width, label="Pre")
    if any(v is not None for v in post):
        ax.bar(x + width / 2, post_vals, width, label="Post")
    ax.axhline(80, linestyle="--", linewidth=1)
    ax.set_ylabel("% del predicho")
    ax.set_title("Resumen espirométrico")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=200)
    buffer.seek(0)
    plt.close(fig)
    return buffer


def render_image_to_rl(uploaded_file, max_width_cm: float = 7.8, max_height_cm: float = 5.8) -> RLImage:
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    width, height = img.size
    aspect = height / width if width else 1
    rl_w = max_width_cm * cm
    rl_h = rl_w * aspect
    if rl_h > max_height_cm * cm:
        rl_h = max_height_cm * cm
        rl_w = rl_h / aspect if aspect else max_width_cm * cm
    uploaded_file.seek(0)
    return RLImage(uploaded_file, width=rl_w, height=rl_h)


def build_values_dataframe(params: Dict[str, ParameterResult]) -> pd.DataFrame:
    rows = []
    for p in params.values():
        rows.append(
            {
                "Parámetro": p.name,
                "Unidad": p.unit,
                "Pre": p.measured_pre,
                "Predicho": p.predicted,
                "%Pred Pre": p.pct_pred_pre,
                "LLN": p.lln,
                "Z Pre": p.zscore_pre,
                "Post": p.measured_post,
                "%Pred Post": p.pct_pred_post,
                "Z Post": p.zscore_post,
                "Δ Abs": p.delta_abs,
                "Δ %": p.delta_pct_baseline,
            }
        )
    return pd.DataFrame(rows)


def make_pdf(
    patient: Dict[str, str],
    study: Dict[str, str],
    params: Dict[str, ParameterResult],
    interpretation: Dict[str, str],
    attachments: Dict[str, object],
) -> bytes:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", fontSize=8.5, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CenterTitle", fontSize=13, leading=15, alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="Section", fontSize=10.5, leading=12, textColor=colors.HexColor("#1F4E79"), spaceBefore=6, spaceAfter=4))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )
    story = []

    header_data = []
    if LOGO_PATH.exists():
        header_data.append([
            RLImage(str(LOGO_PATH), width=2.7 * cm, height=2.7 * cm),
            Paragraph(
                "<b>Consultorio Dr. Andrés López Ruiz</b><br/>"
                "Médico Pediatra<br/>"
                "Calle 11 No. 10 - 83 Consultorio 301<br/>"
                "Edificio Centro Empresarial El Parque<br/>"
                "Sogamoso, Boyacá · Tel. 3004270647",
                styles["Small"],
            ),
        ])
        header = Table(header_data, colWidths=[3.2 * cm, 14.6 * cm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
        story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["CenterTitle"]))
    bogota_now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(f"Fecha de generación: {bogota_now.strftime('%d/%m/%Y %H:%M')}", styles["Small"]))
    story.append(Spacer(1, 0.15 * cm))

    patient_rows = [
        ["Nombre", patient.get("nombre", ""), "Documento", patient.get("identificacion", "")],
        ["Fecha nacimiento", patient.get("fecha_nacimiento", ""), "Edad", patient.get("edad", "")],
        ["Sexo", patient.get("sexo", ""), "EPS", patient.get("eps", "")],
        ["Peso", patient.get("peso", ""), "Talla", patient.get("talla", "")],
        ["Médico remitente", patient.get("remitente", ""), "Fecha del estudio", study.get("fecha_estudio", "")],
        ["Indicación clínica", study.get("indicacion", ""), "IDx", study.get("diagnostico", "")],
    ]
    story.append(Paragraph("1. Identificación del paciente", styles["Section"]))
    t = Table(patient_rows, colWidths=[3.2 * cm, 6.1 * cm, 3.0 * cm, 6.0 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)

    story.append(Paragraph("2. Datos técnicos del estudio", styles["Section"]))
    tech_rows = [
        ["Tipo de estudio", study.get("tipo_estudio", "")],
        ["Calidad / aceptabilidad", study.get("calidad", "")],
        ["Reproducibilidad", study.get("reproducibilidad", "")],
        ["Cooperación", study.get("cooperacion", "")],
        ["Broncodilatador", study.get("broncodilatador", "")],
        ["Tiempo post-BD", study.get("tiempo_post", "")],
    ]
    t2 = Table(tech_rows, colWidths=[4.5 * cm, 13.8 * cm])
    t2.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
    ]))
    story.append(t2)

    story.append(Paragraph("3. Resultados espirométricos", styles["Section"]))
    df = build_values_dataframe(params)
    display_df = df.copy()
    for col in display_df.columns[2:]:
        display_df[col] = display_df[col].map(lambda x: "—" if pd.isna(x) else f"{x:.2f}")
    table_data = [display_df.columns.tolist()] + display_df.values.tolist()
    col_widths = [2.8 * cm, 1.4 * cm, 1.4 * cm, 1.5 * cm, 1.5 * cm, 1.3 * cm, 1.2 * cm, 1.4 * cm, 1.5 * cm, 1.2 * cm, 1.3 * cm, 1.3 * cm]
    rt = Table(table_data, repeatRows=1, colWidths=col_widths)
    rt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(rt)

    story.append(Paragraph("4. Interpretación", styles["Section"]))
    interp_rows = [
        ["Severidad", interpretation["severity"]],
        ["Respuesta broncodilatadora", interpretation["bronchodilator"]],
        ["Reporte técnico", Paragraph(interpretation["technical_report"], styles["Small"])],
        ["Comentario médico", Paragraph(interpretation["medical_comment"], styles["Small"])],
    ]
    t3 = Table(interp_rows, colWidths=[4.5 * cm, 13.8 * cm])
    t3.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t3)

    chart_buffer = build_summary_chart(params)
    resumen_graphic = KeepTogether([
        Paragraph("5. Resumen gráfico", styles["Section"]),
        RLImage(chart_buffer, width=12.0 * cm, height=6.0 * cm),
    ])
    story.append(resumen_graphic)

    image1 = attachments.get("curve_image_1")
    image2 = attachments.get("curve_image_2")
    if image1 or image2:
        curve_elements = [Paragraph("6. Curvas / soporte gráfico", styles["Section"])]
        image_cells = []
        if image1:
            image_cells.append([Paragraph("Curva flujo-volumen", styles["Small"]), render_image_to_rl(image1)])
        if image2:
            image_cells.append([Paragraph("Curva volumen-tiempo", styles["Small"]), render_image_to_rl(image2)])

        if len(image_cells) == 2:
            curve_table = Table([[image_cells[0][1], image_cells[1][1]], [image_cells[0][0], image_cells[1][0]]], colWidths=[8.4 * cm, 8.4 * cm])
            curve_table.setStyle(TableStyle([
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 2),
            ]))
            curve_elements.append(curve_table)
        else:
            img = image_cells[0][1]
            lbl = image_cells[0][0]
            single_table = Table([[img], [lbl]], colWidths=[12.0 * cm])
            single_table.setStyle(TableStyle([
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ]))
            curve_elements.append(single_table)

        story.append(KeepTogether(curve_elements))

    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("<b>Dr. Andrés López Ruiz</b><br/>Médico Pediatra<br/>RETHUS: 1082877373", styles["Small"]))

    doc.build(story)
    main_pdf = buffer.getvalue()
    buffer.close()

    uploaded_pdf = attachments.get("curve_pdf")
    if uploaded_pdf:
        try:
            writer = PdfWriter()
            main_reader = PdfReader(io.BytesIO(main_pdf))
            for page in main_reader.pages:
                writer.add_page(page)
            annex_reader = PdfReader(uploaded_pdf)
            for page in annex_reader.pages:
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception:
            return main_pdf

    return main_pdf


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
    fecha_nacimiento = c4.date_input("Fecha de nacimiento", value=None, min_value=date(1900,1,1), max_value=date.today(), format="DD/MM/YYYY")
    sexo = c5.selectbox("Sexo", ["", "Femenino", "Masculino", "Otro"])
    remitente = c6.text_input("Médico remitente")

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

    # Calcular valores predichos y LLN automáticamente
    rows_data = calcular_predichos_lln(rows_data, edad_num, sexo, talla)

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
    interpretation = build_interpretation(edad_num, params, quality_text)
    if nota_medica_manual.strip():
        interpretation["medical_comment"] = interpretation["medical_comment"] + " " + nota_medica_manual.strip()

    patient_dict = {
        "nombre": nombre,
        "identificacion": f"{id_tipo} {identificacion}".strip(),
        "fecha_nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if isinstance(fecha_nacimiento, date) else "",
        "edad": edad_txt,
        "sexo": sexo,
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
