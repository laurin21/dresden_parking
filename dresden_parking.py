import streamlit as st
import pickle
import glob
from datetime import datetime, timedelta, date
import holidays
import pandas as pd
import folium
import pydeck as pdk
import requests

from mappings import (
    coordinates_mapping,
    name_mapping,
    district_mapping,
    capacity_mapping,
    type_mapping,
    distance_mapping,
    weather_code_mapping,
    rain_values,
    event_size_values
)

st.set_page_config(page_title="Parking Model Inputs", layout="wide")

# --- Parkplatznamen und Mapping auf Eingabewerte ---
pkl_files = glob.glob("xgb_model_*.pkl")
parking_names = [f.replace("xgb_model_", "").replace(".pkl", "") for f in pkl_files]


# --- Wetterdaten von Open-Meteo API ---
try:
    weather_url = ("https://api.open-meteo.com/v1/forecast"
                   "?latitude=51.0504&longitude=13.7373"
                   "&current_weather=true&hourly=weathercode,precipitation")
    response = requests.get(weather_url)
    if response.status_code == 200:
        weather_data = response.json()
        current_weather = weather_data.get("current_weather", {})
        temperature_api = current_weather.get("temperature")
        windspeed = current_weather.get("windspeed")
        weather_code = current_weather.get("weathercode")

        # Niederschlag ermitteln (aktueller Zeitpunkt)
        precipitation_series = weather_data.get("hourly", {}).get("precipitation", [])
        hourly_times = weather_data.get("hourly", {}).get("time", [])
        rain_api = 0.0
        if hourly_times and precipitation_series:
            # Aktuelle Zeit finden
            now_str = datetime.utcnow().replace(minute=0, second=0, microsecond=0).isoformat() + "Z"
            if now_str in hourly_times:
                idx = hourly_times.index(now_str)
                rain_api = precipitation_series[idx]
        description_auto = weather_code_mapping.get(weather_code, "Unknown")
        weather_text = f"Current weather in Dresden: {temperature_api}°C, wind {windspeed} km/h, {description_auto}, rain {rain_api} mm"
    else:
        weather_text = "Weather data failed to load."
        description_auto = "Clear"
        rain_api = 0.0
except Exception as e:
    weather_text = f"Error during loading of weather data: {e}"
    description_auto = "Clear"
    rain_api = 0.0

st.write(weather_text)


sachsen_holidays = holidays.Germany(prov='SN')

if not pkl_files:
    st.warning("No .pkl-files found in the current directory.")
else:
    st.subheader("Time settings")
    minutes_ahead = st.slider("Look into the future (in minutes, 48h max)", min_value=0, max_value=48*60, value=0, step=5)
    prediction_time = datetime.now() + timedelta(minutes=minutes_ahead)
    hour = prediction_time.hour
    minute_of_day = prediction_time.hour * 60 + prediction_time.minute
    weekday = prediction_time.weekday()
    is_weekend = 1 if weekday >= 5 else 0
    is_holiday = 1 if date(prediction_time.year, prediction_time.month, prediction_time.day) in sachsen_holidays else 0

    st.subheader("Other input")
    temperature = temperature_api
    rain = rain_api
    description = description_auto
    humidity = st.slider("Humidity (%)", min_value=0, max_value=100, value=50)
    rain = st.selectbox("Rain (mm)", options=rain_values, format_func=lambda x: f"{x} mm")
    final_avg_occ = st.number_input("Average occupation (%)", min_value=0.0, max_value=100.0, value=50.0)
    in_event_window = st.selectbox("Event in 300m radius??", [0, 1])
    event_size = st.selectbox("Event size", options=event_size_values)

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

        # Fehlende Features abfangen
        missing_features = [f for f in feature_order if f not in inputs]
        if missing_features:
            st.warning(f"Missing features for model {model_name_value}: {missing_features}")
        # DataFrame erstellen, fehlende Features auf None setzen
        input_df = pd.DataFrame([[inputs.get(f, None) for f in feature_order]], columns=feature_order)
        for col in input_df.select_dtypes(include=['object']).columns:
            input_df[col] = input_df[col].astype('category')

        prediction = model.predict(input_df)[0]
        results.append({"Parkplatz": model_name_value, "Vorhersage %": round(prediction, 2)})

    # Karte wie vorher
    vorhersagen = [res.get("Vorhersage %", res.get("Prediction %", 0)) for res in results]
    min_val, max_val = min(vorhersagen), max(vorhersagen)
    range_val = max_val - min_val if max_val != min_val else 1
    map_data = []
    for res in results:
        parkplatz = res.get("Parkplatz", res.get("Parking lot", "Unbekannt"))
        vorhersage = round(res.get("Vorhersage %", res.get("Prediction %", 0)), 2)
        coords = coordinates_mapping.get(parkplatz)
        if coords:
            norm_value = (vorhersage - min_val) / range_val
            r = int(norm_value * 255)
            g = int((1 - norm_value) * 255)
            map_data.append({"lat": coords[1], "lon": coords[0], "Parkplatz": parkplatz, "Vorhersage %": vorhersage, "color": [r, g, 0]})
    map_df = pd.DataFrame(map_data)
    scatter_layer = pdk.Layer("ScatterplotLayer", data=map_df, get_position="[lon, lat]", get_fill_color="color", get_radius=50, pickable=True)
    tooltip = {"html": "<b>{Parkplatz}</b><br/>Vorhersage: {Vorhersage %}%", "style": {"backgroundColor": "steelblue", "color": "white"}}
    view_state = pdk.ViewState(latitude=51.0504, longitude=13.7373, zoom=13)
    st.pydeck_chart(pdk.Deck(layers=[scatter_layer], initial_view_state=view_state, tooltip=tooltip))

show_debug = st.toggle("Debugging Mode")
if show_debug:
    st.subheader("Final model input for last prediction")
    st.json(inputs)
    st.subheader("All prediction results")
    st.dataframe(pd.DataFrame(results))