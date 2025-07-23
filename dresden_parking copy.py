import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import joblib
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime
import asyncio
import os
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="Parkplatzprognose Dresden", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("dresden_parking_final.csv")
    df.columns = df.columns.str.lower()
    df.replace("unknown", pd.NA, inplace=True)
    df["event_size"] = df["event_size"].fillna(0)
    return df

@st.cache_data
def load_coordinates():
    coords = pd.read_csv("coordinates.csv")
    coords = coords.rename(columns={"Parking Lots": "name", "GPS Lon": "lon", "GPS Lat": "lat"})
    coords.columns = coords.columns.str.lower()
    return coords

@st.cache_resource
def load_model():
    if os.path.exists("trained_model.pkl"):
        return joblib.load("trained_model.pkl")
    else:
        st.warning("⚠️ Kein externes Modell gefunden. Es wird ein Dummy-Modell mit RandomForestRegressor erstellt.")
        df = load_data()
        features = ["temperature", "humidity", "rain", "weekday", "is_weekend", "is_holiday",
                    "in_event_window", "event_size", "minute_of_day", "distance_to_nearest_parking"]
        df = df.dropna(subset=features + ["occupation"])
        X = df[features].apply(pd.to_numeric, errors='coerce')
        y = pd.to_numeric(df["occupation"], errors='coerce')
        model = RandomForestRegressor(n_estimators=10, max_depth=5, random_state=42)
        model.fit(X, y)
        return model

st.title("🏍️ Parkplatz-Auslastung & Prognose in Dresden")

use_live_data = st.sidebar.checkbox("🔄 Live-Daten (Webscraping) verwenden", value=False)

def scrape_live_occupancy():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('https://www.dresden.de/apps_ext/ParkplatzApp/index')
            page.wait_for_selector('div.contentsection table', timeout=10000)
            data = page.locator('div.contentsection table tr td div.content').all_text_contents()
            data = [d.strip() for d in data if d.strip() != '']
            browser.close()

        result = []
        i = 0
        while i < len(data) - 2:
            name = data[i]
            cap = data[i+1]
            fr = data[i+2]
            if cap.isdigit() and fr.isdigit():
                cap = int(cap)
                fr = int(fr)
                if cap > 0:
                    occ = 1 - fr / cap
                    result.append((name, cap, occ))
                i += 3
            else:
                i += 1
        return result
    except Exception as e:
        st.warning(f"⚠️ Parkplatz-Webscraping-Fehler: {e}")
        return []
    except Exception as e:
        st.warning(f"⚠️ Webscraping-Fehler: {e}")
        return []

@st.cache_data(show_spinner=False)
def fetch_live_data(use_live_scraping: bool):
    try:
        if use_live_scraping:
            # scrape synchron statt async
            live_occupancy = scrape_live_occupancy()
            occ_dict = {name.lower(): occ for name, cap, occ in live_occupancy}

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto('https://www.wunderground.com/weather/de/dresden')
                page.wait_for_selector('div.current-temp span.wu-value.wu-value-to', timeout=10000)
                temp = float(page.locator('div.current-temp span.wu-value.wu-value-to').inner_text())
                temp = (temp - 32) * 5 / 9
                humidity = float(page.locator('lib-display-unit[type="humidity"] span.wu-value.wu-value-to').inner_text())
                rain = float(page.locator('div.small-8.columns lib-display-unit[type="rain"] span.wu-value.wu-value-to').inner_text())
                browser.close()

            return {
                "temperature": temp,
                "humidity": humidity,
                "rain": rain,
                "minute_of_day": datetime.now().hour * 60 + datetime.now().minute,
                "weekday": datetime.now().isoweekday(),
                "is_weekend": int(datetime.now().isoweekday() in [6, 7]),
                "is_holiday": 0,
                "in_event_window": 1,
                "event_size": 2,
                "live_occupancy": occ_dict
            }
        else:
            raise ValueError("Live-Modus ist deaktiviert")

    except Exception as e:
        st.warning(f"⚠️ Live-Daten konnten nicht geladen werden (Fehler: {e}). Es werden Dummy-Werte verwendet.")
        return {
            "temperature": 22.5,
            "humidity": 60,
            "rain": 0.0,
            "minute_of_day": datetime.now().hour * 60 + datetime.now().minute,
            "weekday": datetime.now().isoweekday(),
            "is_weekend": int(datetime.now().isoweekday() in [6, 7]),
            "is_holiday": 0,
            "in_event_window": 0,
            "event_size": 0,
            "live_occupancy": {}
        }

if st.button("🔁 Modell neu laden"):
    st.cache_resource.clear()

model = load_model()
df = load_data()
coords = load_coordinates()
live_input = fetch_live_data(use_live_data)

if "name" in coords.columns and "name" in df.columns:
    df = pd.merge(df, coords, on="name", how="left")

debug_mode = st.sidebar.checkbox("🐞 Debug-Modus aktivieren", value=False)

# 🧪 Analyse-Modus (optional: alle Zeitpunkte eines Parkplatzes anzeigen – in Vorbereitung)

st.sidebar.header("Filter")
from datetime import time
selected_hour = st.sidebar.slider("Uhrzeit (Minute des Tages)", 0, 1439, live_input["minute_of_day"], step=5)
weekday_labels = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag", 6: "Samstag", 7: "Sonntag"}
weekday_values = sorted([day for day in df["weekday"].dropna().astype(int).unique() if day in weekday_labels])
weekday_display = [weekday_labels[day] for day in weekday_values]
selected_weekday_label = st.sidebar.selectbox("Wochentag", weekday_display, index=live_input["weekday"] - 1)
selected_weekday = weekday_values[weekday_display.index(selected_weekday_label)]
filtered_df = df[(df["minute_of_day"] == selected_hour) & (df["weekday"] == selected_weekday)]

# 🔍 Debug-Ausgabe
if debug_mode:
        st.write("📍 Parkplatznamen in coordinates.csv:")
        st.write(coords['name'].dropna().unique().tolist())

        st.write("📍 Parkplatznamen in dresden_parking_final.csv:")
        st.write(df['name'].dropna().unique().tolist())
if debug_mode:
    st.markdown("---")
    st.markdown("### 🔎 Debugging-Info")
    st.write("Gesamte Zeilen im Datensatz:", len(df))
    st.write("Zeilen nach Zeit- & Wochentags-Filter:", len(filtered_df))
    valid_coords = filtered_df.dropna(subset=['lat', 'lon']).query('capacity > 0')
    st.write("Zeilen mit gültigen Koordinaten und Kapazität > 0:", len(valid_coords))
    st.write("Verfügbare Spalten:", filtered_df.columns.tolist())
    st.write("Beispieldaten:")
    st.dataframe(filtered_df.head())
    st.write("Live-Occupancy Keys (Scraping):", list(live_input["live_occupancy"].keys())[:5])
    st.write("Name-Beispiele aus DataFrame:", df['name'].str.lower().unique()[:5])
    valid_coords = filtered_df.dropna(subset=['lat', 'lon']).query('capacity > 0')
    st.write("Zeilen mit gültigen Koordinaten und Kapazität > 0:", len(valid_coords))
    st.write("Verfügbare Spalten:", filtered_df.columns.tolist())
    st.write("Beispieldaten:")
    st.dataframe(filtered_df.head())

    if "lat" in filtered_df.columns and "lon" in filtered_df.columns:
        st.write("Beispiel-Koordinaten:")
        st.dataframe(filtered_df[["name", "lat", "lon"]].dropna().head())

features = ["temperature", "humidity", "rain", "weekday", "is_weekend", "is_holiday",
            "in_event_window", "event_size", "minute_of_day", "distance_to_nearest_parking"]

for key in live_input:
    if key in filtered_df.columns:
        filtered_df[key] = live_input[key]

if "live_occupancy" in live_input:
    df["live_occupation"] = df.apply(
        lambda row: live_input["live_occupancy"].get(row["name"].lower(), None) / row["capacity"]
        if pd.notna(row["capacity"]) and row["name"].lower() in live_input["live_occupancy"] else None,
        axis=1
    )
    filtered_df["live_occupation"] = filtered_df.apply(
        lambda row: live_input["live_occupancy"].get(row["name"].lower(), None) / row["capacity"]
        if pd.notna(row["capacity"]) and row["name"].lower() in live_input["live_occupancy"] else None,
        axis=1
    )

drop_columns = [col for col in features + ["lat", "lon"] if col in filtered_df.columns]
filtered_df = filtered_df.dropna(subset=drop_columns)

if debug_mode:
    missing_cols = [col for col in features if col not in filtered_df.columns]
    st.write("🧩 Fehlende Spalten fürs Modell:", missing_cols)
    st.write("🔍 NaN-Werte in Features:")
    st.dataframe(filtered_df[features].isna().sum())
X_pred = filtered_df[features].apply(pd.to_numeric, errors='coerce')
if hasattr(model, "predict"):
    filtered_df["predicted_occupation"] = model.predict(X_pred)
else:
    st.error("❌ Das geladene Modell unterstützt keine .predict()-Methode in Python.")

st.subheader("🗺️ Prognose-Karte für Dresden")

# Rote Punkte für gemeinsame Parkplätze
if "name" in df.columns:
    df["name"] = df["name"].astype(str)
    df["name_lower"] = df["name"].str.lower()
else:
    st.warning("⚠️ 'name'-Spalte fehlt in dresden_parking_final.csv")
if "name" in coords.columns:
    coords["name"] = coords["name"].astype(str)
    coords["name_lower"] = coords["name"].str.lower()
else:
    st.warning("⚠️ 'name'-Spalte fehlt in coordinates.csv")
common_names = set(df['name_lower']) & set(coords['name_lower'])
matched_coords = coords[coords['name_lower'].isin(common_names)]
matched_coords = matched_coords.dropna(subset=['lat', 'lon'])

map_fig = px.scatter_mapbox(
    matched_coords,
    lat="lat",
    lon="lon",
    hover_name="name",
    zoom=11,
    height=600,
    title="Parkplätze in Dresden",
)

map_fig.update_traces(marker=dict(size=16, color="red"))
map_fig.update_layout(mapbox_style="open-street-map")
st.plotly_chart(map_fig, use_container_width=True)


st.markdown("---")

st.subheader("🔍 Datenansicht")
if not filtered_df.empty:
        # Gruppieren auf einen Eintrag pro Parkplatz (nachdem alle Spalten vorhanden sind)
    if "predicted_occupation" in filtered_df.columns and "live_occupation" in filtered_df.columns:
        filtered_df = (
            filtered_df
            .groupby(["name", "capacity", "weekday", "minute_of_day", "district", "type", "lat", "lon"], as_index=False)
            .agg({"predicted_occupation": "mean", "live_occupation": "mean"})
        )
    st.dataframe(filtered_df[["name", "capacity", "predicted_occupation", "live_occupation", "weekday", "minute_of_day", "district", "type"]])
else:
    st.info("Keine Daten für die aktuelle Auswahl verfügbar.")
