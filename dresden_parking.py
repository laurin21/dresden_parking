import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import pydeck as pdk
from sklearn.ensemble import RandomForestRegressor
import numpy as np
from bs4 import BeautifulSoup

st.set_page_config(page_title="Parking in Dresden", layout="wide")

# --- JSON mit HTML-Fallback ---
def scrap_parking():
    url_json = "https://www.dresden.de/apps_ext/ParkplatzApp/data.json"
    try:
        r = requests.get(url_json, timeout=5)
        if r.status_code == 200 and r.text.strip().startswith("{"):
            data = r.json()
            if 'parking' in data:
                df = pd.DataFrame([{ 
                    "name": p["name"],
                    "capacity": p["max"],
                    "Free Spots": p["free"],
                    "occupation_percent": round((p["max"]-p["free"])/p["max"]*100,2) if p["max"] else 0
                } for p in data['parking']])
                return df.fillna(0)
    except Exception as e:
        st.warning(f"Fehler JSON: {e}, versuche HTML...")

    # HTML-Fallback
    try:
        url_html = "https://www.dresden.de/apps_ext/ParkplatzApp/index"
        r = requests.get(url_html, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("div", class_="contentsection").find("table")
        rows = table.find_all("tr")
        name, capacity, free = [], [], []
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 3:
                n = cols[0].get_text(strip=True)
                cap = cols[1].get_text(strip=True)
                fr = cols[2].get_text(strip=True)
                if cap.isdigit() and fr.isdigit():
                    name.append(n)
                    capacity.append(int(cap))
                    free.append(int(fr))
        df = pd.DataFrame({"name": name, "capacity": capacity, "Free Spots": free})
        df["occupation_percent"] = ((df["capacity"] - df["Free Spots"]) / df["capacity"] * 100).round(2)
        return df.fillna(0)
    except Exception as e:
        st.error(f"Fehler HTML-Scraping: {e}")
        return pd.DataFrame(columns=["name","capacity","Free Spots","occupation_percent"])

def scrap_weather():
    return [20.0, "Clear", 50, 0]

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
    df = scrap_parking()
    if df.empty:
        return df
    weather = scrap_weather()
    now = datetime.now()
    df["temperature"] = round(weather[0], 2)
    df["description"] = weather[1]
    df["humidity"] = weather[2]
    df["rain"] = weather[3]
    df["date"] = now.strftime("%d/%m/%Y")
    df["time"] = now.strftime("%H:%M:%S")
    return df

st.title("🚗 🅿️ Parking in Dresden")
coords = load_coordinates()
live_df = load_live_data()

if live_df.empty:
    st.error("Keine Live-Daten verfügbar.")
else:
    # Merge
    if "name" in coords.columns and "name" in live_df.columns:
        live_df['name'] = live_df['name'].astype(str)
        coords['name'] = coords['name'].astype(str)
        live_df['name_lower'] = live_df['name'].str.lower()
        coords['name_lower'] = coords['name'].str.lower()
        merged = pd.merge(live_df, coords, on='name_lower', how='left')
    else:
        merged = live_df.copy()

    # Sicherere Berechnung des Emptiest Parking Lot
    if 'occupation_percent' in merged.columns and merged['occupation_percent'].notna().any():
        try:
            idx_min = merged['occupation_percent'].idxmin()
            emptiest_row = merged.loc[idx_min]
            emptiest_name = emptiest_row.get('name_x', emptiest_row.get('name', 'N/A'))
            emptiest_value = emptiest_row['occupation_percent']
        except Exception:
            emptiest_name = "N/A"
            emptiest_value = "N/A"
    else:
        emptiest_name = "N/A"
        emptiest_value = "N/A"

    tab1, tab2 = st.tabs(["Live Data", "Prediction"])

    with tab1:
        if st.button("🔄 Reload live data"):
            live_df = load_live_data()

        total_capacity = merged['capacity'].sum()
        total_free = merged['Free Spots'].sum()
        total_occupancy = ((total_capacity - total_free) / total_capacity * 100).round(2)

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
            r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{name_x}: {occupation_percent}% full"})
            st.pydeck_chart(r)
        else:
            st.info("No working data found for the map.")

    def display_predictions_by_time(pred_df, coords):
        times = pd.Series(pred_df['Datetime'].unique())
        time_labels = times.dt.strftime('%d.%m %H:%M').tolist()
        time_index = st.slider("Select Time (5 min steps for next 48h)", min_value=0, max_value=len(times)-1, value=12)
        selected_time = times.iloc[time_index]

        st.write(f"Predictions for {time_labels[time_index]}")
        filtered = pred_df[pred_df['Datetime'] == selected_time].copy()
        filtered['Datetime'] = filtered['Datetime'].dt.strftime('%d.%m. %H:%M')

        col_left, col_right = st.columns([2, 3])
        with col_left:
            st.dataframe(filtered, use_container_width=True, hide_index=True, height=500)
        with col_right:
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

        if not use_external_model and not live_df.empty:
            df_train = merged.copy()
            df_train['hour'] = datetime.now().hour
            df_train = df_train.dropna(subset=['capacity','hour','occupation_percent'])
            X = df_train[['capacity', 'hour']]
            y = df_train['occupation_percent']
            if not X.empty and not y.empty:
                model = RandomForestRegressor(n_estimators=3, max_depth=2, random_state=42)
                model.fit(X, y)

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
                st.warning("Not enough valid data for training the model.")
        else:
            st.info("External model predictions yet to come.")

st.markdown("---")
if st.toggle("Debugging Mode"):
    st.subheader("Koordinaten CSV")
    st.write(f"Erkannte Spalten: {list(coords.columns)}")
    st.dataframe(coords)
    st.subheader("Gemergte Rohdaten")
    st.dataframe(live_df)
