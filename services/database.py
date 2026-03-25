import sqlite3
from datetime import datetime

DB_NAME = "spirometry.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        identificacion TEXT UNIQUE,
        fecha_nacimiento TEXT,
        sexo TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS spirometry_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        fecha TEXT,
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


def save_patient(nombre, identificacion, fecha_nacimiento, sexo):
    conn = get_connection()
    cursor = conn.cursor()

    # 🔥 Buscar si ya existe
    cursor.execute("SELECT id FROM patients WHERE identificacion = ?", (identificacion,))
    result = cursor.fetchone()

    if result:
        conn.close()
        return result[0]

    # 🔥 Insertar nuevo paciente
    cursor.execute("""
    INSERT INTO patients (nombre, identificacion, fecha_nacimiento, sexo)
    VALUES (?, ?, ?, ?)
    """, (nombre, identificacion, fecha_nacimiento, sexo))

    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()

    return patient_id


def save_spirometry(patient_id, interpretation):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO spirometry_reports (
        patient_id, fecha, pattern, severity, semaforo, resultado, comentario
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        interpretation.get("pattern"),
        interpretation.get("severity"),
        interpretation.get("semaforo"),
        interpretation.get("result"),
        interpretation.get("medical_comment"),
    ))

    conn.commit()
    conn.close()


# ----------------------------
# 🔥 CONSULTAS (HISTORIAL)
# ----------------------------

def get_all_patients():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre, identificacion FROM patients ORDER BY nombre")
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