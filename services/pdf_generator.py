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
                "Médico Especialista en Pediatría<br/>"
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

    story.append(Spacer(1, 2.50 * cm))
    story.append(Paragraph("<b>Dr. Andrés López Ruiz</b><br/>Médico Pediatra<br/>RM 1082877373", styles["Small"]))

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
