import ast
from datetime import date
from pathlib import Path
from typing import Optional
import unittest

from services.interpretation import build_interpretation
from services.spirometry_logic import parameters_from_entered_values


def rows():
    def entry(unit, pre, pred, lln, post=None, zpre=None, zpost=None):
        return dict(unit=unit, pre=pre, pred=pred, lln=lln, post=post, zpre=zpre, zpost=zpost)
    return {"FEV1": entry("L", 1.48, 2, 1.401, zpre=-1.548, zpost=0.0),
            "FVC": entry("L", 1.90, 2.45, 1.7),
            "FEV1/FVC": entry("%", 78, 90, 78)}


def report(data=None, age=12, **overrides):
    gates = dict(calidad="Aceptable", reproducibilidad="Adecuada", cooperacion="Buena",
                 referencia_verificada=True, calidad_post_confirmada=True)
    gates.update(overrides)
    return build_interpretation(age, parameters_from_entered_values(data or rows()),
                                "Estudio sintético.", **gates)


class ClinicalReferencesTest(unittest.TestCase):
    def test_manual_values_preserved_no_percent_fallback(self):
        p = parameters_from_entered_values(rows())["FEV1"]
        self.assertEqual((p.lln, p.zscore_pre, p.zscore_post), (1.401, -1.548, 0))
        self.assertTrue(report()["semaforo"].startswith("🟢"))

    def test_manual_ratio_can_detect_obstruction(self):
        data = rows()
        data["FEV1/FVC"]["lln"] = 80
        self.assertIn("obstructivo", report(data)["pattern"])
        data["FVC"]["lln"] = 2
        self.assertIn("TLC", report(data)["medical_comment"])

    def test_low_fvc_not_confirmed_restriction(self):
        data = rows()
        data["FVC"]["lln"] = 2
        self.assertIn("posible restricción", report(data)["medical_comment"])
        self.assertIn("TLC", report(data)["medical_comment"])

    def test_isolated_fev1_low_not_normal(self):
        data = rows()
        data["FEV1"]["lln"] = 1.49
        self.assertIn("FEV1 bajo", report(data)["pattern"])
        self.assertFalse(report(data)["semaforo"].startswith("🟢"))

    def test_missing_or_invalid_input_never_normal(self):
        for name, field, value in [("FEV1", "lln", None), ("FVC", "pre", None),
                                   ("FEV1/FVC", "lln", 0.78), ("FEV1/FVC", "pre", float("nan"))]:
            with self.subTest(name=name, field=field):
                data = rows()
                data[name][field] = value
                self.assertEqual(report(data)["pattern"], "No clasificable automáticamente")

    def test_quality_and_reference_gates(self):
        for kwargs in [dict(calidad="Sin verificar"), dict(calidad="No aceptable"),
                       dict(referencia_verificada=False), dict(cooperacion="Regular")]:
            self.assertEqual(report(**kwargs)["pattern"], "No clasificable automáticamente")

    def test_denominator_and_boundaries(self):
        data = rows()
        data["FEV1"].update(pre=.80, pred=1.50, post=.92)
        data["FVC"]["post"] = 1.90
        self.assertEqual(report(data)["bronchodilator"], "No cumple el criterio (ERS/ATS)")
        for post, status, gina in [(.95, "No cumple el criterio (ERS/ATS)", "no cumple"),
                                   (.96, "Positiva (ERS/ATS)", "no cumple"),
                                   (.98, "Positiva (ERS/ATS)", "cumple")]:
            data["FEV1"]["post"] = post
            result = report(data)
            self.assertEqual(result["bronchodilator"], status)
            self.assertIn(f"criterio espirométrico: {gina}", result["technical_report"])
        self.assertNotIn("GINA", report(data, age=5)["technical_report"])
        self.assertNotIn("GINA", report(data, age=18)["technical_report"])

    def test_fvc_only_positive_and_partial_negative(self):
        data = rows()
        data["FVC"].update(pre=1.9, pred=2.45, post=2.2)
        self.assertEqual(report(data)["bronchodilator"], "Positiva (ERS/ATS)")
        self.assertIn("no evaluable por datos", report(data)["technical_report"])
        data["FVC"]["post"] = 1.9
        self.assertEqual(report(data)["bronchodilator"], "No evaluable (ERS/ATS)")
        self.assertEqual(report(data, calidad_post_confirmada=False)["bronchodilator"], "No evaluable")

    def test_study_date_exact_completed_age_without_importing_app(self):
        tree = ast.parse(Path("app.py").read_text())
        helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "age_in_years"]
        ns = dict(date=date, Optional=Optional)
        exec(compile(ast.Module(body=helpers, type_ignores=[]), "app.py", "exec"), ns)
        age_at = ns["age_in_years"]
        self.assertEqual(age_at(date(2008, 11, 21), date(2026, 11, 20)), 17)
        self.assertEqual(age_at(date(2008, 11, 21), date(2026, 11, 21)), 18)
        self.assertIsNone(age_at(date(2026, 11, 21), date(2026, 11, 20)))


if __name__ == "__main__":
    unittest.main()
