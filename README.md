# App de Espirometría – Dr. Andrés López Ruiz

Aplicación en Streamlit para generar reportes de espirometría con:

- datos completos del paciente
- tabla de valores pre y post broncodilatador
- interpretación técnica automática
- comentario médico orientativo
- inserción de imágenes de curvas
- anexo opcional de PDF exportado por el espirómetro
- descarga del reporte final en PDF

## Estructura esperada

```text
espirometria_app/
├── app.py
├── logo.png
├── requirements.txt
└── README.md
```

## Cómo ejecutarla

1. Abra la terminal en la carpeta del proyecto.
2. Instale dependencias:

```bash
pip install -r requirements.txt
```

3. Inicie la app:

```bash
streamlit run app.py
```

## Personalización

- Reemplace `logo.png` si en el futuro desea cambiar el logo.
- La firma no está incrustada en el PDF para permitir sello o firma manual al imprimir.
- El encabezado está configurado como consultorio privado, no como IPS independiente.

## Notas

- La interpretación automática es una ayuda clínica y no reemplaza la valoración médica.
- Si el espirómetro exporta un PDF, la app lo agrega al final como anexo cuando sea posible.
