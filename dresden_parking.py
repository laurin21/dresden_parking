import streamlit as st
import pickle
import glob
from datetime import datetime, timedelta, date
import holidays
import pandas as pd
import folium
import pydeck as pdk
from streamlit_folium import st_folium

st.set_page_config(page_title="Parking Model Inputs", layout="wide")

# --- Parkplatznamen und Mapping auf Eingabewerte ---
pkl_files = glob.glob("xgb_model_*.pkl")
parking_names = [f.replace("xgb_model_", "").replace(".pkl", "") for f in pkl_files]


# Mapping der Koordinaten aus bereitgestellten Daten
coordinates_mapping = {
    "Altmarkt": (13.7417891, 51.05067008),
    "Altmarkt - Galerie": (13.73787803, 51.04676432),
    "An der Frauenkirche": (13.74419347, 51.05141507),
    "Budapester Straße": (13.730277, 51.046519),
    "Centrum - Galerie": (13.73394691, 51.04537162),
    "Cossebaude": (13.632377, 51.0852),
    "Ferdinandplatz": (13.73963711, 51.04588257),
    "Fidelio-F.-Finke-Straße": (13.814272, 51.052679),
    "Frauenkirche / Neumarkt": (13.7308651, 51.05900197),
    "GALERIA Karstadt Kaufhof": (13.73804453, 51.04676432),
    "Grenzstraße": (13.776393, 51.12798),
    "Haus am Zwinger": (13.7357789, 51.05141429),
    "Kaditz": (13.69100924, 51.08130555),
    "Klotzsche": (13.789227, 51.115823),
    "Kongresszentrum": (13.73118775, 51.04197071),
    "Langebrück": (13.840873, 51.127132),
    "MESSE DRESDEN Parkplatz P7": (13.71950558, 51.06746291),
    "Ostra-Ufer": (13.728648, 51.060423),
    "Parkhaus Mitte": (13.72611015, 51.05814122),
    "Pennrich": (13.626586, 51.0406),
    "Pieschener Allee Bus": (13.728977, 51.061748),
    "Pirnaischer Platz": (13.74356808, 51.0481722),
    "Prohlis": (13.79944738, 50.99940802),
    "Reick": (13.790173, 51.021124),
    "Reitbahnstraße": (13.73342566, 51.04356811),
    "SachsenEnergie Center": (13.73085214, 51.03859607),
    "Sarrasanistraße": (13.74502398, 51.05762661),
    "Schießgasse": (13.74450534, 51.0504296),
    "Semperoper": (13.73395773, 51.05543977),
    "SP1 Straßburger Platz": (13.756661, 51.046848),
    "Stadtforum Dresden": (13.739645, 51.046649),
    "Strehlener Straße": (13.747033, 51.034874),
    "Taschenbergpalais": (13.73534138, 51.05176913),
    "Theresienstraße": (13.74202109, 51.0631677),
    "Wiener Platz / Hauptbahnhof": (13.731322, 51.041955),
    "Wiesentorstraße": (13.74290934, 51.05670496),
    "World Trade Center": (13.72171564, 51.04937362),
    "Wöhrl / Florentinum": (13.73796299, 51.04451611)
}

# Diese mapping-Daten können später in der Streamlit-App genutzt werden, um Marker auf einer Karte zu platzieren.


# Mapping vom Dateinamen zur Modell-"Name" Variable
name_mapping = {
    "Altmarkt": "Altmarkt",
    "Altmarkt_-_Galerie": "Altmarkt - Galerie",
    "An_der_Frauenkirche": "An der Frauenkirche",
    "Budapester_Straße": "Budapester Straße",
    "Centrum_-_Galerie": "Centrum - Galerie",
    "Cossebaude": "Cossebaude",
    "Ferdinandplatz": "Ferdinandplatz",
    "Fidelio-F.-Finke-Straße": "Fidelio-F.-Finke-Straße",
    "Frauenkirche___Neumarkt": "Frauenkirche / Neumarkt",
    "GALERIA_Karstadt_Kaufhof": "GALERIA Karstadt Kaufhof",
    "Grenzstraße": "Grenzstraße",
    "Haus_am_Zwinger": "Haus am Zwinger",
    "Kaditz": "Kaditz",
    "Klotzsche": "Klotzsche",
    "Kongresszentrum": "Kongresszentrum",
    "Langebrück": "Langebrück",
    "MESSE_DRESDEN_Parkplatz_P7": "MESSE DRESDEN Parkplatz P7",
    "Ostra-Ufer": "Ostra-Ufer",
    "Parkhaus_Mitte": "Parkhaus Mitte",
    "Pennrich": "Pennrich",
    "Pieschener_Allee_Bus": "Pieschener Allee Bus",
    "Pirnaischer_Platz": "Pirnaischer Platz",
    "Prohlis": "Prohlis",
    "Reick": "Reick",
    "Reitbahnstraße": "Reitbahnstraße",
    "SP1_Straßburger_Platz": "SP1 Straßburger Platz",
    "SachsenEnergie_Center": "SachsenEnergie Center",
    "Sarrasanistraße": "Sarrasanistraße",
    "Schießgasse": "Schießgasse",
    "Semperoper": "Semperoper",
    "Stadtforum_Dresden": "Stadtforum Dresden",
    "Strehlener_Straße": "Strehlener Straße",
    "Taschenbergpalais": "Taschenbergpalais",
    "Theresienstraße": "Theresienstraße",
    "Wiener_Platz___Hauptbahnhof": "Wiener Platz / Hauptbahnhof",
    "Wiesentorstraße": "Wiesentorstraße",
    "World_Trade_Center": "World Trade Center",
    "Wöhrl___Florentinum": "Wöhrl / Florentinum"
}

# Dummy Mapping für District und Capacity (vom Parkplatzmodell abhängig)
district_mapping = {
     "Altmarkt": "Innere Altstadt",
    "Altmarkt_-_Galerie": "Prager Straße",
    "An_der_Frauenkirche": "Innere Altstadt",
    "Budapester_Straße": "Prager Straße",
    "Centrum_-_Galerie": "Prager Straße",
    "Cossebaude": "Park + Ride",
    "Ferdinandplatz": "Prager Straße",
    "Fidelio-F.-Finke-Straße": "Sonstige",
    "Frauenkirche___Neumarkt": "Innere Altstadt",
    "GALERIA_Karstadt_Kaufhof": "Prager Straße",
    "Grenzstraße": "Park + Ride",
    "Haus_am_Zwinger": "Innere Altstadt",
    "Kaditz": "Park + Ride",
    "Klotzsche": "Park + Ride",
    "Kongresszentrum": "Ring West",
    "Langebrück": "Park + Ride",
    "MESSE_DRESDEN_Parkplatz_P7": "Sonstige",
    "Ostra-Ufer": "Ring West",
    "Parkhaus_Mitte": "Ring West",
    "Pennrich": "Park + Ride",
    "Pieschener_Allee_Bus": "Busparkplätze",
    "Pirnaischer_Platz": "Ring Ost",
    "Prohlis": "Park + Ride",
    "Reick": "Park + Ride",
    "Reitbahnstraße": "Prager Straße",
    "SP1_Straßburger_Platz": "Ring Ost",
    "SachsenEnergie_Center": "Ring Süd",
    "Sarrasanistraße": "Neustadt",
    "Schießgasse": "Innere Altstadt",
    "Semperoper": "Innere Altstadt",
    "Stadtforum_Dresden": "Prager Straße",
    "Strehlener_Straße": "Ring Süd",
    "Taschenbergpalais": "Innere Altstadt",
    "Theresienstraße": "Neustadt",
    "Wiener_Platz___Hauptbahnhof": "Prager Straße",
    "Wiesentorstraße": "Neustadt",
    "World_Trade_Center": "Ring West",
    "Wöhrl___Florentinum": "Prager Straße"
}
capacity_mapping = {
    "Altmarkt": 400,
    "Altmarkt_-_Galerie": 480,
    "An_der_Frauenkirche": 120,
    "Budapester_Straße": 127,
    "Centrum_-_Galerie": 1059,
    "Cossebaude": 32,
    "Ferdinandplatz": 140,
    "Fidelio-F.-Finke-Straße": 105,
    "Frauenkirche___Neumarkt": 250,
    "GALERIA_Karstadt_Kaufhof": 265,
    "Grenzstraße": 38,
    "Haus_am_Zwinger": 171,
    "Kaditz": 190,
    "Klotzsche": 36,
    "Kongresszentrum": 250,
    "Langebrück": 50,
    "MESSE_DRESDEN_Parkplatz_P7": 1200,
    "Ostra-Ufer": 141,
    "Parkhaus_Mitte": 400,
    "Pennrich": 50,
    "Pieschener_Allee_Bus": 130,
    "Pirnaischer_Platz": 110,
    "Prohlis": 56,
    "Reick": 19,
    "Reitbahnstraße": 285,
    "SP1_Straßburger_Platz": 291,
    "SachsenEnergie_Center": 200,
    "Sarrasanistraße": 55,
    "Schießgasse": 202,
    "Semperoper": 400,
    "Stadtforum_Dresden": 97,
    "Strehlener_Straße": 235,
    "Taschenbergpalais": 120,
    "Theresienstraße": 140,
    "Wiener_Platz___Hauptbahnhof": 350,
    "Wiesentorstraße": 120,
    "World_Trade_Center": 220,
    "Wöhrl___Florentinum": 264
}

# Mapping Name -> Type
type_mapping = {
  "Altmarkt": "Historic Center",
  "Altmarkt - Galerie": "Shopping Center",
  "An der Frauenkirche": "Historic Center",
  "Budapester Straße": "Shopping Center",
  "Centrum - Galerie": "Shopping Center",
  "Cossebaude": "Park + Ride",
  "Ferdinandplatz": "Shopping Center",
  "Fidelio-F.-Finke-Straße": "Residential",
  "Frauenkirche / Neumarkt": "Historic Center",
  "GALERIA Karstadt Kaufhof": "Shopping Center",
  "Grenzstraße": "Park + Ride",
  "Haus am Zwinger": "Historic Center",
  "Kaditz": "Park + Ride",
  "Klotzsche": "Park + Ride",
  "Kongresszentrum": "Business District",
  "Langebrück": "Park + Ride",
  "MESSE DRESDEN Parkplatz P7": "Event Venue",
  "Ostra-Ufer": "Business District",
  "Parkhaus Mitte": "Business District",
  "Pennrich": "Park + Ride",
  "Pieschener Allee Bus": "Bus Station",
  "Pirnaischer Platz": "Business District",
  "Prohlis": "Park + Ride",
  "Reick": "Park + Ride",
  "Reitbahnstraße": "Shopping Center",
  "SP1 Straßburger Platz": "Shopping center",
  "SachsenEnergie Center": "Business District",
  "Sarrasanistraße": "Residential",
  "Schießgasse": "Historic Center",
  "Semperoper": "Historic Center",
  "Stadtforum Dresden": "Shopping Center",
  "Strehlener Straße": "Residential",
  "Taschenbergpalais": "Historic Center",
  "Theresienstraße": "Residential",
  "Wiener Platz / Hauptbahnhof": "Train Station",
  "Wiesentorstraße": "Residential",
  "World Trade Center": "Business District",
  "Wöhrl / Florentinum": "Shopping Center"
}

# Mapping Name -> distance_to_nearest_parking
distance_mapping = {
  "Altmarkt": 187.8659498,
  "Altmarkt - Galerie": 11.67616037,
  "An der Frauenkirche": 111.7926006,
  "Budapester Straße": 287.2800393,
  "Centrum - Galerie": 203.9418611,
  "Cossebaude": 4131.258258,
  "Ferdinandplatz": 85.26649105,
  "Fidelio-F.-Finke-Straße": 3896.232697,
  "Frauenkirche / Neumarkt": 221.7030143,
  "GALERIA Karstadt Kaufhof": 11.67616037,
  "Grenzstraße": 1623.756351,
  "Haus am Zwinger": 49.99519686,
  "Kaditz": 2521.960052,
  "Klotzsche": 1623.756351,
  "Kongresszentrum": 9.576368598,
  "Langebrück": 3828.579722,
  "MESSE DRESDEN Parkplatz P7": 919.2628998,
  "Parkhaus Mitte": 309.9921125,
  "Pennrich": 4978.307024,
  "Pieschener Allee Bus": 149.1990836,
  "Pirnaischer Platz": 259.5917749,
  "Prohlis": 2502.017578,
  "Reick": 2502.017578,
  "Reitbahnstraße": 203.9418611,
  "SP1 Straßburger Platz": 929.8968404,
  "SachsenEnergie Center": 375.1280744,
  "Sarrasanistraße": 180.261308,
  "Schießgasse": 111.7926006,
  "Semperoper": 419.7225845,
  "Stadtforum Dresden": 85.26649105,
  "Strehlener Straße": 1208.137926,
  "Taschenbergpalais": 49.99519686,
  "Theresienstraße": 651.3997874,
  "Wiener Platz / Hauptbahnhof": 9.576368598,
  "Wiesentorstraße": 180.261308,
  "World Trade Center": 679.1870619,
  "Wöhrl / Florentinum": 192.076243
}

rain_values = ['0.0', '0.01', '0.02', '0.03', '0.04', '0.05', '0.06', '0.07', '0.08', '0.09']
description_values = ['Clear', 'Cloudy', 'Fair', 'Fog', 'Light Rain', 'Light Rain with Thunder', 'Mostly Cloudy', 'Partly Cloudy', 'Rain', 'Rain Shower', 'Showers in the Vicinity', 'Sunny', 'Thunder in the Vicinity', 'Thunderstorm']
event_size_values = ['', 'large', 'medium', 'small', 'unknown']

# Feiertage Sachsen
sachsen_holidays = holidays.Germany(prov='SN')

if not pkl_files:
    st.warning("Keine .pkl-Dateien im aktuellen Verzeichnis gefunden.")
else:
    # --- Zeitfeatures ---
    st.subheader("Zeiteinstellungen")
    minutes_ahead = st.slider("Vorhersagezeitraum (in Minuten, bis 48h)", min_value=0, max_value=48*60, value=0, step=5)
    prediction_time = datetime.now() + timedelta(minutes=minutes_ahead)
    hour = prediction_time.hour
    minute_of_day = prediction_time.hour * 60 + prediction_time.minute
    weekday = prediction_time.weekday()
    is_weekend = 1 if weekday >= 5 else 0
    is_holiday = 1 if date(prediction_time.year, prediction_time.month, prediction_time.day) in sachsen_holidays else 0

    # --- Eingaben für alle Modelle ---
    st.subheader("Allgemeine Eingaben")
    temperature = st.number_input("Temperatur (°C)", value=20.0)
    description = st.selectbox("Wetterbeschreibung", description_values)
    humidity = st.slider("Luftfeuchtigkeit (%)", min_value=0, max_value=100, value=50)
    rain = st.selectbox("Regen (mm)", options=rain_values, format_func=lambda x: f"{x} mm")
    final_avg_occ = st.number_input("Durchschnittliche Belegung (%)", min_value=0.0, max_value=100.0, value=50.0)
    in_event_window = st.selectbox("In Event-Fenster?", [0, 1])
    event_size = st.selectbox("Eventgröße", options=event_size_values)

    results = []
    for model_file, key in zip(pkl_files, parking_names):
        with open(model_file, "rb") as f:
            model = pickle.load(f)
        
        model_name_value = name_mapping.get(key, key)
        inputs = {
            "Name": model_name_value,
            "Capacity": float(capacity_mapping.get(key, 0)),
            "Temperature": float(temperature),
            "Description": description,
            "Humidity": float(humidity),
            "Rain": float(rain),
            "District": district_mapping.get(key, "Unbekannt"),
            "Type": type_mapping.get(model_name_value, "Unbekannt"),
            "final_avg_occ": float(final_avg_occ),
            "in_event_window": int(in_event_window),
            "event_size": event_size,
            "distance_to_nearest_parking": float(distance_mapping.get(model_name_value, 0.0)),
            "hour": float(hour),
            "minute_of_day": float(minute_of_day),
            "weekday": float(weekday),
            "is_weekend": float(is_weekend),
            "is_holiday": float(is_holiday)
        }

        feature_order = list(model.feature_names_in_) if hasattr(model, "feature_names_in_") else list(inputs.keys())
        input_df = pd.DataFrame([[inputs[f] for f in feature_order]], columns=feature_order)
        for col in input_df.select_dtypes(include=['object']).columns:
            input_df[col] = input_df[col].astype('category')
        
        prediction = model.predict(input_df)[0]
        results.append({"Parkplatz": model_name_value, "Vorhersage %": round(prediction, 2)})
    
    
    
    st.header("Parkplatz-Vorhersagen auf Karte")

    # Normierte Werte (0 = minimal, 1 = maximal) berechnen
    vorhersagen = [res["Vorhersage %"] for res in results]
    min_val, max_val = min(vorhersagen), max(vorhersagen)
    range_val = max_val - min_val if max_val != min_val else 1

    map_data = []
    for res in results:
        parkplatz = res["Parkplatz"]
        vorhersage = round(res["Vorhersage %"], 1)
        coords = coordinates_mapping.get(parkplatz)
        if coords:
            norm_value = (res["Vorhersage %"] - min_val) / range_val  # Skala 0-1
            r = int(norm_value * 255)
            g = int((1 - norm_value) * 255)
            b = 0
            map_data.append({
                "lat": coords[1],
                "lon": coords[0],
                "Parkplatz": parkplatz,
                "Vorhersage %": vorhersage,
                "color": [r, g, b]
            })

    map_df = pd.DataFrame(map_data)

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius=50,
        pickable=True
    )

    tooltip = {
        "html": "<b>{Parkplatz}</b><br/>Vorhersage: {Vorhersage %}%",
        "style": {"backgroundColor": "steelblue", "color": "white"}
    }

    view_state = pdk.ViewState(latitude=51.0504, longitude=13.7373, zoom=13)

    # Legende mit Streamlit Widgets
    st.subheader("Legende")
    col1, col2 = st.columns([1, 4])
    with col1:
        st.color_picker("Niedrig", "#00FF00", key="low_color", disabled=True)
    with col2:
        st.write(f"Niedrig ({min_val:.1f}%)")
    col3, col4 = st.columns([1, 4])
    with col3:
        st.color_picker("Hoch", "#FF0000", key="high_color", disabled=True)
    with col4:
        st.write(f"Hoch ({max_val:.1f}%)")

    deck = pdk.Deck(layers=[scatter_layer], initial_view_state=view_state, tooltip=tooltip)
    st.pydeck_chart(deck)
