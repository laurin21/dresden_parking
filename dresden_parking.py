import streamlit as st
import pickle
import glob
from datetime import datetime, timedelta

st.set_page_config(page_title="Parking Model Inputs", layout="wide")

# --- Parkplatznamen und Modell-Dateien ---
pkl_files = glob.glob("xgb_model_*.pkl")
parking_names = [f.replace("xgb_model_", "").replace(".pkl", "") for f in pkl_files]

if not pkl_files:
    st.warning("Keine .pkl-Dateien im aktuellen Verzeichnis gefunden.")
else:
    # Dropdown für Parkplatzname -> gleichzeitig Modellwahl
    selected_name = st.selectbox("Name des Parkplatzes", parking_names)
    selected_file = f"xgb_model_{selected_name}.pkl"

    with open(selected_file, "rb") as f:
        model = pickle.load(f)

    # --- Zeitfeatures automatisch bestimmen + Slider für Blick in Zukunft ---
    st.subheader("Zeiteinstellungen")
    minutes_ahead = st.slider("Vorhersagezeitraum (in Minuten, bis 48h)", min_value=0, max_value=48*60, value=0, step=5)
    prediction_time = datetime.now() + timedelta(minutes=minutes_ahead)

    hour = prediction_time.hour
    minute_of_day = prediction_time.hour * 60 + prediction_time.minute
    weekday = prediction_time.weekday()
    is_weekend = 1 if weekday >= 5 else 0
    is_holiday = 0  # Platzhalter: echte Feiertagslogik kann hier ergänzt werden

    # Eingaben für Modell (ohne Zeitfeatures)
    st.subheader("Eingaben für Modell (ohne Zeitfeatures)")
    capacity = st.number_input("Kapazität", min_value=0, max_value=10000, step=1)
    temperature = st.number_input("Temperatur (°C)", value=20.0)
    description = st.selectbox("Wetterbeschreibung", ["Clear", "Cloudy", "Rain", "Snow"])
    humidity = st.slider("Luftfeuchtigkeit (%)", min_value=0, max_value=100, value=50)
    rain = st.number_input("Regen (mm)", value=0.0)
    district = st.text_input("Stadtbezirk", "")
    type_ = st.selectbox("Parkplatztyp", ["Tiefgarage", "Parkhaus", "Freifläche"])
    final_avg_occ = st.number_input("Durchschnittliche Belegung (%)", min_value=0.0, max_value=100.0, value=50.0)
    in_event_window = st.selectbox("In Event-Fenster?", [0, 1])
    event_size = st.number_input("Eventgröße (Personen)", min_value=0, max_value=100000, step=100)
    distance_to_nearest_parking = st.number_input("Entfernung zum nächsten Parkplatz (m)", min_value=0.0, max_value=5000.0, value=100.0)

    st.markdown("---")
    st.write("**Zusammenfassung der Eingaben:**")
    inputs = {
        "Name": selected_name,
        "Capacity": capacity,
        "Temperature": temperature,
        "Description": description,
        "Humidity": humidity,
        "Rain": rain,
        "District": district,
        "Type": type_,
        "final_avg_occ": final_avg_occ,
        "in_event_window": in_event_window,
        "event_size": event_size,
        "distance_to_nearest_parking": distance_to_nearest_parking,
        "hour": hour,
        "minute_of_day": minute_of_day,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday
    }
    st.json(inputs)

    # --- Debugging Mode ---
    st.markdown("---")
    if st.toggle("Debugging Mode"):
        st.subheader("Debugging Informationen")
        st.write(model)
        if hasattr(model, "feature_names_in_"):
            st.success("Das Modell erwartet folgende Features:")
            st.write(list(model.feature_names_in_))
        if hasattr(model, "feature_types_"):
            st.success("Datentypen der Features laut Modell:")
            st.write(list(model.feature_types_))
        elif hasattr(model, "n_features_in_"):
            st.warning(f"Keine Feature-Typen gespeichert. Das Modell erwartet {model.n_features_in_} Features.")
        else:
            st.error("Das Modell enthält keine Informationen über die erwarteten Inputs.")
