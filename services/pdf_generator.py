from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import A4
import io

def generate_pdf(text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    elements = [Paragraph(text)]

    doc.build(elements)
    return buffer.getvalue()
