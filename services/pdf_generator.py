# services/pdf_generator.py

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
    patient: Dict[str, str],
    study: Dict[str, str],
    params: Dict[str, Any],
    interpretation: Dict[str, str],
    attachments: Dict[str, object],
) -> bytes:

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", fontSize=8.5))
    styles.add(ParagraphStyle(name="CenterTitle", fontSize=13))

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4)

    story = []

    # TÍTULO
    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["CenterTitle"]))

    # FECHA
    now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(now.strftime("%d/%m/%Y %H:%M"), styles["Small"]))

    # TABLA
    df = build_values_dataframe(params)

    table_data = [df.columns.tolist()] + df.fillna("").values.tolist()

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey)
    ]))

    story.append(Spacer(1, 10))
    story.append(table)

    # INTERPRETACIÓN
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Resultado: {interpretation['result']}", styles["Small"]))

    # GRÁFICA
    chart = build_summary_chart(params)
    story.append(RLImage(chart, width=400, height=200))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf