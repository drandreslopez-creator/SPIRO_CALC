# (Archivo corregido resumido SOLO en sección problemática)

# REEMPLAZA SOLO ESTA PARTE EN TU ARCHIVO:

c7, c8, c9, c10 = st.columns(4)

peso = c7.number_input("Peso (kg)", min_value=0.0, step=0.1, value=None, placeholder="Ej. 18.5")
talla = c8.number_input("Talla (cm)", min_value=0.0, step=0.1, value=None, placeholder="Ej. 108")

grupo_etnico = c9.selectbox(
    "Grupo étnico",
    ["", "Latino", "Caucásico", "Afrodescendiente", "Asiático", "Otro"]
)

fumador = c10.selectbox(
    "¿Fuma?",
    ["No", "Exfumador", "Sí"]
)

# NUEVA FILA
c11, c12 = st.columns(2)

fecha_estudio = c11.date_input(
    "Fecha del estudio",
    value=date.today(),
    min_value=date(1900,1,1),
    max_value=date.today(),
    format="DD/MM/YYYY"
)

id_tipo = c12.selectbox(
    "Tipo de documento",
    ["CC", "TI", "RC", "CE", "Pasaporte", "Otro"]
)


# Y TAMBIÉN CORRIGE ESTO:

patient_dict = {
    "nombre": nombre,
    "identificacion": f"{id_tipo} {identificacion}".strip(),
    "fecha_nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if isinstance(fecha_nacimiento, date) else "",
    "edad": edad_txt,
    "sexo": sexo,
    "eps": eps,
    "peso": f"{peso:.1f} kg" if peso is not None else "",
    "talla": f"{talla:.1f} cm" if talla is not None else "",
    "remitente": remitente,
    "grupo_etnico": grupo_etnico,
    "fumador": fumador,
}
