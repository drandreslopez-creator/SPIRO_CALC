"""Declara el alcance del estudio antes de generar derivados o exportar."""
from datetime import date

SIMPLE_STUDY = "Espirometría simple"
POST_STUDY = "Espirometría pre y post broncodilatador"


def has_post_phase(study_type):
    return study_type == POST_STUDY


def conflicting_study_dates(dob, study_date):
    return isinstance(dob, date) and isinstance(study_date, date) and dob > study_date


def reference_provenance(equation, version):
    """La procedencia se declara, no se valida contra un catálogo local."""
    def clean(value):
        value = " ".join(value.split()) if isinstance(value, str) else ""
        if value.casefold() in {
            "", "-", "—", "?", "no sé", "no se", "n/a", "na", "s/d", "sin dato",
            "ninguna", "ninguno", "desconocida", "desconocido", "no disponible",
            "no consta", "no aplica", "sin verificar", "pendiente"
        } or not any(c.isalnum() for c in value):
            return ""
        return value

    equation, version = clean(equation), clean(version)
    return f"{equation} | {version}" if equation and version else None


def scoped_rows(rows, include_post):
    """Una sesión simple no debe reutilizar datos post de widgets anteriores."""
    if include_post:
        return rows
    return {name: {**row, "post": None, "zpost": None} for name, row in rows.items()}
