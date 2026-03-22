import streamlit as st
from services.spirometry_logic import ParameterResult
from utils.calculations import calculate_zscore
from services.interpretation import build_interpretation
from services.pdf_generator import generate_pdf

st.title("Espirometría PRO")

fev1 = st.number_input("FEV1")
fvc = st.number_input("FVC")
ratio = st.number_input("FEV1/FVC")

if st.button("Calcular"):

    params = {
        "FEV1": ParameterResult("FEV1", "L", fev1, None, 3.0, 2.5, None, None),
        "FVC": ParameterResult("FVC", "L", fvc, None, 3.5, 2.8, None, None),
        "FEV1/FVC": ParameterResult("FEV1/FVC", "%", ratio, None, 80, 70, None, None),
    }

    resultado = build_interpretation(None, params)

    st.success(resultado)

    pdf = generate_pdf(resultado)
    st.download_button(
    "Descargar PDF",
    data=pdf,
    file_name="reporte_espirometria.pdf",
    mime="application/pdf"
)
