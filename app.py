import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import folium_static
import uuid
import math
import plotly.express as px
import streamlit.components.v1 as components

# Simplified LOCATIONS dictionary (expand as needed)
LOCATIONS = {
    'United Kingdom': {
        'London': (51.5074, -0.1278),
        'Manchester': (53.4808, -2.2426),
        'Birmingham': (52.4862, -1.8904)
    },
    'United States': {
        'New York': (40.7128, -74.0060),
        'Los Angeles': (34.0522, -118.2437),
        'Chicago': (41.8781, -87.6298)
    },
    'Japan': {
        'Tokyo': (35.6895, 139.6503),
        'Osaka': (34.6937, 135.5023),
        'Yokohama': (35.4437, 139.6380)
    },
    'Nigeria': {
        'Lagos': (6.5244, 3.3792),
        'Abuja': (9.0579, 7.4951),
        'Kano': (12.0001, 8.5167)
    },
    'Brazil': {
        'São Paulo': (-23.5505, -46.6333),
        'Rio de Janeiro': (-22.9068, -43.1729),
        'Brasília': (-15.8267, -47.9218)
    }
}

# Emission factors (kg CO₂ per km per ton)
EMISSION_FACTORS = {
    'Truck': 0.096, 'Train': 0.028, 'Ship': 0.016, 'Plane': 0.602,
    'Electric Truck': 0.020, 'Biofuel Truck': 0.050, 'Hydrogen Truck': 0.010
}

def init_db():
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS emissions 
                        (id TEXT PRIMARY KEY, source TEXT, destination TEXT, 
                         transport_mode TEXT, distance_km REAL, co2_kg REAL, 
                         weight_tons REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database initialization failed: {e}")
        raise

def get_coordinates(country, city):
    return LOCATIONS.get(country, {}).get(city, (0, 0))

def calculate_distance(country1, city1, country2, city2):
    lat1, lon1 = get_coordinates(country1, city1)
    lat2, lon2 = get_coordinates(country2, city2)
    if lat1 == 0 and lon1 == 0 or lat2 == 0 and lon2 == 0:
        raise ValueError(f"Coordinates not found for {city1}, {country1} or {city2}, {country2}")
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

def calculate_co2(country1, city1, country2, city2, transport_mode, distance_km, weight_tons):
    emission_factor = EMISSION_FACTORS.get(transport_mode)
    if emission_factor is None:
        raise ValueError(f"Invalid transport mode: {transport_mode}")
    co2_kg = distance_km * weight_tons * emission_factor
    return round(co2_kg, 2)

def optimize_route(country1, city1, country2, city2, distance_km, weight_tons, prioritize_green=False):
    intercontinental = country1 != country2
    distance_short = distance_km < 1000
    distance_medium = 1000 <= distance_km < 5000
    distance_long = distance_km >= 5000
    current_co2 = distance_km * weight_tons * EMISSION_FACTORS['Truck']
    combinations = []
    if intercontinental:
        if distance_long:
            combinations.extend([
                ('Ship', 0.9, 'Train', 0.1),
                ('Ship', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Ship', 0.8, 'Truck', 0.2),
            ])
        elif distance_medium:
            combinations.extend([
                ('Ship', 0.7, 'Train', 0.3),
                ('Plane', 0.4, 'Hydrogen Truck', 0.6) if prioritize_green else ('Plane', 0.4, 'Truck', 0.6),
            ])
        else:
            combinations.extend([
                ('Train', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Train', 0.8, 'Truck', 0.2),
            ])
    else:
        if distance_short:
            combinations.extend([
                ('Train', 0.9, 'Electric Truck', 0.1) if prioritize_green else ('Train', 0.9, 'Truck', 0.1),
                ('Electric Truck', 1.0, None, 0.0) if prioritize_green else ('Truck', 1.0, None, 0.0),
            ])
        else:
            combinations.extend([
                ('Train', 0.7, 'Biofuel Truck', 0.3) if prioritize_green else ('Train', 0.7, 'Truck', 0.3),
            ])
    best_option = None
    min_co2 = float('inf')
    best_breakdown = None
    best_distances = None
    for mode1, ratio1, mode2, ratio2 in combinations:
        dist1 = distance_km * ratio1
        dist2 = distance_km * ratio2 if mode2 else 0
        co2_1 = dist1 * weight_tons * EMISSION_FACTORS[mode1]
        co2_2 = dist2 * weight_tons * EMISSION_FACTORS[mode2] if mode2 else 0
        total_co2 = co2_1 + co2_2
        if total_co2 < min_co2:
            min_co2 = total_co2
            best_option = (mode1, ratio1, mode2, ratio2)
            best_breakdown = (co2_1, co2_2)
            best_distances = (dist1, dist2)
    return best_option, round(min_co2, 2), best_breakdown, best_distances, round(current_co2, 2)

def save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            emission_id = str(uuid.uuid4())
            c.execute('INSERT INTO emissions (id, source, destination, transport_mode, distance_km, co2_kg, weight_tons, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (emission_id, source, destination, transport_mode, distance_km, co2_kg, weight_tons))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Failed to save emission data: {e}")

def main():
    st.set_page_config(page_title="Carbon 360", layout="wide", initial_sidebar_state="expanded")

    # Inject Tailwind CSS
    components.html("""
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .nav-item { 
            transition: all 0.3s ease; 
            padding: 0.5rem 1rem; 
            border-radius: 0.5rem; 
            margin: 0.25rem 0;
        }
        .nav-item:hover { background-color: #e6fffa; }
        .nav-item-active { background-color: #10b981; color: white; }
        .card { 
            background: white; 
            border-radius: 1rem; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
            padding: 1.5rem; 
            margin-bottom: 1.5rem;
        }
        .btn-primary {
            background: linear-gradient(to right, #10b981, #059669);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            background: linear-gradient(to right, #059669, #047857);
            transform: translateY(-1px);
        }
        .header { 
            background: linear-gradient(to right, #10b981, #059669); 
            color: white; 
            padding: 1rem 2rem; 
            border-radius: 0.5rem; 
            margin-bottom: 2rem;
        }
        .sidebar { 
            background: #f7fafc; 
            border-right: 1px solid #e2e8f0; 
            padding: 1rem;
        }
        .metric-card {
            background: #f7fafc;
            border-radius: 0.5rem;
            padding: 1rem;
            text-align: center;
        }
    </style>
    """, height=0)

    # Initialize database
    try:
        init_db()
    except Exception as e:
        st.error(f"Application failed to start: {e}")
        return

    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state.page = "Calculate Emissions"
    if 'source_country' not in st.session_state or st.session_state.source_country not in LOCATIONS:
        st.session_state.source_country = next(iter(LOCATIONS))
    if 'source_city' not in st.session_state or st.session_state.source_city not in LOCATIONS[st.session_state.source_country]:
        st.session_state.source_city = next(iter(LOCATIONS[st.session_state.source_country]))
    if 'dest_country' not in st.session_state or st.session_state.dest_country not in LOCATIONS:
        st.session_state.dest_country = next(iter(LOCATIONS))
    if 'dest_city' not in st.session_state or st.session_state.dest_city not in LOCATIONS[st.session_state.dest_country]:
        st.session_state.dest_city = next(iter(LOCATIONS[st.session_state.dest_country]))
    if 'weight_tons' not in st.session_state:
        st.session_state.weight_tons = 1.0

    # Header
    st.markdown("""
    <div class="header flex items-center justify-between">
        <div class="flex items-center space-x-4">
            <img src="https://via.placeholder.com/40" class="rounded-full" alt="Logo">
            <h1 class="text-2xl font-bold">Carbon 360</h1>
        </div>
        <div class="text-sm">Sustainable Logistics Solutions</div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold mb-4 text-gray-800">Navigation</h2>', unsafe_allow_html=True)
        pages = [
            ("Calculate Emissions", "📊"),
            ("Optimized Route Planning", "🚚")
        ]
        for page_name, icon in pages:
            is_active = st.session_state.page == page_name
            st.markdown(
                f'<button class="nav-item w-full text-left {"nav-item-active" if is_active else ""}" onclick="st.session_state.page=\'{page_name}\';st.experimental_rerun()">{icon} {page_name}</button>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # Main content
    st.markdown('<div class="container mx-auto px-4 py-6">', unsafe_allow_html=True)

    try:
        if st.session_state.page == "Calculate Emissions":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Calculate CO₂ Emissions</h2>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 1], gap="large")

            with col1:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Source</h3>', unsafe_allow_html=True)
                source_country = st.selectbox(
                    "Source Country",
                    sorted(LOCATIONS.keys()),
                    index=sorted(LOCATIONS.keys()).index(st.session_state.source_country) if st.session_state.source_country in LOCATIONS else 0,
                    key="calc_source_country"
                )
                source_city = st.selectbox(
                    "Source City",
                    sorted(LOCATIONS[source_country].keys()),
                    index=sorted(LOCATIONS[source_country].keys()).index(st.session_state.source_city) if st.session_state.source_city in LOCATIONS[source_country] else 0,
                    key="calc_source_city"
                )
                st.session_state.source_country = source_country
                st.session_state.source_city = source_city

                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700 mt-6">Destination</h3>', unsafe_allow_html=True)
                dest_country = st.selectbox(
                    "Destination Country",
                    sorted(LOCATIONS.keys()),
                    index=sorted(LOCATIONS.keys()).index(st.session_state.dest_country) if st.session_state.dest_country in LOCATIONS else 0,
                    key="calc_dest_country"
                )
                dest_city = st.selectbox(
                    "Destination City",
                    sorted(LOCATIONS[dest_country].keys()),
                    index=sorted(LOCATIONS[dest_country].keys()).index(st.session_state.dest_city) if st.session_state.dest_city in LOCATIONS[dest_country] else 0,
                    key="calc_dest_city"
                )
                st.session_state.dest_country = dest_country
                st.session_state.dest_city = dest_city

            with col2:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Shipment Details</h3>', unsafe_allow_html=True)
                transport_mode = st.selectbox("Transport Mode", list(EMISSION_FACTORS.keys()), key="calc_transport_mode")
                weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1, key="calc_weight")
                st.session_state.weight_tons = weight_tons
                try:
                    distance_km = calculate_distance(source_country, source_city, dest_country, dest_city)
                    st.markdown(f'<p class="text-gray-600">Estimated Distance: <span class="font-semibold">{distance_km} km</span></p>', unsafe_allow_html=True)
                except ValueError as e:
                    st.error(str(e))
                    distance_km = 0.0

            st.markdown('<div class="mt-6">', unsafe_allow_html=True)
            if st.button("Calculate", key="calc_button", type="primary"):
                if distance_km > 0:
                    with st.spinner("Calculating emissions..."):
                        source = f"{source_city}, {source_country}"
                        destination = f"{dest_city}, {dest_country}"
                        try:
                            co2_kg = calculate_co2(source_country, source_city, dest_country, dest_city, transport_mode, distance_km, weight_tons)
                            st.markdown(f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">Estimated CO₂ Emissions: {co2_kg} kg</p></div>', unsafe_allow_html=True)
                            save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons)
                        except ValueError as e:
                            st.error(str(e))
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif st.session_state.page == "Optimized Route Planning":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Optimized Route Planning</h2>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2 = st.columns([1, 1], gap="large")

            with col1:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Source</h3>', unsafe_allow_html=True)
                source_country = st.selectbox(
                    "Source Country",
                    sorted(LOCATIONS.keys()),
                    index=sorted(LOCATIONS.keys()).index(st.session_state.source_country) if st.session_state.source_country in LOCATIONS else 0,
                    key="route_source_country"
                )
                source_city = st.selectbox(
                    "Source City",
                    sorted(LOCATIONS[source_country].keys()),
                    index=sorted(LOCATIONS[source_country].keys()).index(st.session_state.source_city) if st.session_state.source_city in LOCATIONS[source_country] else 0,
                    key="route_source_city"
                )
                st.session_state.source_country = source_country
                st.session_state.source_city = source_city

                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700 mt-6">Destination</h3>', unsafe_allow_html=True)
                dest_country = st.selectbox(
                    "Destination Country",
                    sorted(LOCATIONS.keys()),
                    index=sorted(LOCATIONS.keys()).index(st.session_state.dest_country) if st.session_state.dest_country in LOCATIONS else 0,
                    key="route_dest_country"
                )
                dest_city = st.selectbox(
                    "Destination City",
                    sorted(LOCATIONS[dest_country].keys()),
                    index=sorted(LOCATIONS[dest_country].keys()).index(st.session_state.dest_city) if st.session_state.dest_city in LOCATIONS[dest_country] else 0,
                    key="route_dest_city"
                )
                st.session_state.dest_country = dest_country
                st.session_state.dest_city = dest_city

            with col2:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Details</h3>', unsafe_allow_html=True)
                weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1, key="route_weight")
                prioritize_green = st.checkbox("Prioritize Green Transport", value=False, key="route_green")
                try:
                    distance_km = calculate_distance(source_country, source_city, dest_country, dest_city)
                    st.markdown(f'<p class="text-gray-600">Estimated Distance: <span class="font-semibold">{distance_km} km</span></p>', unsafe_allow_html=True)
                except ValueError as e:
                    st.error(str(e))
                    distance_km = 0.0

            st.markdown('<div class="mt-6">', unsafe_allow_html=True)
            if st.button("Optimize Route", key="optimize_button", type="primary"):
                if distance_km > 0:
                    with st.spinner("Optimizing route..."):
                        try:
                            best_option, min_co2, best_breakdown, best_distances, current_co2 = optimize_route(
                                source_country, source_city, dest_country, dest_country, distance_km, weight_tons, prioritize_green
                            )
                            mode1, ratio1, mode2, ratio2 = best_option
                            dist1, dist2 = best_distances
                            co2_1, co2_2 = best_breakdown
                            st.markdown(
                                f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">Optimized CO₂ Emissions: {min_co2} kg (vs {current_co2} kg standard)</p></div>',
                                unsafe_allow_html=True
                            )
                            st.markdown(f'<p class="text-gray-600">Route: {mode1} ({dist1:.1f} km) + {mode2 if mode2 else "None"} ({dist2:.1f} km)</p>', unsafe_allow_html=True)
                        except ValueError as e:
                            st.error(str(e))
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred while rendering the page: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
