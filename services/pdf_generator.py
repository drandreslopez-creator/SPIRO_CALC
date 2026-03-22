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
def make_pdf(
    patient,
    study,
    params,
    interpretation,
    attachments,
) -> bytes:

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="MySmall", fontSize=8.5, leading=10))
    styles.add(ParagraphStyle(name="MyTitle", fontSize=14, leading=16, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="MySection", fontSize=11, leading=13, textColor=colors.HexColor("#1F4E79")))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    story = []

    # ENCABEZADO
    story.append(Paragraph("CONSULTORIO DR. ANDRÉS LÓPEZ RUIZ", styles["MyTitle"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["MyTitle"]))
    story.append(Spacer(1, 10))

    # DATOS PACIENTE
    story.append(Paragraph("1. IDENTIFICACIÓN", styles["MySection"]))
    story.append(Paragraph(f"Nombre: {patient.get('nombre','')}", styles["MySmall"]))
    story.append(Paragraph(f"Documento: {patient.get('identificacion','')}", styles["MySmall"]))
    story.append(Paragraph(f"Edad: {patient.get('edad','')} | Sexo: {patient.get('sexo','')}", styles["MySmall"]))
    story.append(Spacer(1, 10))

    # DATOS ESTUDIO
    story.append(Paragraph("2. DATOS DEL ESTUDIO", styles["MySection"]))
    story.append(Paragraph(f"Fecha: {study.get('fecha_estudio','')}", styles["MySmall"]))
    story.append(Paragraph(f"Indicación: {study.get('indicacion','')}", styles["MySmall"]))
    story.append(Spacer(1, 10))

    # TABLA DE RESULTADOS
    story.append(Paragraph("3. RESULTADOS ESPIROMÉTRICOS", styles["MySection"]))

    data = [["Parámetro", "Pre", "%Pred", "LLN", "Post"]]

    for p in params.values():
        data.append([
            p.name,
            f"{p.measured_pre or ''}",
            f"{round(p.pct_pred_pre,1) if p.pct_pred_pre else ''}",
            f"{p.lln or ''}",
            f"{p.measured_post or ''}",
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.3, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)
    ]))

    story.append(table)
    story.append(Spacer(1, 10))

    # INTERPRETACIÓN
    story.append(Paragraph("4. INTERPRETACIÓN", styles["MySection"]))
    story.append(Paragraph(interpretation["technical_report"], styles["MySmall"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(interpretation["medical_comment"], styles["MySmall"]))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf
