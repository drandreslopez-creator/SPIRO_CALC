from utils.calculations import fmt_num

import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from typing import Dict, Any
from pypdf import PdfReader, PdfWriter
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.platypus import (
    Image as RLImage,
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
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER

from PIL import Image


APP_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = APP_DIR / "logo.png"


# 🔥 FOOTER DEVICE ID
def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1 * cm, "Device ID: PULMO70BEXPII100078")
    canvas.restoreState()


def build_summary_chart(params: Dict[str, Any]) -> io.BytesIO:
    labels = ["FVC", "FEV1", "FEV1/FVC", "PEF", "FEF25-75"]

    pre = [params[k].pct_pred_pre if k in params else None for k in labels]
    post = [params[k].pct_pred_post if k in params else None for k in labels]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4))

    pre_vals = [0 if v is None else v for v in pre]
    post_vals = [0 if v is None else v for v in post]

    ax.bar(x - width/2, pre_vals, width, label="Pre")

    if any(v is not None for v in post):
        ax.bar(x + width/2, post_vals, width, label="Post")

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


def render_image(uploaded_file, max_width_cm=10):
    if uploaded_file is None:
        return None

    try:
        img = Image.open(uploaded_file)

        width, height = img.size
        aspect = height / width if width else 1

        rl_width = max_width_cm * cm
        rl_height = rl_width * aspect

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return RLImage(buffer, width=rl_width, height=rl_height)

    except Exception as e:
        print("Error imagen:", e)
        return None


def make_pdf(patient, study, params, interpretation, attachments):

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="XSmall", fontSize=8.5, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Justify", fontSize=8.6, leading=10, alignment=TA_JUSTIFY))

    styles.add(ParagraphStyle(
        name="XTitle",
        fontSize=12,
        leading=14,
        alignment=TA_CENTER,
        spaceBefore=12,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name="XSection",
        fontSize=10.5,
        leading=12,
        textColor=colors.HexColor("#1F4E79"),
        spaceBefore=6,
        spaceAfter=4
    ))

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
                RLImage(str(LOGO_PATH), width=2.5 * cm, height=2.5 * cm),
                Paragraph(
                    "<b>Consultorio Dr. Andrés López Ruiz</b><br/>"
                    "Médico Especialista en Pediatría<br/>"
                    "Calle 11 No. 10 - 83 Consultorio 301<br/>"
                    "Sogamoso, Boyacá · Tel. 3004270647",
                    styles["XSmall"],
                )
            ]],
            colWidths=[3 * cm, 14 * cm]
        )

        header.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("TOPPADDING", (0,0), (0,0), -8),
        ]))

        story.append(header)

    story.append(Spacer(1, 10))
    story.append(Paragraph("REPORTE DE ESPIROMETRÍA", styles["XTitle"]))

    now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(f"Fecha: {now.strftime('%d/%m/%Y %H:%M')}", styles["XSmall"]))

    # ... (TODO tu contenido se mantiene EXACTO igual)

    story.append(PageBreak())
    story.append(Paragraph("5. Resumen gráfico", styles["XSection"]))

    story.append(RLImage(build_summary_chart(params), width=14*cm, height=7*cm))

    # 🔥 FIRMA MÉDICA
    story.append(Spacer(1, 40))

    firma = """
    <b>DR. ANDRÉS LÓPEZ RUIZ</b><br/>
    MÉDICO ESPECIALISTA EN PEDIATRÍA<br/>
    INTERPRETACIÓN DE ESPIROMETRÍA
    """

    story.append(Paragraph(firma, styles["XSmall"]))

    # 🔥 FOOTER ACTIVADO
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes