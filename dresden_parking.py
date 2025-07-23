import streamlit as st
import pandas as pd
from datetime import datetime
import subprocess
subprocess.run(["playwright", "install", "chromium"])
from playwright.sync_api import sync_playwright
import pydeck as pdk
from sklearn.ensemble import RandomForestRegressor
import numpy as np

browser = p.chromium.launch(headless=True, args=["--no-sandbox"])

st.set_page_config(page_title="Parking in Dresden", layout="wide")

# --- Webscraping Code ---
def scrap_parking():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.dresden.de/apps_ext/ParkplatzApp/index')
        page.wait_for_selector('div.contentsection table', timeout=10000)
        data = page.locator('div.contentsection table tr td div.content').all_text_contents()
        browser.close()
        data = [element.strip() for element in data if element.strip() != '']
        return data

def classify(datalist):
    name, capacity, free = [], [], []
    i = 0
    while i < len(datalist) - 2:
        if datalist[i].isdigit():
            i += 1
            continue
        n, cap, fr = datalist[i], datalist[i+1], datalist[i+2]
        if cap.isdigit() and fr.isdigit():
            cap, fr = int(cap), int(fr)
            if cap != 0:
                name.append(n)
                capacity.append(cap)
                free.append(fr)
            i += 3
        else:
            i += 1
    return name, capacity, free

def scrap_weather():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.wunderground.com/weather/de/dresden')
        page.wait_for_selector('div.current-temp span.wu-value.wu-value-to', timeout=10000)
        weather_data = [
            page.locator('div.current-temp span.wu-value.wu-value-to').inner_text(),
            page.locator('div.condition-icon.small-6.medium-12.columns p').inner_text(),
            page.locator('lib-display-unit[type="humidity"] span.wu-value.wu-value-to').inner_text(),
            page.locator('div.small-8.columns lib-display-unit[type="rain"] span.wu-value.wu-value-to').inner_text()
        ]
        weather_data = [element.strip() for element in weather_data]
        weather_data[0] = (float(weather_data[0]) - 32) * 5 / 9
        browser.close()
        return weather_data

def load_coordinates():
    coords = pd.read_csv("coordinates.csv", sep=";")
    coords.columns = coords.columns.str.lower()
    if "parking lots" in coords.columns:
        coords = coords.rename(columns={"parking lots": "name"})
    if "gps lon" in coords.columns:
        coords = coords.rename(columns={"gps lon": "lon"})
    if "gps lat" in coords.columns:
        coords = coords.rename(columns={"gps lat": "lat"})
    return coords

def load_live_data():
    data = scrap_parking()
    weather = scrap_weather()
    name, capacity, free = classify(data)
    now = datetime.now()
    df = pd.DataFrame({
        'name': name,
        'capacity': capacity,
        'Free Spots': free,
        'temperature': round(weather[0], 2),
        'description': weather[1],
        'humidity': weather[2],
        'rain': weather[3],
        'date': now.strftime("%d/%m/%Y"),
        'time': now.strftime("%H:%M:%S")
    })
    # Auslastung in Prozent
    df['occupation_percent'] = ((df['capacity'] - df['Free Spots']) / df['capacity'] * 100).round(2)
    return df

st.title("🚗 🅿️ Parking in Dresden")
coords = load_coordinates()
live_df = load_live_data()

# Merge
if "name" in coords.columns:
    live_df['name_lower'] = live_df['name'].str.lower()
    coords['name_lower'] = coords['name'].str.lower()
    merged = pd.merge(live_df, coords, on='name_lower', how='left')
else:
    merged = live_df.copy()

tab1, tab2 = st.tabs(["Live Data", "Prediction"])

with tab1:
    if st.button("🔄 Reload live data"):
        live_df = load_live_data()

    # KPIs
    total_capacity = merged['capacity'].sum()
    total_free = merged['Free Spots'].sum()
    total_occupancy = ((total_capacity - total_free) / total_capacity * 100).round(2)
    emptiest_row = merged.loc[merged['occupation_percent'].idxmin()]
    emptiest_name = emptiest_row['name_x'] if 'name_x' in emptiest_row else emptiest_row['name']
    emptiest_value = emptiest_row['occupation_percent']
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Overview")
        cols_to_show = [c for c in ['name_x','capacity','Free Spots','occupation_percent'] if c in merged.columns]
        renamed_df = merged[cols_to_show].rename(columns={
            'name_x': 'Parking Lot',
            'capacity': 'Capacity',
            'occupation_percent': 'Occupation %'
        })
        st.dataframe(renamed_df)
    with col2:
        st.metric(label="Total Occupancy", value=f"{total_occupancy}%")
        st.metric(label="Emptiest Parking Lot", value=f"{emptiest_name} ({emptiest_value}%)")

    st.markdown("---")

    # Karte nur mit Farben, kleine Punkte
    if 'lat' in merged.columns and 'lon' in merged.columns and not merged[['lat','lon']].dropna().empty:
        st.subheader("Map of parking lots in Dresden")
        merged['color'] = merged['occupation_percent'].apply(lambda x: [128,128,128] if pd.isna(x) else [int(255*x/100), int(255*(1-x/100)), 0])
        merged = merged.dropna(subset=['lat','lon'])
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=merged,
            get_position='[lon, lat]',
            get_fill_color='color',
            get_radius=100,
            pickable=True
        )
        view_state = pdk.ViewState(latitude=merged['lat'].mean(), longitude=merged['lon'].mean(), zoom=11)
        legend_html = """
        <div style='background-color:#333;color:white;padding:10px;border-radius:5px;'>
            <b>Legend:</b><br>
            <span style='color:lime;'>●</span> Empty<br>
            <span style='color:red;'>●</span> Full <br>
        </div>
        """
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{name_x}: {occupation_percent}% full"})
        st.pydeck_chart(r)
        st.markdown(legend_html, unsafe_allow_html=True)
    else:
        st.info("No working data found for the map.")       






def display_predictions_by_time(pred_df, coords):
    # Immer Slider verwenden mit schöneren Labels
    times = pd.Series(pred_df['Datetime'].unique())
    time_labels = times.dt.strftime('%d.%m %H:%M').tolist()
    # Standardwert auf Index 12 (60 Minuten)
    time_index = st.slider("Select Time (5 min steps for next 48h)", min_value=0, max_value=len(times)-1, value=12)
    selected_time = times.iloc[time_index]

    st.write(f"Predictions for {time_labels[time_index]}")
    filtered = pred_df[pred_df['Datetime'] == selected_time].copy()
    filtered['Datetime'] = filtered['Datetime'].dt.strftime('%d.%m. %H:%M')

    col_left, col_right = st.columns([2, 3])  # Linke Spalte größer machen
    with col_left:
        st.dataframe(filtered, use_container_width=True, hide_index=True, height=500)  # Mehr Höhe
    with col_right:
        # Karte mit grünen und roten Punkten
        merged_pred = pd.merge(filtered, coords, left_on='Parking Lot', right_on='name', how='left')
        merged_pred['color'] = merged_pred['Occupation (in %)'].apply(lambda x: [128,128,128] if pd.isna(x) else [int(255*x/100), int(255*(1-x/100)), 0])
        merged_pred = merged_pred.dropna(subset=['lat','lon'])
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=merged_pred,
            get_position='[lon, lat]',
            get_fill_color='color',
            get_radius=100,
            pickable=True
        )
        view_state = pdk.ViewState(latitude=merged_pred['lat'].mean(), longitude=merged_pred['lon'].mean(), zoom=11)
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{Parking Lot}: {Occupation (in %)}% full"})
        st.pydeck_chart(r)

with tab2:
    st.subheader("Prediction")

    use_external_model = st.toggle("Use External Model", value=False)

    if not use_external_model:
        # Minimalmodell mit wenigen Bäumen und geringer Tiefe
        df_train = merged.copy()
        df_train['hour'] = datetime.now().hour
        X = df_train[['capacity', 'hour']]
        y = df_train['occupation_percent']
        model = RandomForestRegressor(n_estimators=3, max_depth=2, random_state=42)
        model.fit(X, y)

        # Vorhersagen (48h, 5-Minuten-Takt)
        future_times = pd.date_range(datetime.now(), periods=48*12, freq='5T')
        predictions = []
        for name in merged['name_x']:
            cap = merged.loc[merged['name_x'] == name, 'capacity'].values[0]
            for t in future_times:
                pred_occ = model.predict([[cap, t.hour]])[0]
                predictions.append([name, t, round(pred_occ, 2)])
        pred_df = pd.DataFrame(predictions, columns=['Parking Lot', 'Datetime', 'Occupation (in %)'])

        display_predictions_by_time(pred_df, coords)
    else:
        # Externes Modell wird aus Datei geladen (Platzhalter)
        st.info("External model predictions yet to come.")











# Strich vor Debugging-Mode
st.markdown("---")
if st.toggle("Debugging Mode"):
    st.subheader("Koordinaten CSV")
    st.write(f"Erkannte Spalten: {list(coords.columns)}")
    st.dataframe(coords)
    st.subheader("Gemergte Rohdaten")
    st.dataframe(merged)
