# ESPIROMETRÍA PRO - TABLA COMPLETA CON PRE1 PRE2 PRE3 BEST

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Espirometría PRO", layout="wide")

def build_table(params):
    rows = []

    for name, data in params.items():
        pre_vals = [data["pre1"], data["pre2"], data["pre3"]]
        pre_clean = [v for v in pre_vals if v not in (None, 0)]

        best = max(pre_clean) if pre_clean else None

        pred = data.get("pred")
        post = data.get("post")

        pct = (best / pred * 100) if best and pred else None
        delta = ((post - best) / best * 100) if best and post else None

        rows.append({
            "Parámetro": name,
            "Pre1": data["pre1"],
            "Pre2": data["pre2"],
            "Pre3": data["pre3"],
            "Best": best,
            "Predicho": pred,
            "%Pred": pct,
            "Post": post,
            "Δ%": delta
        })

    return pd.DataFrame(rows)

st.title("🫁 Espirometría PRO")

st.subheader("Ingreso de datos")

params = {}

param_list = ["FVC","FEV1","FEV1/FVC","PEF","FEF25","FEF50","FEF75","FEF25-75"]

for p in param_list:
    st.markdown(f"### {p}")
    c1,c2,c3,c4,c5 = st.columns(5)
    pre1 = c1.number_input(f"{p} PRE1", key=p+"1")
    pre2 = c2.number_input(f"{p} PRE2", key=p+"2")
    pre3 = c3.number_input(f"{p} PRE3", key=p+"3")
    pred = c4.number_input(f"{p} Predicho", key=p+"4")
    post = c5.number_input(f"{p} Post", key=p+"5")

    params[p] = {
        "pre1": pre1,
        "pre2": pre2,
        "pre3": pre3,
        "pred": pred,
        "post": post
    }

if st.button("Generar tabla"):
    df = build_table(params)
    st.dataframe(df, use_container_width=True)

    now = datetime.now(ZoneInfo("America/Bogota"))
    st.caption(now.strftime("%d/%m/%Y %H:%M"))