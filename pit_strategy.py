import os
import fastf1
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime

# =========================
# Cache setup
# =========================
os.makedirs('cache', exist_ok=True)
fastf1.Cache.enable_cache('cache')

# =========================
# Load session
# =========================
session = fastf1.get_session(2019, 'Silverstone', 'R')
session.load()

# =========================
# Official team colors
# =========================
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

# =========================
# Driver info
# =========================
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

# =========================
# Stints and Pit Stops
# =========================
laps = session.laps.copy().reset_index()
laps['Abbreviation'] = laps['Driver']
laps['CompoundChange'] = (laps['Compound'] != laps.groupby('Abbreviation')['Compound'].shift()).astype(int)
laps['Stint'] = laps.groupby('Abbreviation')['CompoundChange'].cumsum()

stints = laps.groupby(['Abbreviation', 'Stint', 'Compound']).agg(
    StartLap=('LapNumber', 'min'),
    EndLap=('LapNumber', 'max')
).reset_index()

pit_stops = session.laps.loc[session.laps['PitOutTime'].notnull()].copy()
pit_stops['PitDuration'] = (pit_stops['PitOutTime'] - pit_stops['PitInTime']).dt.total_seconds()

# Create a pit marker dataframe for visualization
pit_markers = pit_stops[['Driver', 'LapNumber', 'Compound']].copy()
pit_markers['Abbreviation'] = pit_markers['Driver']
pit_markers['TyreColor'] = pit_markers['Compound'].map({
    'Soft': 'red',
    'Medium': 'yellow',
    'Hard': 'white',
    'Intermediate': 'green',
    'Wet': 'blue'
}).fillna('gray')

# Create a quick lookup dictionary for pit stop durations
pit_lookup = pit_stops.set_index(['Driver', 'LapNumber'])['PitDuration'].to_dict()

def get_pit_info(abbr, lap):
    key = (abbr, lap)
    duration = pit_lookup.get(key)
    return f"{duration:.2f}s" if duration else None

stints['PitStop'] = stints.apply(lambda x: get_pit_info(x['Abbreviation'], x['EndLap']), axis=1)

# =========================
# Chart creation
# =========================
fig = go.Figure()
driver_order = sorted(stints['Abbreviation'].unique(), reverse=True)

for _, row in stints.iterrows():
    abbr = row['Abbreviation']
    team = driver_info[abbr]['TeamName']
    color = team_colors.get(team, '#888888')
    tyre = row['Compound'].title() if row['Compound'] else "Unknown"
    hovertext = (
        f"<b>{abbr}</b> | {team} | {tyre}<br>"
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

# Add pit stop markers
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

# =========================
# Fastest lap
# =========================
fastest_lap = session.laps.pick_fastest()
fastest_abbr = fastest_lap['Driver']
fastest_lap_num = fastest_lap['LapNumber']
fastest_time = str(fastest_lap['LapTime'])[:-3]

fig.add_vline(
    x=fastest_lap_num,
    line=dict(color="purple", width=2, dash="dot"),
    annotation_text=f"Fastest Lap ({fastest_abbr})",
    annotation_position="top",
    annotation_font_color="white"
)

# =========================
# Safety car
# =========================
sc_msgs = session.race_control_messages
sc_laps = sorted(sc_msgs[sc_msgs['Message'].str.contains("SAFETY CAR", case=False, na=False)]['Lap'].dropna().unique())

for lap in sc_laps:
    fig.add_vrect(
        x0=lap - 0.5, x1=lap + 2.5,
        fillcolor="yellow", opacity=0.15,
        layer="below", line_width=0
    )

# =========================
# Weather & race info
# =========================
weather = session.weather_data.iloc[0]
weather_icons = "☀️"
if weather['Humidity'] > 90:
    weather_icons = "🌧"
elif weather['Humidity'] > 80:
    weather_icons = "☁️"

weather_text = (
    f"{weather_icons}  Air: {weather['AirTemp']:.1f}°C | Track: {weather['TrackTemp']:.1f}°C | "
    f"Humidity: {weather['Humidity']:.0f}% | Wind: {weather['WindSpeed']:.1f} m/s"
)

race_name = f"Formula 1 - {session.event['EventName']} {session.event.year}"
race_date = datetime.fromisoformat(str(session.event['EventDate'])).strftime("%d %B %Y")

fig.add_annotation(
    xref="paper", yref="paper",
    x=0.5, y=1.15,
    text=f"<b style='font-size:20px'>{race_name}</b><br><span style='color:yellow'>{race_date} — {weather_text}</span>",
    showarrow=False,
    font=dict(size=16, color="white"),
    align="center"
)

# =========================
# Starting Grid
# =========================
results = session.results
starting_grid = results.sort_values('GridPosition')
grid_text = "<b>Starting Grid</b><br>" + "<br>".join(
    f"{int(row['GridPosition'])}. {driver_info[row['Abbreviation']]['FullName']} ({row['Abbreviation']})"
    for _, row in starting_grid.iterrows()
)
fig.add_annotation(
    xref="paper", yref="paper",
    x=-0.9, y=1.09,
    text=grid_text,
    showarrow=False,
    font=dict(size=12, color="white"),
    align="left",
    bgcolor="#111111",
    bordercolor="white",
    borderwidth=1
)

# =========================
# Podium
# =========================
podium = results.nsmallest(3, 'Position')
podium_text = "<b>Podium</b><br>" + "<br>".join(
    f"{int(row['Position'])}. {driver_info[row['Abbreviation']]['FullName']} ({row['Abbreviation']})"
    for _, row in podium.iterrows()
)
fig.add_annotation(
    xref="paper", yref="paper",
    x=1.0, y=1.09,
    text=podium_text,
    showarrow=False,
    font=dict(size=12, color="white"),
    align="left",
    bgcolor="#111111",
    bordercolor="white",
    borderwidth=1
)

# =========================
# Layout styling
# =========================
fig.update_layout(
    xaxis=dict(title="Lap Number", showgrid=True, gridcolor='rgba(255,255,255,0.1)', zeroline=False, color='white'),
    yaxis=dict(title="Drivers", categoryorder='array', categoryarray=driver_order, color='white'),
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    margin=dict(t=200, l=200, r=200, b=60),
    height=950,
    hovermode="closest",
    title=dict(text="", x=0.5)
)

fig.show()
