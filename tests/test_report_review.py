import io
import unittest

from services.pdf_generator import make_pdf
from services.spirometry_logic import ParameterResult

from services.report_review import (
    MAX_CLINICAL_COMMENT,
    reviewed_interpretation,
    suggest_clinical_comment,
)


class ReportReviewTests(unittest.TestCase):
    assessment = {
        "pattern": "FVC baja con relación FEV1/FVC conservada",
        "medical_comment": "Sugiere posible restricción, que requiere confirmación con TLC.",
        "bronchodilator": "No realizado",
    }

    def test_default_draft_preserves_limitation(self):
        result = suggest_clinical_comment(self.assessment)
        self.assertIn("posible restricción", result)
        self.assertIn("confirmación con TLC", result)

    def test_clinical_edit_does_not_change_calculated_result(self):
        result = reviewed_interpretation(self.assessment, "  Texto revisado.  ", True)
        self.assertEqual(result["reviewed_clinical_comment"], "Texto revisado.")
        self.assertEqual(result["pattern"], self.assessment["pattern"])
        self.assertEqual(result["bronchodilator"], self.assessment["bronchodilator"])
        self.assertNotIn("reviewed_clinical_comment", self.assessment)

    def test_explicit_confirmation_required(self):
        with self.assertRaises(ValueError):
            reviewed_interpretation(self.assessment, "Texto", False)

    def test_requires_a_bounded_nonempty_comment(self):
        for comment in ("   ", "a" * (MAX_CLINICAL_COMMENT + 1)):
            with self.subTest(comment=comment), self.assertRaises(ValueError):
                reviewed_interpretation(self.assessment, comment, True)

    def test_corrupt_device_pdf_is_not_silently_omitted(self):
        with self.assertRaisesRegex(ValueError, "No se pudo incorporar el PDF del equipo"):
            params = {"FEV1": ParameterResult("FEV1", "L", 1.0, None, None, None, None, None)}
            make_pdf({"nombre": "Caso sintético"}, {}, params, self.assessment,
                     {"curve_pdf": io.BytesIO(b"not a PDF")})
