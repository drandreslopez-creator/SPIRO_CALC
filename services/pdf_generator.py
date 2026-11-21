from xml.sax.saxutils import escape
from utils.calculations import fmt_num
from services.study_guard import has_post_phase

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


# ----------------------------
# LOGO
# ----------------------------
APP_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = APP_DIR / "logo.png"


# ----------------------------
# GRÁFICA
# ----------------------------
def build_summary_chart(params: Dict[str, Any], include_post: bool = True) -> io.BytesIO:
    labels = ["FVC", "FEV1", "FEV1/FVC", "PEF", "FEF25-75"]

    pre = [params[k].pct_pred_pre if k in params else None for k in labels]
    post = [params[k].pct_pred_post if k in params else None for k in labels]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 4))

    pre_vals = [float("nan") if v is None else v for v in pre]
    post_vals = [float("nan") if v is None else v for v in post]

    ax.bar(x - width/2, pre_vals, width, label="Pre")

    if include_post and any(v is not None for v in post):
        ax.bar(x + width/2, post_vals, width, label="Post")

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
# TABLA
# ----------------------------
def build_values_dataframe(params: Dict[str, Any], include_post: bool = True) -> pd.DataFrame:
    rows = []

    for p in params.values():
        row = {
            "Parámetro": p.name,
            "Unidad": p.unit,
            "Pre": p.measured_pre,
            "Predicho": p.predicted,
            "%Pred Pre": p.pct_pred_pre,
            "LLN": p.lln,
            "Z Pre": p.zscore_pre,
        }
        if include_post:
            row.update({
                "Post": p.measured_post,
                "%Pred Post": p.pct_pred_post,
                "Z Post": p.zscore_post,
                "Δ Abs": p.delta_abs,
                "Δ % basal": p.delta_pct_baseline,
            })
        rows.append(row)

    return pd.DataFrame(rows)


# ----------------------------
# IMÁGENES
# ----------------------------
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

    except Exception:
        return None


# ----------------------------
# PDF PRINCIPAL
# ----------------------------
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

    # ---------------- HEADER ----------------
    if LOGO_PATH.exists():
        header = Table(
            [[
                RLImage(str(LOGO_PATH), width=2.5 * cm, height=2.5 * cm),
                Paragraph(
                    "<b>Consultorio Dr. Andrés López Ruiz</b><br/>"
                    "Médico Especialista en Pediatría<br/>"
                    "Calle 11 No. 10 - 83 Consultorio 301<br/>"
                    "Edificio Centro Empresarial El Parque<br/>"
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
    story.append(Paragraph("<b>PRUEBA · NO USAR EN ATENCIÓN CLÍNICA</b>", styles["XSmall"]))

    now = datetime.now(ZoneInfo("America/Bogota"))
    story.append(Paragraph(f"Emisión: {now.strftime('%d/%m/%Y %H:%M')}", styles["XSmall"]))

    # ---------------- PACIENTE ----------------
    story.append(Spacer(1, 6))
    story.append(Paragraph("1. Identificación del paciente", styles["XSection"]))

    t = Table([
        ["Nombre", patient.get("nombre",""), "Documento", patient.get("identificacion","")],
        ["Fecha nacimiento", patient.get("fecha_nacimiento",""), "Edad", patient.get("edad","")],
        ["Sexo", patient.get("sexo",""), "EPS", patient.get("eps","")],
        ["Etnia", patient.get("etnia",""), "Tabaquismo", patient.get("fumador","")],
        ["Peso", patient.get("peso",""), "Talla", patient.get("talla","")],
        ["Médico remitente", patient.get("remitente",""), "Fecha estudio", study.get("fecha_estudio","")],
    ], colWidths=[3.2*cm,6.1*cm,3.0*cm,6.0*cm])

    t.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("BACKGROUND",(2,0),(2,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.5),
    ]))

    story.append(t)

    # ---------------- DATOS ----------------
    story.append(Spacer(1, 6))
    story.append(Paragraph("2. Datos técnicos del estudio", styles["XSection"]))

    technical_rows = [
        ["Tipo de estudio", study.get("tipo_estudio","")],
        ["Calidad", study.get("calidad","")],
        ["Reproducibilidad", study.get("reproducibilidad","")],
        ["Cooperación", study.get("cooperacion","")],
        ["Referencia (ecuación y versión)", Paragraph(escape(study.get("referencia", "No informada")), styles["XSmall"])],
        ["Procedencia confirmada", "Sí" if study.get("referencia_verificada") else "No"],
    ]
    include_post = has_post_phase(study.get("tipo_estudio"))
    if include_post:
        technical_rows.extend([
            ["Broncodilatador", study.get("broncodilatador","")],
            ["Tiempo post-BD", study.get("tiempo_post","")],
        ])
    t2 = Table(technical_rows, colWidths=[5*cm,13*cm])

    t2.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.5),
    ]))

    story.append(t2)

    # ---------------- RESULTADOS ----------------
    story.append(Spacer(1, 6))
    story.append(Paragraph("3. Resultados espirométricos", styles["XSection"]))

    df = build_values_dataframe(params, include_post=include_post)

    def fmt(x, digits=2):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return "—"
        if isinstance(x, (int, float)):
            return f"{x:.{digits}f}"
        return str(x)

    display_df = df.copy()
    for col in display_df.columns:
        digits = 3 if col in ("LLN", "Z Pre", "Z Post") else 2
        display_df[col] = display_df[col].apply(lambda value: fmt(value, digits))

    table_data = [display_df.columns.tolist()] + display_df.values.tolist()

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.25,colors.grey),
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
        ("FONTSIZE",(0,0),(-1,-1),8),
    ]))

    story.append(table)

    # ---------------- INTERPRETACIÓN ----------------
    story.append(Spacer(1, 6))
    story.append(Paragraph("4. Interpretación", styles["XSection"]))

    interpretation_rows = [
        ["Reporte técnico", Paragraph(escape(interpretation.get("technical_report","")), styles["Justify"])],
        ["Hallazgo orientativo", Paragraph(escape(interpretation.get("medical_comment","")), styles["Justify"])],
        ["Severidad", Paragraph(escape(interpretation.get("severity","")), styles["XSmall"])],
    ]
    if interpretation.get("reviewed_clinical_comment"):
        conclusion = escape(interpretation["reviewed_clinical_comment"]).replace("\n", "<br/>")
        interpretation_rows.append(["Conclusión revisada", Paragraph(conclusion, styles["Justify"])])
    if include_post:
        interpretation_rows.append(["Respuesta broncodilatadora",
                                    Paragraph(escape(interpretation.get("bronchodilator","")), styles["XSmall"])])
    t3 = Table(interpretation_rows, colWidths=[5*cm,13*cm])

    t3.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("FONTSIZE",(0,0),(-1,-1),8.6),
    ]))

    story.append(t3)

    # ---------------- RESUMEN GRÁFICO ----------------
    story.append(PageBreak())
    story.append(Paragraph("5. Resumen gráfico", styles["XSection"]))

    story.append(RLImage(build_summary_chart(params, include_post=include_post), width=14*cm, height=7*cm))

    # 🔥 IMÁGENES CORREGIDAS
    if attachments.get("curve_image_1"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("Curva flujo-volumen", styles["XSmall"]))
        img1 = render_image(attachments["curve_image_1"], max_width_cm=7)
        if img1 is None:
            raise ValueError("No se pudo leer el anexo flujo-volumen. Reemplázalo o retíralo.")
        story.append(img1)

    if attachments.get("curve_image_2"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("Curva volumen-tiempo", styles["XSmall"]))
        img2 = render_image(attachments["curve_image_2"], max_width_cm=7)
        if img2 is None:
            raise ValueError("No se pudo leer el anexo volumen-tiempo. Reemplázalo o retíralo.")
        story.append(img2)

    # 🔥🔥🔥 AQUÍ EMPIEZAN LOS ÚNICOS CAMBIOS 🔥🔥🔥

    story.append(Spacer(1, 55))

    story.append(Paragraph(
        "<b>DR. ANDRÉS LÓPEZ RUIZ</b><br/>"
        "MÉDICO ESPECIALISTA EN PEDIATRÍA<br/>"
        "INTERPRETACIÓN DE ESPIROMETRÍA",
        styles["XSmall"]
    ))

    story.append(Spacer(1, 35))

    story.append(Paragraph(
        "Espirómetro: " + escape(study.get("identificador_equipo") or "No informado"),
        styles["XSmall"]
    ))

    # 🔥🔥🔥 FIN DE CAMBIOS 🔥🔥🔥

    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # 🔥 FUSIÓN CON PDF DEL EQUIPO (SIN TOCAR)
    curve_pdf = attachments.get("curve_pdf")

    if curve_pdf is not None:
        try:
            writer = PdfWriter()

            main_pdf = PdfReader(io.BytesIO(pdf_bytes))
            for page in main_pdf.pages:
                writer.add_page(page)

            curve_pdf.seek(0)
            extra_pdf = PdfReader(curve_pdf)

            for page in extra_pdf.pages:
                writer.add_page(page)

            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)

            return output_buffer.read()

        except Exception as exc:
            raise ValueError("No se pudo incorporar el PDF del equipo. Reemplázalo o retíralo.") from exc

    return pdf_bytes