import streamlit as st
import pandas as pd
import pydeck as pdk
import pickle
import glob
from datetime import datetime

st.set_page_config(page_title="Parking in Dresden - Model Inputs", layout="wide")

# --- Suche nach pkl-Dateien im aktuellen Repo ---
pkl_files = glob.glob("*.pkl")

if not pkl_files:
    st.warning("Keine .pkl-Dateien im aktuellen Verzeichnis gefunden.")
else:
    st.subheader("Gefundene Modelle")
    for file in pkl_files:
        st.write(file)
    selected_file = st.selectbox("Wähle ein Modell:", pkl_files)

    if selected_file:
        with open(selected_file, "rb") as f:
            model = pickle.load(f)
        st.subheader("Model Info")
        st.write(model)

        # Eingabe-Features anzeigen
        if hasattr(model, "feature_names_in_"):
            st.success("Das Modell erwartet folgende Features:")
            st.write(list(model.feature_names_in_))
        elif hasattr(model, "n_features_in_"):
            st.warning(f"Keine Feature-Namen gespeichert. Das Modell erwartet {model.n_features_in_} Features.")
        else:
            st.error("Das Modell enthält keine Informationen über die erwarteten Inputs.")