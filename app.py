import os
import fastf1
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
import streamlit as st

# Cache 
os.makedirs('cache', exist_ok=True)
fastf1.Cache.enable_cache('cache')

st.title("🏎️ F1 Statistics Dashboard 🏁")

year = st.number_input("Select Year 📆", min_value=2018, max_value=2024, value=2021)

# Dropdown
tracks = [
    'Albert Park 🇦🇺', 'Bahrain 🇧🇭', 'Imola 🇮🇹', 'Miami 🇺🇸', 'Catalunya 🇪🇸', 'Monaco 🇲🇨', 'Baku 🇦🇿', 'Montreal 🇨🇦',
    'Red Bull Ring 🇦🇹', 'Silverstone 🇬🇧', 'Hungaroring 🇭🇺', 'Spa 🇮🇹', 'Zandvoort 🇳🇱', 'Monza 🇮🇹',
    'Singapore 🇸🇬', 'Suzuka 🇯🇵', 'Austin 🇺🇸', 'Mexico City 🇲🇽', 'Interlagos 🇧🇷', 'Las Vegas 🇺🇸', 'Yas Marina 🇦🇪'
]
track = st.selectbox("Select Circuit 🚥", options=tracks, index=tracks.index("Monza 🇮🇹"))

# Session Dropdown
session_types = {'Race': 'R', 'Qualifying': 'Q', 'Sprint': 'S'}
session_display = st.selectbox("Select Session Type", options=list(session_types.keys()))
session_code = session_types[session_display]

show_pit_stops = st.checkbox("Show Pit Stops", value=True)
show_colored_tyres = st.checkbox("Show Tyre Compound Colors", value=True)
show_fastest_lap = st.checkbox("Highlight Fastest Lap", value=True)

if st.button("Extract Data 📊"):
    try:
        session = fastf1.get_session(year, track, session_code)
        session.load()

        weather = session.weather_data.iloc[0] if not session.weather_data.empty else None
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

        team_colors = {
            'Red Bull Racing': '#1E41FF',
            'Ferrari': '#DC0000',
            'Mercedes': '#00D2BE',
            'McLaren': '#FF8700',
            'Alpine': '#0090FF',
            'Aston Martin': '#009150',
            'Alfa Romeo': '#A80000',
            'AlphaTauri': '#3E5F8A',
            'Haas F1 Team': '#C6C6C6',
            'Williams': '#007AFF'
        }

        laps = session.laps.copy().reset_index()
        laps['Abbreviation'] = laps['Driver']
        laps['CompoundChange'] = (laps['Compound'] != laps.groupby('Abbreviation')['Compound'].shift()).astype(int)
        laps['Stint'] = laps.groupby('Abbreviation')['CompoundChange'].cumsum()
        laps = laps.dropna(subset=['LapTime'])

        # Dropdown: Select Drivers
        available_drivers = sorted(laps['Abbreviation'].unique())
        selected_drivers = st.multiselect("Select Drivers", available_drivers, default=available_drivers)
        laps = laps[laps['Abbreviation'].isin(selected_drivers)]

        # Lap range filter
        max_lap = laps['LapNumber'].max()
        lap_range = st.slider("Select Lap Range", 1, int(max_lap), (1, int(max_lap)))
        laps = laps[(laps['LapNumber'] >= lap_range[0]) & (laps['LapNumber'] <= lap_range[1])]

        stints = laps.groupby(['Abbreviation', 'Stint', 'Compound']).agg(
            StartLap=('LapNumber', 'min'),
            EndLap=('LapNumber', 'max')
        ).reset_index()

        pit_stops = laps.loc[laps['PitOutTime'].notnull()].copy()
        pit_stops['PitDuration'] = (pit_stops['PitOutTime'] - pit_stops['PitInTime']).dt.total_seconds()

        pit_markers = pit_stops[['Driver', 'LapNumber', 'Compound']].copy()
        pit_markers['Abbreviation'] = pit_markers['Driver']
        pit_markers['TyreColor'] = pit_markers['Compound'].map({
            'Soft': 'red', 'Medium': 'yellow', 'Hard': 'white',
            'Intermediate': 'green', 'Wet': 'blue'
        }).fillna('gray')

        pit_lookup = pit_stops.set_index(['Driver', 'LapNumber'])['PitDuration'].to_dict()
        def get_pit_info(abbr, lap):
            key = (abbr, lap)
            duration = pit_lookup.get(key)
            return f"{duration:.2f}s" if duration else None

        stints['PitStop'] = stints.apply(lambda x: get_pit_info(x['Abbreviation'], x['EndLap']), axis=1)

        # Fastest Lap
        fastest = laps.loc[laps['LapTime'] == laps['LapTime'].min()]

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
                + (f" | Pit: {row['PitStop']}" if row['PitStop'] else '')
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

        if show_pit_stops:
            for _, row in pit_markers.iterrows():
                abbr = row['Abbreviation']
                lap = row['LapNumber']
                compound = row['Compound']
                color = row['TyreColor']
                duration = get_pit_info(abbr, lap)
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
            margin=dict(t=100, l=150, r=150, b=60),
            height=850,
            hovermode="closest"
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
