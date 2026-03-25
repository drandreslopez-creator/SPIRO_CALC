import sqlite3
from datetime import datetime

DB_NAME = "spirometry.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------
    # TABLA PACIENTES
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        identificacion TEXT UNIQUE,
        fecha_nacimiento TEXT,
        sexo TEXT
    )
    """)

    # ----------------------------
    # TABLA ESPIROMETRÍAS (CON FEV1 PARA EVOLUCIÓN)
    # ----------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS spirometry_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        fecha TEXT,

        fev1 REAL,
        fvc REAL,
        ratio REAL,

        pattern TEXT,
        severity TEXT,
        semaforo TEXT,
        resultado TEXT,
        comentario TEXT,

        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )
    """)

    conn.commit()
    conn.close()


# ----------------------------
# GUARDAR PACIENTE
# ----------------------------
def save_patient(nombre, identificacion, fecha_nacimiento, sexo):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM patients WHERE identificacion = ?",
        (identificacion,)
    )
    result = cursor.fetchone()

    if result:
        conn.close()
        return result[0]

    cursor.execute("""
    INSERT INTO patients (nombre, identificacion, fecha_nacimiento, sexo)
    VALUES (?, ?, ?, ?)
    """, (nombre, identificacion, fecha_nacimiento, sexo))

    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()

    return patient_id


# ----------------------------
# GUARDAR ESPIROMETRÍA
# ----------------------------
def save_spirometry(patient_id, interpretation, params):
    conn = get_connection()
    cursor = conn.cursor()

    fev1 = params["FEV1"].measured_pre if "FEV1" in params else None
    fvc = params["FVC"].measured_pre if "FVC" in params else None
    ratio = params["FEV1/FVC"].measured_pre if "FEV1/FVC" in params else None

    cursor.execute("""
    INSERT INTO spirometry_reports (
        patient_id, fecha, fev1, fvc, ratio, pattern, severity, semaforo, resultado, comentario
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        fev1,
        fvc,
        ratio,
        interpretation.get("pattern"),
        interpretation.get("severity"),
        interpretation.get("semaforo"),
        interpretation.get("result"),
        interpretation.get("medical_comment"),
    ))

    conn.commit()
    conn.close()


# ----------------------------
# CONSULTAS
# ----------------------------
def get_all_patients():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, nombre, identificacion
    FROM patients
    ORDER BY nombre
    """)

    data = cursor.fetchall()
    conn.close()
    return data


def get_patient_reports(patient_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT fecha, pattern, severity, semaforo, resultado, comentario
    FROM spirometry_reports
    WHERE patient_id = ?
    ORDER BY fecha DESC
    """, (patient_id,))

    data = cursor.fetchall()
    conn.close()
    return data


# ----------------------------
# 📈 EVOLUCIÓN
# ----------------------------
def get_patient_evolution(patient_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT fecha, fev1
    FROM spirometry_reports
    WHERE patient_id = ?
    ORDER BY fecha
    """, (patient_id,))

    data = cursor.fetchall()
    conn.close()
    return data
