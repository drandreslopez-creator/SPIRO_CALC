import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# 🔐 CONFIG
SHEET_NAME = "Espirometrías"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json", scope
)

client = gspread.authorize(creds)
spreadsheet = client.open(SHEET_NAME)

patients_sheet = spreadsheet.worksheet("pacientes")
reports_sheet = spreadsheet.worksheet("reportes")


# ----------------------------
# PACIENTES
# ----------------------------
def save_patient(nombre, identificacion, fecha_nacimiento, sexo):

    data = patients_sheet.get_all_records()

    for row in data:
        if row["identificacion"] == identificacion:
            return row["id"]

    new_id = len(data) + 1

    patients_sheet.append_row([
        new_id,
        nombre,
        identificacion,
        fecha_nacimiento,
        sexo
    ])

    return new_id


# ----------------------------
# REPORTES
# ----------------------------
def save_spirometry(patient_id, interpretation):

    reports_sheet.append_row([
        patient_id,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        interpretation.get("pattern"),
        interpretation.get("severity"),
        interpretation.get("semaforo"),
        interpretation.get("result"),
        interpretation.get("medical_comment"),
    ])


# ----------------------------
# CONSULTAS
# ----------------------------
def get_all_patients():
    data = patients_sheet.get_all_records()
    return [(row["id"], row["nombre"], row["identificacion"]) for row in data]


def get_patient_reports(patient_id):
    data = reports_sheet.get_all_records()

    return [
        (
            row["fecha"],
            row["pattern"],
            row["severity"],
            row["semaforo"],
            row["resultado"],
            row["comentario"],
        )
        for row in data
        if row["patient_id"] == patient_id
    ]
