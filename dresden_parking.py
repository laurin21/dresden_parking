import streamlit as st
import pickle
import glob
from datetime import datetime, timedelta, date, timezone
import pytz
import holidays
import pandas as pd
import pydeck as pdk
import requests

from mappings import *

st.set_page_config(page_title="Dresden Parking", layout="wide")

# --- Parkplatznamen und Mapping auf Eingabewerte ---
pkl_files = glob.glob("xgb_model_*.pkl")
parking_names = [f.replace("xgb_model_", "").replace(".pkl", "") for f in pkl_files]
parking_display_names = [name_mapping.get(p, p) for p in parking_names]

# --- Wetterdaten ---
weather_url = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=51.0504&longitude=13.7373"
               "&current_weather=true&hourly=weathercode,precipitation,relativehumidity_2m")
response = requests.get(weather_url)
weather_data = response.json()
current_weather = weather_data.get("current_weather", {})
temperature_api = current_weather.get("temperature")
weather_code = current_weather.get("weathercode")

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

st.title("🅿️ Parking lot predictions for Dresden")
st.markdown("---")
st.subheader("User input")
col_time, col_event = st.columns([1, 1], border=True)

with col_time:
    minutes_ahead = st.slider("Look into the future (in minutes, 48h max)", 0, 48*60, 120, 5)
    local_tz = pytz.timezone("Europe/Berlin")
    prediction_time = datetime.now(timezone.utc).astimezone(local_tz) + timedelta(minutes=minutes_ahead)
    minute_rounded = (prediction_time.minute // 5) * 5
    prediction_time = prediction_time.replace(minute=minute_rounded, second=0, microsecond=0)
    hours_ahead = minutes_ahead // 60
    minutes_only = minutes_ahead % 60
    st.markdown(f"**Selected time:** {prediction_time.strftime('%d.%m.%Y, %H:%M')} (+ {hours_ahead:02d}:{minutes_only:02d})")

with col_event:
    selected_parking_display = st.selectbox("Select parking lot", parking_display_names)
    selected_parking = parking_names[parking_display_names.index(selected_parking_display)]

    in_event_window = st.toggle("Event in 600 m radius?", value=False)
    if in_event_window:
        raw_event_size = st.pills(
            "Event size",
            options=[x for x in event_size_values if x],
            format_func=lambda x: event_size_display_mapping.get(x, x),
            default = "Medium"
        )
        event_size = raw_event_size
    else:
        event_size = None

# --- Zeitbasierte Variablen ---
hour = prediction_time.hour
minute_of_day = prediction_time.hour * 60 + prediction_time.minute
weekday = prediction_time.weekday()
is_weekend = 1 if weekday >= 5 else 0
is_holiday = 1 if date(prediction_time.year, prediction_time.month, prediction_time.day) in sachsen_holidays else 0

def get_occupancy_value(parking_key, minute_of_day):
    mapped_name = name_mapping.get(parking_key, parking_key)
    if mapped_name not in occupancy_mapping:
        return 50.0
    rounded_minute = str(5 * round(minute_of_day / 5))
    return occupancy_mapping[mapped_name].get(rounded_minute, 50.0)

results = []
selected_prediction = None
for model_file, key in zip(pkl_files, parking_names):
    try:
        with open(model_file, "rb") as f:
            model = pickle.load(f)
    except (EOFError, _pickle.UnpicklingError):
        placeholder = st.empty()
        placeholder.info("An error occurred and the application was restarted.")
        st.experimental_rerun()


    model_name_value = name_mapping.get(key, key)
    inputs = {
        "Name": model_name_value,
        "Capacity": float(capacity_mapping.get(key, 0)),
        "Temperature": float(temperature_api),
        "Description": description_auto,
        "Humidity": float(humidity_api),
        "Rain": float(rain_api),
        "District": district_mapping.get(key, "Unbekannt"),
        "Type": type_mapping.get(model_name_value, "Unbekannt"),
        "final_avg_occ": float(get_occupancy_value(key, minute_of_day)),
        "in_event_window": int(in_event_window if key == selected_parking else 0),
        "event_size": event_size if key == selected_parking else None,
        "distance_to_nearest_parking": float(distance_mapping.get(model_name_value, 0.0)),
        "hour": float(hour),
        "minute_of_day": float(minute_of_day),
        "weekday": float(weekday),
        "is_weekend": float(is_weekend),
        "is_holiday": float(is_holiday)
    }
    feature_order = list(model.feature_names_in_) if hasattr(model, "feature_names_in_") else list(inputs.keys())
    input_df = pd.DataFrame([[inputs.get(f, None) for f in feature_order]], columns=feature_order)
    for col in input_df.select_dtypes(include=['object']).columns:
        input_df[col] = input_df[col].astype('category')
    prediction = model.predict(input_df)[0]
    results.append({"Parkplatz": model_name_value, "Vorhersage %": round(prediction, 2)})
    if key == selected_parking:
        selected_prediction = round(prediction, 2)

for res in results:
    res["Vorhersage %"] = min(res["Vorhersage %"], 1.00)
if selected_prediction is not None:
    selected_prediction = min(selected_prediction, 1.00)

# --- KPIs ---
st.markdown("---")
col_selected, col_min, col_max = st.columns([1, 1, 1], border=True)

# Selected parking KPI
with col_selected:
    if selected_prediction is not None:
        st.markdown("Predicted occupation for selection")
        st.metric(label=f"{selected_parking_display}", value=f"{int(selected_prediction*100)}%")

# Determine min and max predictions
if results:
    min_result = min(results, key=lambda x: x["Vorhersage %"])
    max_result = max(results, key=lambda x: x["Vorhersage %"])

    with col_min:
        st.markdown("Lowest predicted occupation")
        st.metric(label=f"{min_result['Parkplatz']}", value=f"{int(min_result['Vorhersage %']*100)}%")

    with col_max:
        st.markdown("Highest predicted occupation")
        st.metric(label=f"{max_result['Parkplatz']}", value=f"{int(max_result['Vorhersage %']*100)}%")


# --- Karte ---
st.markdown("---")
st.subheader("🗺️ Map for Dresden parking prediction")
vorhersagen = [res.get("Vorhersage %", 0) for res in results]
min_val, max_val = min(vorhersagen), max(vorhersagen)
range_val = max_val - min_val if max_val != min_val else 1
map_data = []
for res in results:
    parkplatz = res.get("Parkplatz", "Unbekannt")
    vorhersage = res.get("Vorhersage %", 0)
    coords = coordinates_mapping.get(parkplatz)
    if coords:
        norm_value = (vorhersage - min_val) / range_val
        r = int(norm_value * 255)
        g = int((1 - norm_value) * 255)
        map_data.append({
            "lat": coords[1],
            "lon": coords[0],
            "Parkplatz": parkplatz,
            "TooltipText": f"Prediction for {prediction_time.strftime('%H:%M')}: {int(vorhersage*100)}%",
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
tooltip = {"html": "<b>{Parkplatz}</b><br/>{TooltipText}",
           "style": {"backgroundColor": "steelblue", "color": "white"}}
# Standard ViewState
view_state = pdk.ViewState(latitude=51.0504, longitude=13.7373, zoom=13)
# Karte anzeigen
st.pydeck_chart(pdk.Deck(layers=[scatter_layer], initial_view_state=view_state, tooltip=tooltip))

st.markdown("---")

show_debug = st.toggle("Debugging Mode")
if show_debug:
    st.subheader("Final model input for last prediction")
    st.json(inputs)
    st.subheader("All prediction results")
    st.dataframe(pd.DataFrame(results))