import os
import fastf1
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
import streamlit as st

# Cache setup
os.makedirs('cache', exist_ok=True)
fastf1.Cache.enable_cache('cache')

st.set_page_config(page_title="🏎️ F1 Statistics Dashboard", layout="wide")
st.title("🏎️ F1 Statistics Dashboard 🏁")

# ---------------- UI inputs ----------------
year = st.number_input("Select Year 📆", min_value=2018, max_value=2024, value=2021)

tracks = [
    'Albert Park 🇦🇺', 'Bahrain 🇧🇭', 'Imola 🇮🇹', 'Miami 🇺🇸', 'Catalunya 🇪🇸', 'Monaco 🇲🇨', 'Baku 🇦🇿', 'Montreal 🇨🇦',
    'Red Bull Ring 🇦🇹', 'Silverstone 🇬🇧', 'Hungaroring 🇭🇺', 'Spa 🇧🇪', 'Zandvoort 🇳🇱', 'Monza 🇮🇹',
    'Singapore 🇸🇬', 'Suzuka 🇯🇵', 'Austin 🇺🇸', 'Mexico City 🇲🇽', 'Interlagos 🇧🇷', 'Las Vegas 🇺🇸', 'Yas Marina 🇦🇪'
]
track = st.selectbox("Select Circuit 🚥", options=tracks, index=tracks.index("Monza 🇮🇹"))

session_types = {'Race': 'R', 'Qualifying': 'Q', 'Sprint': 'S'}
session_display = st.selectbox("Select Session Type", options=list(session_types.keys()))
session_code = session_types[session_display]

show_pit_stops = st.checkbox("Show Pit Stops", value=True)
show_colored_tyres = st.checkbox("Show Tyre Compound Colors", value=True)
show_fastest_lap = st.checkbox("Highlight Fastest Lap", value=True)

# ---------------- Persisted state keys ----------------
if "session_loaded" not in st.session_state:
    st.session_state.session_loaded = False
    st.session_state.session_obj = None
    st.session_state.laps = None
    st.session_state.driver_info = None
    st.session_state.stints = None
    st.session_state.pit_markers = None
    st.session_state.pit_lookup = None
    st.session_state.fastest = None
    st.session_state.available_drivers = []
    st.session_state.weather_df = None

# helper function used later (kept same behavior)
def get_pit_info_from_lookup(lookup, abbr, lap):
    key = (abbr, lap)
    duration = lookup.get(key)
    return f"{duration:.2f}s" if duration else None

# ---------------- Extract Data Button ----------------
if st.button("Extract Data 📊"):
    try:
        session = fastf1.get_session(year, track, session_code)
        session.load()

        # save session obj for weather tab
        st.session_state.session_obj = session

        # driver info
        drivers = session.drivers
        driver_info = {}
        for drv in drivers:
            drv_data = session.get_driver(drv)
            abbr = drv_data['Abbreviation']
            driver_info[abbr] = {
                'Abbreviation': abbr,
                'FullName': drv_data['FullName'],
                'TeamName': drv_data['TeamName'],
                'Number': drv_data['DriverNumber']
            }

        # Official F1 team colors (kept consistent with your earlier request)
        team_colors = {
            'Red Bull Racing': '#3671C6',
            'Ferrari': '#E8002D',
            'Mercedes': '#00D2BE',
            'McLaren': '#FF8000',
            'Alpine': '#0090FF',
            'Aston Martin': '#229971',
            'Alfa Romeo': '#900000',
            'AlphaTauri': '#2B4562',
            'Haas F1 Team': '#FFFFFF',
            'Williams': '#005AFF'
        }

        # laps & stints
        laps = session.laps.copy().reset_index()
        laps['Abbreviation'] = laps['Driver']
        laps['CompoundChange'] = (laps['Compound'] != laps.groupby('Abbreviation')['Compound'].shift()).astype(int)
        laps['Stint'] = laps.groupby('Abbreviation')['CompoundChange'].cumsum()
        laps = laps.dropna(subset=['LapTime'])

        stints = laps.groupby(['Abbreviation', 'Stint', 'Compound']).agg(
            StartLap=('LapNumber', 'min'),
            EndLap=('LapNumber', 'max')
        ).reset_index()

        # pit stops & markers
        pit_stops = laps.loc[laps['PitOutTime'].notnull()].copy()
        if not pit_stops.empty:
            pit_stops['PitDuration'] = (pit_stops['PitOutTime'] - pit_stops['PitInTime']).dt.total_seconds()
        pit_markers = pit_stops[['Driver', 'LapNumber', 'Compound']].copy()
        pit_markers['Abbreviation'] = pit_markers['Driver']
        pit_markers['TyreColor'] = pit_markers['Compound'].map({
            'Soft': 'red', 'Medium': 'yellow', 'Hard': 'white',
            'Intermediate': 'green', 'Wet': 'blue'
        }).fillna('gray')

        pit_lookup = {}
        if not pit_stops.empty:
            pit_lookup = pit_stops.set_index(['Driver', 'LapNumber'])['PitDuration'].to_dict()

        fastest = laps.loc[laps['LapTime'] == laps['LapTime'].min()]

        # weather (may be empty)
        weather_df = None
        try:
            if not session.weather_data.empty:
                weather_df = session.weather_data.copy().reset_index(drop=True)
                # convert times if string-like; else keep as-is
                if 'Time' in weather_df.columns:
                    try:
                        weather_df['Time'] = pd.to_datetime(weather_df['Time'])
                    except Exception:
                        pass

        except Exception:
            weather_df = None

        # Save everything into session_state (so widget changes won't clear data)
        st.session_state.session_loaded = True
        st.session_state.laps = laps
        st.session_state.driver_info = driver_info
        st.session_state.stints = stints
        st.session_state.pit_markers = pit_markers
        st.session_state.pit_lookup = pit_lookup
        st.session_state.fastest = fastest
        st.session_state.team_colors = team_colors
        st.session_state.available_drivers = sorted(laps['Abbreviation'].unique())
        st.session_state.weather_df = weather_df

        st.success("Session loaded — scroll down to view tabs.")
    except Exception as e:
        st.error(f"Error: {e}")

# ---------------- If data loaded, show tabs and charts ----------------
if st.session_state.session_loaded and st.session_state.laps is not None:
    laps = st.session_state.laps
    driver_info = st.session_state.driver_info
    stints = st.session_state.stints
    pit_markers = st.session_state.pit_markers
    pit_lookup = st.session_state.pit_lookup
    fastest = st.session_state.fastest
    team_colors = st.session_state.team_colors
    available_drivers = st.session_state.available_drivers
    weather_df = st.session_state.weather_df
    session_obj = st.session_state.session_obj

    # Keep your same tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Stints & Pit Stops", "Sector Times", "Lap Delta", "Position Changes", "Weather & Track Data"])

    # ---------------- Tab 1: Stints & Pit Stops ----------------
    with tab1:
        fig = go.Figure()
        driver_order = sorted(stints['Abbreviation'].unique(), reverse=True)

        for _, row in stints.iterrows():
            abbr = row['Abbreviation']
            team = driver_info[abbr]['TeamName']
            color = team_colors.get(team, '#888888') if show_colored_tyres else 'gray'
            tyre = row['Compound'].title() if row['Compound'] else "Unknown"
            name = driver_info[abbr]['FullName']
            hovertext = (
                f"<b>{name} ({abbr})</b> | {team} | {tyre}<br>"
                f"Laps {row['StartLap']}–{row['EndLap']}"
                + (f" | Pit: {get_pit_info_from_lookup(pit_lookup, row['Abbreviation'], row['EndLap'])}" if get_pit_info_from_lookup(pit_lookup, row['Abbreviation'], row['EndLap']) else '')
            )
            fig.add_trace(go.Scatter(
                x=[row['StartLap'], row['EndLap']],
                y=[abbr, abbr],
                mode="lines",
                line=dict(color=color, width=10),
                hoverinfo="text",
                hovertext=hovertext,
                showlegend=False
            ))

        if show_pit_stops and not pit_markers.empty:
            for _, row in pit_markers.iterrows():
                abbr = row['Abbreviation']
                lap = row['LapNumber']
                compound = row['Compound']
                color = row['TyreColor']
                duration = get_pit_info_from_lookup(pit_lookup, abbr, lap)
                fig.add_trace(go.Scatter(
                    x=[lap],
                    y=[abbr],
                    mode="markers",
                    marker=dict(color=color, size=10, symbol='circle'),
                    hovertext=f"Pit Stop | Lap {lap} | {duration}<br>Tyre: {compound}",
                    hoverinfo="text",
                    showlegend=False
                ))

        if show_fastest_lap and not fastest.empty:
            for _, row in fastest.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['LapNumber']],
                    y=[row['Abbreviation']],
                    mode="markers+text",
                    marker=dict(size=16, color='gold', symbol='star'),
                    text=[f"Fastest Lap ({row['Abbreviation']} - {str(row['LapTime']).split('0 days ')[-1]})"],
                    textposition="top center",
                    hoverinfo="text"
                ))

        fig.update_layout(
            xaxis=dict(title="Lap Number", showgrid=True, gridcolor='rgba(255,255,255,0.1)', zeroline=False, color='white'),
            yaxis=dict(title="Drivers", categoryorder='array', categoryarray=driver_order, color='white'),
            plot_bgcolor='black',
            paper_bgcolor='black',
            font=dict(color='white'),
            height=850,
            hovermode="closest",
            margin=dict(t=100, l=150, r=150, b=60)
        )
        st.plotly_chart(fig, use_container_width=True)

        # ---------------- Tab 2: Sector Times ---------------- #
        with tab2:
            sector_best = laps.groupby('Abbreviation').agg(
                Sector1=('Sector1Time', 'min'),
                Sector2=('Sector2Time', 'min'),
                Sector3=('Sector3Time', 'min')
            ).reset_index()
            for col in ['Sector1', 'Sector2', 'Sector3']:
                sector_best[col] = sector_best[col].dt.total_seconds()

            fig_sector = go.Figure()
            for sector in ['Sector1', 'Sector2', 'Sector3']:
                fig_sector.add_trace(go.Bar(
                    x=sector_best['Abbreviation'],
                    y=sector_best[sector],
                    name=sector
                ))
            fig_sector.update_layout(barmode='group', title="Best Sector Times (seconds)", plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
            st.plotly_chart(fig_sector, use_container_width=True)


    # ---------------- Tab 3: Lap Delta ----------------
    with tab3:
        # maintain previous driver choices across reruns using session_state
        if "driver_a" not in st.session_state:
            st.session_state.driver_a = available_drivers[0] if available_drivers else None
        if "driver_b" not in st.session_state:
            st.session_state.driver_b = available_drivers[1] if len(available_drivers) > 1 else available_drivers[0] if available_drivers else None

        # driver selectboxes (indexes set from session_state so changing them doesn't clear session)
        if available_drivers:
            driver_a = st.selectbox("Select Driver A", available_drivers, index=available_drivers.index(st.session_state.driver_a) if st.session_state.driver_a in available_drivers else 0)
            driver_b = st.selectbox("Select Driver B", available_drivers, index=available_drivers.index(st.session_state.driver_b) if st.session_state.driver_b in available_drivers else (1 if len(available_drivers)>1 else 0))
            st.session_state.driver_a = driver_a
            st.session_state.driver_b = driver_b

            laps_a = laps[laps['Abbreviation'] == driver_a]
            laps_b = laps[laps['Abbreviation'] == driver_b]

            # merge on LapNumber — handle missing laps gracefully
            merged = pd.merge(laps_a[['LapNumber', 'LapTime']], laps_b[['LapNumber', 'LapTime']], on='LapNumber', suffixes=('_A', '_B'))
            if not merged.empty:
                merged['Delta'] = (merged['LapTime_A'] - merged['LapTime_B']).dt.total_seconds()

                fig_delta = go.Figure()
                # color lines by team (driver B color used for positive/negative interpretation)
                color_a = team_colors.get(driver_info[driver_a]['TeamName'], '#888888')
                color_b = team_colors.get(driver_info[driver_b]['TeamName'], '#888888')

                fig_delta.add_trace(go.Scatter(x=merged['LapNumber'], y=merged['Delta'], mode='lines+markers',
                                              marker=dict(color=color_b), line=dict(color=color_b)))
                fig_delta.update_layout(title=f"Lap Time Delta: {driver_a} vs {driver_b} (Positive = {driver_b} faster)", plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
                st.plotly_chart(fig_delta, use_container_width=True)
            else:
                st.warning("No overlapping lap numbers between selected drivers to compute delta.")
        else:
            st.warning("No drivers available for this session.")

    # ---------------- Tab 4: Position Changes ----------------
    with tab4:
        pos_data = laps.groupby(['LapNumber', 'Abbreviation'])['Position'].mean().reset_index()
        fig_pos = go.Figure()
        for drv in sorted(set(laps['Abbreviation'])):
            d = pos_data[pos_data['Abbreviation'] == drv]
            fig_pos.add_trace(go.Scatter(
                x=d['LapNumber'],
                y=d['Position'],
                mode='lines',
                name=drv,
                line=dict(color=team_colors.get(driver_info[drv]['TeamName'], '#888888'))
            ))
        fig_pos.update_yaxes(autorange='reversed')  # P1 at top
        fig_pos.update_layout(title="Position Changes Over Race", plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
        st.plotly_chart(fig_pos, use_container_width=True)

    # ---------------- Tab 5: Weather & Track Data ----------------
    with tab5:
        if weather_df is not None and not weather_df.empty:
            # show some summary values (use first row as "start" values if present)
            first_row = weather_df.iloc[0]
            # defensive: some sessions have different column names; try present ones
            air_temp = first_row.get('AirTemp') if 'AirTemp' in weather_df.columns else None
            track_temp = first_row.get('TrackTemp') if 'TrackTemp' in weather_df.columns else None
            humidity = first_row.get('Humidity') if 'Humidity' in weather_df.columns else None
            wind_speed = first_row.get('WindSpeed') if 'WindSpeed' in weather_df.columns else None
            wind_dir = first_row.get('WindDirection') if 'WindDirection' in weather_df.columns else None

            st.subheader("Weather Summary (start of session)")
            if air_temp is not None:
                st.markdown(f"**Air Temp:** {air_temp:.1f} °C")
            if track_temp is not None:
                st.markdown(f"**Track Temp:** {track_temp:.1f} °C")
            if humidity is not None:
                st.markdown(f"**Humidity:** {humidity:.0f} %")
            if wind_speed is not None:
                st.markdown(f"**Wind Speed:** {wind_speed:.1f} km/h")
            if wind_dir is not None:
                st.markdown(f"**Wind Direction:** {wind_dir:.0f}°")

            # Build time series plot with available columns
            fig_weather = go.Figure()
            # prefer a datetime-like x axis if present
            x = weather_df['Time'] if 'Time' in weather_df.columns else weather_df.index

            if 'AirTemp' in weather_df.columns:
                fig_weather.add_trace(go.Scatter(x=x, y=weather_df['AirTemp'], mode='lines', name='Air Temp (°C)'))
            if 'TrackTemp' in weather_df.columns:
                fig_weather.add_trace(go.Scatter(x=x, y=weather_df['TrackTemp'], mode='lines', name='Track Temp (°C)'))
            if 'Humidity' in weather_df.columns:
                fig_weather.add_trace(go.Scatter(x=x, y=weather_df['Humidity'], mode='lines', name='Humidity (%)'))
            if 'WindSpeed' in weather_df.columns:
                fig_weather.add_trace(go.Scatter(x=x, y=weather_df['WindSpeed'], mode='lines', name='Wind Speed'))

            fig_weather.update_layout(title="Weather & Track Conditions Over Session", plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'), hovermode='x unified')
            st.plotly_chart(fig_weather, use_container_width=True)

            # show count of weather descriptions if present
            if 'Weather' in weather_df.columns:
                st.markdown("**Weather Descriptions (counts)**")
                st.write(weather_df['Weather'].value_counts())
        else:
            st.warning("No weather data available for this session.")
else:
    st.info("Load a session first using 'Extract Data 📊' to see charts and the Weather & Track Data tab.")
