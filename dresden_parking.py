import streamlit as st
import pandas as pd
import pydeck as pdk
import pickle
import glob
import io
import pickletools
from datetime import datetime

st.set_page_config(page_title="Parking in Dresden - Model Inputs", layout="wide")

# --- Roh-Analyse von pkl-Dateien ohne externe Bibliotheken ---
def analyze_pickle_structure(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read()
    info = io.StringIO()
    pickletools.dis(raw, out=info)
    return info.getvalue()

# --- Suche nach pkl-Dateien ---
pkl_files = glob.glob("*.pkl")

if not pkl_files:
    st.warning("Keine .pkl-Dateien im aktuellen Verzeichnis gefunden.")
else:
    st.subheader("Gefundene Modelle")
    for file in pkl_files:
        st.write(file)
    selected_file = st.selectbox("Wähle ein Modell:", pkl_files)

    if selected_file:
        st.subheader("Pickle Struktur Analyse")
        structure_info = analyze_pickle_structure(selected_file)
        st.text(structure_info)
        st.info("Diese Rohanalyse zeigt die Struktur, auch wenn bestimmte Bibliotheken fehlen.")
