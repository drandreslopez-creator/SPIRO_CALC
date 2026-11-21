import io
import unittest
from datetime import date

from pypdf import PdfReader

from services.interpretation import build_interpretation
from services.pdf_generator import build_values_dataframe, make_pdf
from services.spirometry_logic import parameters_from_entered_values
from services.study_guard import (
    POST_STUDY, SIMPLE_STUDY, conflicting_study_dates,
    has_post_phase, reference_provenance, scoped_rows,
)


class StudyGuardTest(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "FEV1": dict(unit="L", pre=1.8, pred=2, lln=1.4, zpre=-0.83, post=7.77, zpost=8.88),
            "FVC": dict(unit="L", pre=2.4, pred=2.5, lln=1.8, zpre=None, post=None, zpost=None),
            "FEV1/FVC": dict(unit="%", pre=75, pred=83, lln=72, zpre=None, post=None, zpost=None),
        }

    def test_study_dates(self):
        study_date = date(2026, 11, 20)
        self.assertTrue(conflicting_study_dates(date(2026, 11, 21), study_date))
        self.assertFalse(conflicting_study_dates(study_date, study_date))
        self.assertFalse(conflicting_study_dates(None, study_date))

    def test_declared_equation_and_version_both_needed(self):
        self.assertEqual(reference_provenance("  GLI    Global  ", " 2022 "), "GLI Global | 2022")
        for equation, version in [(None, "2022"), ("GLI", ""), ("GLI", "N/A"),
                                  ("No sé", "2022"), ("GLI", "  --- ")]:
            with self.subTest(equation=equation, version=version):
                self.assertIsNone(reference_provenance(equation, version))

    def test_simple_scope_ignores_stale_post_even_with_post_quality(self):
        self.assertFalse(has_post_phase(SIMPLE_STUDY))
        self.assertTrue(has_post_phase(POST_STUDY))
        params = parameters_from_entered_values(scoped_rows(self.raw, include_post=False))
        self.assertEqual(self.raw["FEV1"]["post"], 7.77)
        self.assertIsNone(params["FEV1"].measured_post)
        self.assertIsNone(params["FEV1"].zscore_post)
        self.assertIsNone(params["FEV1"].delta_abs)
        result = build_interpretation(
            11, params, "Datos ficticios", calidad="Aceptable",
            reproducibilidad="Adecuada", cooperacion="Buena",
            referencia_verificada=True, calidad_post_confirmada=True,
        )
        self.assertEqual(result["bronchodilator"], "No realizado")
        self.assertNotIn("GINA", result["technical_report"])

    def test_simple_export_drops_post_even_if_parameters_have_it(self):
        params = parameters_from_entered_values(scoped_rows(self.raw, include_post=True))
        self.assertIn("Post", build_values_dataframe(params).columns)
        self.assertEqual(
            set(build_values_dataframe(params, include_post=False).columns),
            {"Parámetro", "Unidad", "Pre", "Predicho", "%Pred Pre", "LLN", "Z Pre"},
        )
        pdf = make_pdf(
            {"nombre": "Caso sintético"},
            {"tipo_estudio": SIMPLE_STUDY, "referencia": "GLI & Global | 2022",
             "referencia_verificada": True, "include_post": False,
             "broncodilatador": "Medicamento de prueba", "tiempo_post": "Prueba"},
            params, {"technical_report": "Calidad verificada.", "bronchodilator": "No aplica"},
            {},
        )
        rendered = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("GLI & Global | 2022", rendered)
        self.assertIn("Procedencia confirmada", rendered)
        for excluded in ("7.77", "8.88", "Z Post", "Tiempo post-BD",
                         "Medicamento de prueba", "Respuesta broncodilatadora"):
            self.assertNotIn(excluded, rendered)


if __name__ == "__main__":
    unittest.main()
