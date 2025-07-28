import streamlit as st
import pickle
import glob
from datetime import datetime, timedelta, date, timezone
import pytz
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
    event_size_values,
    occupancy_mapping,
    event_size_display_mapping
)

st.set_page_config(page_title="Dresden Parking", layout="wide")

# --- Parkplatznamen und Mapping auf Eingabewerte ---
pkl_files = glob.glob("xgb_model_*.pkl")
parking_names = [f.replace("xgb_model_", "").replace(".pkl", "") for f in pkl_files]


# --- Wetterdaten von Open-Meteo API ---
weather_url = (
"https://api.open-meteo.com/v1/forecast"
"?latitude=51.0504&longitude=13.7373"
"&current_weather=true&hourly=weathercode,precipitation,relativehumidity_2m")

response = requests.get(weather_url)
weather_data = response.json()
current_weather = weather_data.get("current_weather", {})
temperature_api = current_weather.get("temperature")
windspeed = current_weather.get("windspeed")
weather_code = current_weather.get("weathercode")

## Humidity extrahieren (aktueller Zeitpunkt)
humidity_series = weather_data.get("hourly", {}).get("relativehumidity_2m", [])
rain_series = weather_data.get("hourly", {}).get("precipitation", [])
hourly_times = weather_data.get("hourly", {}).get("time", [])

rain_api = 0.0
humidity_api = 50.0
if hourly_times:
    now_str = datetime.utcnow().replace(minute=0, second=0, microsecond=0).isoformat() + "Z"
    if now_str in hourly_times:
        idx = hourly_times.index(now_str)
        if rain_series:
            rain_api = rain_series[idx]
        if humidity_series:
            humidity_api = humidity_series[idx]

description_auto = weather_code_mapping.get(weather_code, "Unknown")

sachsen_holidays = holidays.Germany(prov='SN')

st.subheader("User input")
col_time, col_event = st.columns([1, 1], border = True)

with col_time:
    minutes_ahead = st.slider("Look into the future (in minutes, 48h max)", min_value=0, max_value=48*60, value=120, step=5)
    local_tz = pytz.timezone("Europe/Berlin")
    prediction_time = datetime.now(timezone.utc).astimezone(local_tz) + timedelta(minutes=minutes_ahead)    
    minute_rounded = (prediction_time.minute // 5) * 5
    prediction_time = prediction_time.replace(minute=minute_rounded, second=0, microsecond=0)
    # Anzeige der ausgewählten Uhrzeit
    st.markdown(f"**Selected time:**")
    st.markdown(f"{prediction_time.strftime('%d.%m.%Y, %H:%M')}")

with col_event:
    in_event_window = st.toggle("Event in 600 m radius?", value=False)
    if in_event_window:
        raw_event_size = st.selectbox("Event size", options=event_size_values)
        event_size = event_size_display_mapping.get(raw_event_size)
    else:
        event_size = None

hour = prediction_time.hour
minute_of_day = prediction_time.hour * 60 + prediction_time.minute
weekday = prediction_time.weekday()
is_weekend = 1 if weekday >= 5 else 0
is_holiday = 1 if date(prediction_time.year, prediction_time.month, prediction_time.day) in sachsen_holidays else 0

temperature = temperature_api
rain = rain_api
description = description_auto
humidity = humidity_api

# --- avg occ Abfrage ---
def get_occupancy_value(parking_key, minute_of_day):
    mapped_name = name_mapping.get(parking_key, parking_key)
    if mapped_name not in occupancy_mapping:
        return 50.0  # Fallback

    rounded_minute = str(5 * round(minute_of_day / 5))  # String!
    return occupancy_mapping[mapped_name].get(rounded_minute, 50.0)




st.markdown("---")

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
        "final_avg_occ": float(get_occupancy_value(key, minute_of_day)),
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

# --- Karte ---
vorhersagen = [res.get("Vorhersage %", res.get("Prediction %", 0)) for res in results]
min_val, max_val = min(vorhersagen), max(vorhersagen)
range_val = max_val - min_val if max_val != min_val else 1

map_data = []
for res in results:
    parkplatz = res.get("Parkplatz", res.get("Parking lot", "Unbekannt"))
    vorhersage = res.get("Vorhersage %", res.get("Prediction %", 0))
    vorhersage_rounded = round(vorhersage, 2)
    coords = coordinates_mapping.get(parkplatz)
    if coords:
        norm_value = (vorhersage_rounded - min_val) / range_val
        r = int(norm_value * 255)
        g = int((1 - norm_value) * 255)
        map_data.append({
            "lat": coords[1],
            "lon": coords[0],
            "Parkplatz": parkplatz,
            # als String mit 2 Nachkommastellen für Tooltip
            "Vorhersage %": f"{vorhersage_rounded:.2f} occupation",  
            "color": [r, g, 0]
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
    "html": "<b>{Parkplatz}</b><br/>Prediction: {Vorhersage %}%",
    "style": {"backgroundColor": "steelblue", "color": "white"}
}

view_state = pdk.ViewState(latitude=51.0504, longitude=13.7373, zoom=13)
st.pydeck_chart(pdk.Deck(layers=[scatter_layer], initial_view_state=view_state, tooltip=tooltip))


st.markdown("---")

show_debug = st.toggle("Debugging Mode")
if show_debug:
    st.subheader("Final model input for last prediction")
    st.json(inputs)
    st.subheader("All prediction results")
    st.dataframe(pd.DataFrame(results))
