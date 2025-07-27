import streamlit as st
import pandas as pd
import pydeck as pdk
import pickle
from datetime import datetime

st.set_page_config(page_title="Parking in Dresden - Model Inputs", layout="wide")

# --- Modell laden und Inputs anzeigen ---
model_file = st.file_uploader("Upload your model (.pkl)", type=["pkl"])

if model_file is not None:
    model = pickle.load(model_file)
    st.subheader("Model Info")
    st.write(model)

    if hasattr(model, "feature_names_in_"):
        st.success("Das Modell erwartet folgende Features:")
        st.write(list(model.feature_names_in_))
    elif hasattr(model, "n_features_in_"):
        st.warning("Keine Feature-Namen gespeichert. Das Modell erwartet {} Features.".format(model.n_features_in_))
    else:
        st.error("Das Modell enthält keine Informationen über die erwarteten Inputs.")
else:
    st.info("Bitte lade eine .pkl Datei hoch, um die erwarteten Inputs zu sehen.")
