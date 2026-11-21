"""Regression examples from ERS publications; no patient data or reference engine.

GLI 2012, online supplement §4.3.4; doi:10.1183/09031936.00080312.
ERS/ATS interpretive standard, Box 1; doi:10.1183/13993003.01499-2021.
"""
import csv
import io
import unittest
from datetime import date
from fractions import Fraction
from pathlib import Path

from pypdf import PdfReader

from services.interpretation import (
    bronchodilator_response, change_over_predicted, is_below_lln,
)
from services.pdf_generator import build_values_dataframe, make_pdf
from services.spirometry_logic import parameters_from_entered_values
from services.study_guard import POST_STUDY, SIMPLE_STUDY


def fev1_case(pre, pred, lln=None, zpre=None, post=None):
    return parameters_from_entered_values({
        "FEV1": {
            "unit": "L", "pre": pre, "pred": pred, "lln": lln,
            "zpre": zpre, "post": post, "zpost": None,
        }
    })


def pdf_text(params, report, include_post):
    pdf = make_pdf(
        {"nombre": "Ejemplo publicado"},
        {"fecha_estudio": "01/02/2026", "referencia": "GLI | 2012",
         "tipo_estudio": POST_STUDY if include_post else SIMPLE_STUDY,
         "referencia_verificada": True, "include_post": include_post},
        params, report, {},
    )
    return " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


class PublishedReferenceExamples(unittest.TestCase):
    def test_gli_4_3_4_fev1_preserves_the_supplied_reference(self):
        params = fev1_case(2.210, 2.7800, lln=2.1741, zpre=-1.55)
        fev1 = params["FEV1"]
        self.assertFalse(is_below_lln(fev1))
        self.assertEqual(f"{fev1.pct_pred_pre:.1f}", "79.5")
        self.assertEqual((fev1.predicted, fev1.lln, fev1.zscore_pre), (2.7800, 2.1741, -1.55))
        csv_text = build_values_dataframe(params, include_post=False).to_csv(index=False)
        row = next(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(tuple(float(row[name]) for name in ("Pre", "Predicho", "LLN", "Z Pre")),
                         (2.210, 2.7800, 2.1741, -1.55))
        rendered = pdf_text(params, {}, include_post=False)
        for display in ("2.2100", "2.7800", "2.1741", "-1.550", "79.5"):
            self.assertIn(display, rendered)

    def test_fourth_decimal_is_retained_for_the_lln_boundary(self):
        self.assertTrue(is_below_lln(fev1_case(2.1740, 2.7800, lln=2.1741)["FEV1"]))
        self.assertFalse(is_below_lln(fev1_case(2.1741, 2.7800, lln=2.1741)["FEV1"]))

    def test_ers_ats_box_1_uses_exact_predicted_denominator(self):
        params = fev1_case(pre=2.00, post=2.40, pred=3.32)
        fev1 = params["FEV1"]
        exact = change_over_predicted(fev1)
        self.assertEqual(exact, Fraction(10, 83))
        # The published Box prints 12.1%, but its stated inputs yield
        # 12.04819277...%, i.e. 12.0% to nearest tenth. Both are >10%.
        self.assertEqual(f"{float(exact * 100):.1f}", "12.0")
        status, detail = bronchodilator_response(fev1, None, 50, quality_ok=True)
        self.assertEqual(status, "Positiva (ERS/ATS)")
        self.assertIn("FEV1 +12.05%", detail)
        self.assertNotIn("GINA", detail)
        row = next(csv.DictReader(io.StringIO(build_values_dataframe(params).to_csv(index=False))))
        self.assertEqual(tuple(float(row[name]) for name in ("Pre", "Post", "Predicho")),
                         (2.00, 2.40, 3.32))
        self.assertIn("+12.05%", pdf_text(params, {
            "technical_report": detail, "bronchodilator": status,
        }, include_post=True))
        for invalid_quality in (False, None):
            status, detail = bronchodilator_response(fev1, None, 50, quality_ok=invalid_quality)
            self.assertEqual(status, "No evaluable")
            self.assertNotIn("12.05", detail)

    def test_positive_value_can_display_rounded_to_the_threshold(self):
        fev1 = fev1_case(pre=2.0000, post=2.3321, pred=3.3200)["FEV1"]
        status, detail = bronchodilator_response(fev1, None, 50, quality_ok=True)
        self.assertEqual(status, "Positiva (ERS/ATS)")
        self.assertIn("+10.00%", detail)
        self.assertIn("sin redondear", detail)


    def test_published_examples_from_form_to_preview_and_reviewed_export(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest is not installed")
        app_path = str(Path(__file__).resolve().parents[1] / "app.py")

        def get(fields, label):
            return next(item for item in fields if item.label == label)

        for case in ("GLI", "ERS/ATS"):
            with self.subTest(case=case):
                app = AppTest.from_file(app_path, default_timeout=25).run()
                self.assertFalse(app.exception)
                get(app.text_input, "Nombre completo").set_value("Ejemplo publicado sin datos personales")
                get(app.date_input, "Fecha de nacimiento").set_value(date(1976, 1, 1))
                get(app.date_input, "Fecha del estudio").set_value(date(2026, 1, 1))
                get(app.selectbox, "Calidad / aceptabilidad").set_value("Aceptable")
                get(app.selectbox, "Reproducibilidad").set_value("Adecuada")
                get(app.selectbox, "Cooperación del paciente").set_value("Buena")
                get(app.text_input, "Ecuación o familia de referencia").set_value("GLI")
                get(app.text_input, "Versión o año de la ecuación").set_value("2012")
                app.checkbox[0].check()
                values = ({"FEV1_pre": 2.210, "FEV1_pred": 2.7800, "FEV1_lln": 2.1741, "FEV1_zpre": -1.55}
                          if case == "GLI" else
                          {"FEV1_pre": 2.00, "FEV1_pred": 3.32, "FEV1_post": 2.40})
                if case == "ERS/ATS":
                    get(app.selectbox, "Tipo de estudio").set_value("Espirometría pre y post broncodilatador")
                    app.checkbox[1].check()
                for label, value in values.items():
                    get(app.number_input, label).set_value(value)
                get(app.button, "Preparar borrador para revisión").click().run()
                self.assertFalse(app.exception)
                report_params = app.session_state["report_snapshot"][2]
                report = app.session_state["report_snapshot"][3]
                preview_row = app.dataframe[0].value.query("Parámetro == 'FEV1'").iloc[0]
                csv_frame = build_values_dataframe(report_params, include_post=case == "ERS/ATS")
                if case == "GLI":
                    self.assertEqual(preview_row["LLN"], 2.1741)
                    self.assertEqual(preview_row["Z Pre"], -1.55)
                    self.assertFalse(is_below_lln(report_params["FEV1"]))
                    # Published GLI fixture is a single parameter, not a diagnosis.
                    self.assertEqual(report["pattern"], "No clasificable automáticamente")
                    csv_columns = ("Pre", "Predicho", "LLN", "Z Pre")
                    expected = (2.210, 2.7800, 2.1741, -1.55)
                else:
                    self.assertIn("+12.05%", report["technical_report"])
                    self.assertIn("Positiva (ERS/ATS)", report["bronchodilator"])
                    self.assertNotIn("GINA", report["technical_report"])
                    csv_columns = ("Pre", "Predicho", "Post")
                    expected = (2.00, 3.32, 2.40)
                csv_rows = csv.DictReader(io.StringIO(csv_frame.to_csv(index=False)))
                csv_row = next(row for row in csv_rows if row["Parámetro"] == "FEV1")
                self.assertEqual(tuple(float(csv_row[name]) for name in csv_columns), expected)

                get(app.checkbox, "He revisado la identidad, los valores y anexos del estudio, y la conclusión.").check()
                get(app.button, "Confirmar revisión y preparar PDF de prueba").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.get("download_button")), 2)
                pdf = app.session_state["report_export"][0]
                content = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
                for part in (("2.2100", "2.7800", "2.1741", "-1.550", "79.5")
                             if case == "GLI" else ("+12.05%", "Positiva (ERS/ATS)")):
                    self.assertIn(part, content)


if __name__ == "__main__":
    unittest.main()
