import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Espirometría Pro", layout="centered")

st.title("🫁 Espirometría con Z-score automático (versión clínica)")

# -------------------------
# INPUTS
# -------------------------
edad = st.number_input("Edad (años)", 5, 90, 30)
sexo = st.selectbox("Sexo", ["Masculino", "Femenino"])
talla = st.number_input("Talla (cm)", 100, 210, 170)

fev1 = st.number_input("FEV1 (L)", 0.5, 6.0, 2.5)
fvc = st.number_input("FVC (L)", 0.5, 7.0, 3.5)

# -------------------------
# PREDICCIÓN SIMPLIFICADA (tipo GLI aproximado)
# -------------------------
if sexo == "Masculino":
    fev1_pred = (0.041 * talla) - (0.024 * edad) - 2.190
    fvc_pred = (0.052 * talla) - (0.028 * edad) - 3.200
else:
    fev1_pred = (0.034 * talla) - (0.025 * edad) - 1.578
    fvc_pred = (0.041 * talla) - (0.026 * edad) - 2.600

# SD aproximada (GLI usa LMS, aquí simplificado)
sd = 0.5

z_fev1 = (fev1 - fev1_pred) / sd
z_fvc = (fvc - fvc_pred) / sd

ratio = fev1 / fvc

# -------------------------
# INTERPRETACIÓN (ATS/ERS moderna)
# -------------------------
if ratio < 0.7:
    if z_fvc < -1.64:
        patron = "Mixto"
    else:
        patron = "Obstructivo"
elif z_fvc < -1.64:
    patron = "Restrictivo probable"
else:
    patron = "Normal"

# -------------------------
# RESULTADOS
# -------------------------
st.subheader("Resultados")

st.write(f"**FEV1 predicho:** {fev1_pred:.2f} L")
st.write(f"**FVC predicho:** {fvc_pred:.2f} L")

st.write(f"**Z-score FEV1:** {z_fev1:.2f}")
st.write(f"**Z-score FVC:** {z_fvc:.2f}")

st.write(f"**Relación FEV1/FVC:** {ratio:.2f}")

st.subheader("Interpretación")
st.success(f"Patrón: {patron}")

# -------------------------
# GRÁFICO CLÍNICO (Z-SCORE)
# -------------------------
st.subheader("Visualización clínica (Z-score)")

fig, ax = plt.subplots()

labels = ["FEV1", "FVC"]
values = [z_fev1, z_fvc]

ax.bar(labels, values)

ax.axhline(-1.64, linestyle='--')  # LLN
ax.axhline(0)

ax.set_ylabel("Z-score")
ax.set_title("Evaluación funcional")

st.pyplot(fig)

# -------------------------
# EXPLICACIÓN
# -------------------------
st.subheader("Explicación clínica")

if z_fev1 < -1.64:
    st.write("• FEV1 disminuido → compromiso funcional")

if z_fvc < -1.64:
    st.write("• FVC disminuida → sugiere restricción")

if ratio < 0.7:
    st.write("• Relación baja → obstrucción")
