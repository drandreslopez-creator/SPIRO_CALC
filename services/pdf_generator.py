# services/pdf_generator.py

from utils.calculations import fmt_num

import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from typing import Dict, Any
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from pypdf import PdfReader, PdfWriter
from PIL import Image


# LOGO
APP_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = APP_DIR / "logo.png"


# ----------------------------
# GRÁFICA
# ----------------------------
def build_summary_chart(params: Dict[str, Any]) -> io.BytesIO:
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


# ----------------------------
# IMÁGENES
# ----------------------------
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


# ----------------------------
# TABLA
# ----------------------------
def build_values_dataframe(params: Dict[str, Any]) -> pd.DataFrame:
    rows = []

    for p in params.values():
        rows.append({
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
        })

    return pd.DataFrame(rows)


# ----------------------------
# PDF PRINCIPAL
# ----------------------------
def make_pdf(patient, study, params, interpretation, attachments):

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="XSmall", fontSize=8.5, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(
    name="XTitle",
    fontSize=12,
    leading=15,
    alignment=TA_CENTER,
    spaceBefore=20,   # 🔥 AQUÍ está la clave
    spaceAfter=8
))
    styles.add(ParagraphStyle(name="XSection", fontSize=10.5, leading=12, textColor=colors.HexColor("#1F4E79"), spaceBefore=6, spaceAfter=4))

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

        # HEADER
    if LOGO_PATH.exists():
    header = Table(
        [[
            RLImage(str(LOGO_PATH), width=2.4 * cm, height=2.4 * cm),
            Paragraph(
                "<b>Consultorio Dr. Andrés López Ruiz</b><br/>"
                "Médico Especialista en Pediatría<br/>"
                "Calle 11 No. 10 - 83 Consultorio 301<br/>"
                "Edificio Centro Empresarial El Parque<br/>"
                "Sogamoso, Boyacá · Tel. 3004270647",
                styles["XSmall"],
            )
        ]],
        colWidths=[2.8 * cm, 14.2 * cm]
    )

    header.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (0,0), -17),
    ]))

        story.append(header)

    # 🔥 DOBLE ESPACIO REAL
    story.append(Spacer(1, 12))
    story.append(Spacer(1, 12))

    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["XTitle"]))

    now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(f"Fecha de generación: {now.strftime('%d/%m/%Y %H:%M')}", styles["XSmall"]))

    # PACIENTE
    story.append(Spacer(1, 6))
    story.append(Paragraph("1. Identificación del paciente", styles["XSection"]))

    t = Table([
        ["Nombre", patient.get("nombre",""), "Documento", patient.get("identificacion","")],
        ["Fecha nacimiento", patient.get("fecha_nacimiento",""), "Edad", patient.get("edad","")],
        ["Sexo", patient.get("sexo",""), "EPS", patient.get("eps","")],
        ["Peso", patient.get("peso",""), "Talla", patient.get("talla","")],
        ["Médico remitente", patient.get("remitente",""), "Fecha del estudio", study.get("fecha_estudio","")],
        ["Indicación clínica", study.get("indicacion",""), "IDx", study.get("diagnostico","")],
    ], colWidths=[3.2*cm,6.1*cm,3.0*cm,6.0*cm])

    t.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.35,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("BACKGROUND",(2,0),(2,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.6),
    ]))

    story.append(t)

    # DATOS TÉCNICOS
    story.append(Spacer(1, 6))
    story.append(Paragraph("2. Datos técnicos del estudio", styles["XSection"]))

    t2 = Table([
        ["Tipo de estudio", study.get("tipo_estudio","")],
        ["Calidad", study.get("calidad","")],
        ["Reproducibilidad", study.get("reproducibilidad","")],
        ["Cooperación", study.get("cooperacion","")],
        ["Broncodilatador", study.get("broncodilatador","")],
        ["Tiempo post-BD", study.get("tiempo_post","")],
    ], colWidths=[4.5*cm,13.8*cm])

    t2.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.35,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.6),
    ]))

    story.append(t2)

    # RESULTADOS
    story.append(Spacer(1, 6))
    story.append(Paragraph("3. Resultados espirométricos", styles["XSection"]))

    df = build_values_dataframe(params)

    def fmt(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return "—"
        if isinstance(x, (int, float)):
            return f"{x:.2f}"
        return str(x)

    display_df = df.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].apply(fmt)

    headers = [
        "Parámetro","Unidad","Pre","Predicho","%Pred Pre",
        "LLN","Z Pre","Post","%Pred Post","Z Post","Δ Abs","Δ %"
    ]

    table_data = [headers] + display_df.values.tolist()

    col_widths = [
        2.5*cm,1.2*cm,1.3*cm,1.5*cm,1.5*cm,
        1.3*cm,1.2*cm,1.3*cm,1.5*cm,1.2*cm,
        1.3*cm,1.3*cm
    ]

    table = Table(table_data, repeatRows=1, colWidths=col_widths)

    table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.25,colors.grey),
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("ALIGN",(2,1),(-1,-1),"CENTER"),
    ]))

    story.append(table)

    # INTERPRETACIÓN
    story.append(Spacer(1, 6))
    story.append(Paragraph("4. Interpretación", styles["XSection"]))

    t3 = Table([
        ["Severidad", interpretation.get("severity","")],
        ["Respuesta broncodilatadora", interpretation.get("bronchodilator","")],
        ["Reporte técnico", interpretation.get("technical_report","")],
        ["Comentario médico", interpretation.get("medical_comment","")],
    ], colWidths=[5*cm,13*cm])

    t3.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.5),
    ]))

    story.append(t3)

    # GRÁFICA EN NUEVA PÁGINA
    story.append(PageBreak())

    story.append(Paragraph("5. Resumen gráfico", styles["XSection"]))
    story.append(RLImage(build_summary_chart(params), width=14*cm, height=7*cm))

    # FIRMA
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "<b>Dr. Andrés López Ruiz</b><br/>Médico Pediatra<br/>RM 1082877373",
        styles["XSmall"]
    ))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf