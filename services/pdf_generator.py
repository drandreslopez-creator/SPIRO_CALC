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

    # ⚠️ nombres cambiados para evitar error
    styles.add(ParagraphStyle(name="MySmall", fontSize=8.5, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="MyTitle", fontSize=13, leading=15, alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="MySection", fontSize=10.5, leading=12, textColor=colors.HexColor("#1F4E79"), spaceBefore=6, spaceAfter=4))

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

    # 🔹 ENCABEZADO
    if LOGO_PATH.exists():
        header = Table([
            [
                RLImage(str(LOGO_PATH), width=2.7 * cm, height=2.7 * cm),
                Paragraph(
                    "<b>Consultorio Dr. Andrés López Ruiz</b><br/>"
                    "Médico Especialista en Pediatría<br/>"
                    "Sogamoso, Boyacá · Tel. 3004270647",
                    styles["MySmall"],
                ),
            ]
        ], colWidths=[3.2 * cm, 14.6 * cm])

        story.append(header)
        story.append(Spacer(1, 6))

    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["MyTitle"]))

    now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(f"Fecha: {now.strftime('%d/%m/%Y %H:%M')}", styles["MySmall"]))

    # 🔹 IDENTIFICACIÓN
    story.append(Paragraph("1. Identificación del paciente", styles["MySection"]))

    t = Table([
        ["Nombre", patient.get("nombre",""), "Documento", patient.get("identificacion","")],
        ["Edad", patient.get("edad",""), "Sexo", patient.get("sexo","")],
    ])

    story.append(t)

    # 🔹 RESULTADOS
    story.append(Paragraph("2. Resultados", styles["MySection"]))

    df = build_values_dataframe(params)
    table_data = [df.columns.tolist()] + df.fillna("").values.tolist()

    story.append(Table(table_data))

    # 🔹 INTERPRETACIÓN
    story.append(Paragraph("3. Interpretación", styles["MySection"]))
    story.append(Paragraph(interpretation["technical_report"], styles["MySmall"]))
    story.append(Paragraph(interpretation["medical_comment"], styles["MySmall"]))

    # 🔹 GRÁFICA
    chart = build_summary_chart(params)
    story.append(RLImage(chart, width=12 * cm, height=6 * cm))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf
