import io
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def field(fields, label):
    return next(item for item in fields if item.label == label)


PREPARE = "Preparar borrador para revisión"
EXPORT = "Confirmar revisión y preparar PDF de prueba"
CONFIRM = "He revisado la identidad, los valores y anexos del estudio, y la conclusión."


class ReviewFlowTests(unittest.TestCase):
    def new_app(self, with_reference=True, post=False):
        app = AppTest.from_file(APP, default_timeout=25).run()
        self.assertFalse(app.exception)
        field(app.text_input, "Nombre completo").set_value("Caso sintético A")
        field(app.date_input, "Fecha de nacimiento").set_value(date(2015, 1, 1))
        field(app.date_input, "Fecha del estudio").set_value(date(2026, 1, 1))
        field(app.selectbox, "Calidad / aceptabilidad").set_value("Aceptable")
        field(app.selectbox, "Reproducibilidad").set_value("Adecuada")
        field(app.selectbox, "Cooperación del paciente").set_value("Buena")
        app.checkbox[0].check()
        if with_reference:
            field(app.text_input, "Ecuación o familia de referencia").set_value("Referencia de prueba")
            field(app.text_input, "Versión o año de la ecuación").set_value("2022")
        if post:
            field(app.selectbox, "Tipo de estudio").set_value("Espirometría pre y post broncodilatador")
        app.checkbox[1].check()
        for label, value in {"FVC_pre": 2., "FVC_lln": 1.7, "FVC_pred": 2.2, "FVC_post": 2.25,
                             "FEV1_pre": 1.6, "FEV1_lln": 1.4, "FEV1_pred": 1.8,
                             "FEV1_post": 1.8, "FEV1/FVC_pre": 80., "FEV1/FVC_lln": 75.}.items():
            field(app.number_input, label).set_value(value)
        return app

    def test_review_pdf_and_new_study_invalidates_export(self):
        app = self.new_app()
        field(app.button, PREPARE).click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.get("download_button"))
        self.assertEqual(app.session_state["report_snapshot"][3]["bronchodilator"], "No aplica (estudio simple)")
        self.assertIsNone(app.session_state["report_snapshot"][2]["FEV1"].measured_post)

        field(app.button, EXPORT).click().run()
        self.assertFalse(app.get("download_button"))
        self.assertTrue(any("Confirma" in e.value for e in app.error))

        field(app.text_area, "Conclusión clínica editable").set_value("Conclusión sintética A & B.")
        field(app.checkbox, CONFIRM).check()
        field(app.button, EXPORT).click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("download_button")), 2)
        content = "".join(page.extract_text() for page in
                          PdfReader(io.BytesIO(app.session_state["report_export"][0])).pages)
        self.assertIn("NO USAR EN ATENCIÓN CLÍNICA", content)
        self.assertIn("Conclusión sintética A & B.", content)
        self.assertIn("Referencia de prueba", content)
        self.assertNotIn("Aumento >10%", content)

        field(app.button, "Volver a editar la conclusión").click().run()
        self.assertEqual(field(app.text_area, "Conclusión clínica editable").value, "Conclusión sintética A & B.")
        self.assertFalse(field(app.checkbox, CONFIRM).value)
        self.assertFalse(app.get("download_button"))

        field(app.text_input, "Nombre completo").set_value("Caso sintético B")
        field(app.button, PREPARE).click().run()
        self.assertNotIn("sintética A", field(app.text_area, "Conclusión clínica editable").value)
        self.assertFalse(app.get("download_button"))
        field(app.date_input, "Fecha del estudio").set_value(date(2014, 1, 1))
        field(app.button, PREPARE).click().run()
        self.assertTrue(any("posterior" in e.value for e in app.error))
        self.assertNotIn("report_snapshot", app.session_state)
        self.assertFalse(app.get("download_button"))

    def test_missing_reference_disables_automated_classification_and_bdr(self):
        app = self.new_app(with_reference=False, post=True)
        field(app.button, PREPARE).click().run()
        self.assertFalse(app.exception)
        result = app.session_state["report_snapshot"][3]
        self.assertEqual(result["pattern"], "No clasificable automáticamente")
        self.assertEqual(result["bronchodilator"], "No evaluable")

    def test_pre_post_verified_distinguishes_ats_ers_from_gina(self):
        app = self.new_app(post=True)
        field(app.button, PREPARE).click().run()
        self.assertFalse(app.exception)
        result = app.session_state["report_snapshot"][3]
        self.assertEqual(result["bronchodilator"], "Positiva (ERS/ATS)")
        self.assertIn("no cumple el criterio de aumento de FEV1 ≥12%", result["technical_report"])
