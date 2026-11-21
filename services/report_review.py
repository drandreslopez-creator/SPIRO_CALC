"""Local text templates and the explicit human-review gate. No model/API calls."""

MAX_CLINICAL_COMMENT = 900


def suggest_clinical_comment(assessment):
    """Draft from the calculated assessment, never from identifying/free-text fields."""
    pattern, detail = (assessment[k].rstrip(". ") for k in ("pattern", "medical_comment"))
    return f"{pattern}. {detail}. Correlacionar con los hallazgos clínicos."


def reviewed_interpretation(assessment, clinical_comment, confirmed):
    """Keep the calculated findings distinct from any clinician-authored conclusion."""
    if confirmed is not True:
        raise ValueError("Confirma la revisión del estudio antes de generar el informe.")
    comment = clinical_comment.strip()
    if not comment:
        raise ValueError("Ingresa la conclusión clínica revisada antes de generar el informe.")
    if len(comment) > MAX_CLINICAL_COMMENT:
        raise ValueError(f"La conclusión admite hasta {MAX_CLINICAL_COMMENT} caracteres.")
    return {**assessment, "reviewed_clinical_comment": comment}
