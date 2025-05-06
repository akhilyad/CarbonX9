import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import folium_static
import uuid
import math
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import streamlit.components.v1 as components

# Initialize SQLite database
def init_db():
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS suppliers 
                        (id TEXT PRIMARY KEY, supplier_name TEXT, country TEXT, city TEXT, 
                         material TEXT, green_score INTEGER, annual_capacity_tons INTEGER, 
                         sustainable_practices TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS emissions 
                        (id TEXT PRIMARY KEY, source TEXT, destination TEXT, 
                         transport_mode TEXT, distance_km REAL, co2_kg REAL, 
                         weight_tons REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS packaging 
                        (id TEXT PRIMARY KEY, material_type TEXT, weight_kg REAL, 
                         co2_kg REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS offsets 
                        (id TEXT PRIMARY KEY, project_type TEXT, co2_offset_tons REAL, 
                         cost_usd REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            sample_suppliers = [
                (str(uuid.uuid4()), 'UK Steel Co', 'United Kingdom', 'London', 'Steel', 85, 50000, 'Renewable energy'),
                (str(uuid.uuid4()), 'London Tech Supplies', 'United Kingdom', 'London', 'Electronics', 70, 20000, 'Recycling'),
                (str(uuid.uuid4()), 'British Textiles Ltd', 'United Kingdom', 'London', 'Textiles', 65, 30000, 'Sustainable sourcing'),
                (str(uuid.uuid4()), 'French Steelworks', 'France', 'Paris', 'Steel', 80, 45000, 'Energy-efficient manufacturing'),
                (str(uuid.uuid4()), 'Paris Electronics Hub', 'France', 'Paris', 'Electronics', 75, 25000, 'Carbon offsetting'),
                (str(uuid.uuid4()), 'ChemFrance', 'France', 'Paris', 'Chemicals', 60, 40000, 'Waste reduction'),
                (str(uuid.uuid4()), 'American Steel Corp', 'USA', 'New York', 'Steel', 75, 60000, 'Renewable energy'),
                (str(uuid.uuid4()), 'NY Tech Innovate', 'USA', 'New York', 'Electronics', 80, 30000, 'Sustainable packaging'),
                (str(uuid.uuid4()), 'US Textile Giants', 'USA', 'New York', 'Textiles', 70, 35000, 'Recycling'),
                (str(uuid.uuid4()), 'China Steel Group', 'China', 'Shanghai', 'Steel', 65, 80000, 'Energy-efficient manufacturing'),
                (str(uuid.uuid4()), 'Shanghai Electronics', 'China', 'Shanghai', 'Electronics', 60, 50000, 'Carbon offsetting'),
                (str(uuid.uuid4()), 'EastChem Co', 'China', 'Shanghai', 'Chemicals', 55, 60000, 'Waste reduction'),
                (str(uuid.uuid4()), 'Nippon Steel', 'Japan', 'Tokyo', 'Steel', 80, 55000, 'Renewable energy'),
                (str(uuid.uuid4()), 'Tokyo Tech Solutions', 'Japan', 'Tokyo', 'Electronics', 85, 40000, 'Sustainable packaging'),
                (str(uuid.uuid4()), 'Japan Textiles', 'Japan', 'Tokyo', 'Textiles', 70, 30000, 'Recycling'),
                (str(uuid.uuid4()), 'Aussie Steelworks', 'Australia', 'Sydney', 'Steel', 75, 40000, 'Sustainable sourcing'),
                (str(uuid.uuid4()), 'Sydney Chem Supplies', 'Australia', 'Sydney', 'Chemicals', 65, 35000, 'Energy-efficient manufacturing'),
                (str(uuid.uuid4()), 'Aus Textiles', 'Australia', 'Sydney', 'Textiles', 70, 25000, 'Carbon offsetting')
            ]
            c.executemany('INSERT OR IGNORE INTO suppliers VALUES (?, ?, ?, ?, ?, ?, ?, ?)', sample_suppliers)
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

# DEFRA-based emission factors (kg CO₂ per km per ton)
EMISSION_FACTORS = {
    'Truck': 0.096,       # HGV, diesel
    'Train': 0.028,       # Freight train
    'Ship': 0.016,        # Container ship
    'Plane': 0.602,       # Cargo plane
    'Electric Truck': 0.020,  # Electric vehicle, assuming grid emissions
    'Biofuel Truck': 0.050,   # Biofuel-powered truck
    'Hydrogen Truck': 0.010   # Hydrogen fuel cell truck
}

# Color mapping for transport modes
TRANSPORT_COLORS = {
    'Truck': 'red',
    'Train': 'blue',
    'Ship': 'green',
    'Plane': 'purple',
    'Electric Truck': 'cyan',
    'Biofuel Truck': 'orange',
    'Hydrogen Truck': 'pink'
}

# Country-city structure with coordinates (latitude, longitude)
LOCATIONS = {
    'United Kingdom': {'London': (51.5074, -0.1278)},
    'France': {'Paris': (48.8566, 2.3522)},
    'USA': {'New York': (40.7128, -74.0060)},
    'China': {'Shanghai': (31.2304, 121.4737)},
    'Japan': {'Tokyo': (35.6762, 139.6503)},
    'Australia': {'Sydney': (-33.8688, 151.2093)}
}

# Carbon pricing data (as of April 2025, based on EU ETS)
CARBON_PRICE_EUR_PER_TON = 65.89  # EU ETS price
EXCHANGE_RATES = {
    'EUR': 1.0,
    'USD': 1.06,  # Approximate
    'AUD': 1.62,  # Approximate
    'SAR': 3.98   # Approximate
}

# Packaging emission factors (kg CO₂ per kg of material)
PACKAGING_EMISSIONS = {
    'Plastic': 6.0,      # Virgin plastic
    'Cardboard': 0.9,    # Recycled cardboard
    'Biodegradable': 0.3,  # Compostable materials
    'Reusable': 0.1       # Reusable packaging
}

# Offset project costs (USD per ton of CO₂)
OFFSET_COSTS = {
    'Reforestation': 15.0,
    'Renewable Energy': 20.0,
    'Methane Capture': 18.0
}

# Packaging material costs (USD per kg, approximate)
PACKAGING_COSTS = {
    'Plastic': 1.5,
    'Cardboard': 0.8,
    'Biodegradable': 2.0,
    'Reusable': 3.0
}

def get_coordinates(country, city):
    return LOCATIONS.get(country, {}).get(city, (0, 0))

def calculate_distance(country1, city1, country2, city2):
    lat1, lon1 = get_coordinates(country1, city1)
    lat2, lon2 = get_coordinates(country2, city2)
    if lat1 == 0 and lon1 == 0 or lat2 == 0 and lon2 == 0:
        raise ValueError(f"Coordinates not found for {city1}, {country1} or {city2}, {country2}")
    R = 6371  # Earth's radius in km
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
                ('Ship', 0.8, 'Hydrogen Truck', 0.2) if prioritize_green else ('Ship', 0.8, 'Truck', 0.2),
                ('Plane', 0.5, 'Ship', 0.5),
                ('Ship', 0.7, 'Biofuel Truck', 0.3),
                ('Plane', 0.6, 'Electric Truck', 0.4) if prioritize_green else ('Plane', 0.6, 'Truck', 0.4)
            ])
        elif distance_medium:
            combinations.extend([
                ('Ship', 0.7, 'Train', 0.3),
                ('Plane', 0.4, 'Hydrogen Truck', 0.6) if prioritize_green else ('Plane', 0.4, 'Truck', 0.6),
                ('Ship', 0.6, 'Electric Truck', 0.4) if prioritize_green else ('Ship', 0.6, 'Truck', 0.4),
                ('Train', 0.5, 'Biofuel Truck', 0.5),
                ('Plane', 0.3, 'Train', 0.7)
            ])
        else:
            combinations.extend([
                ('Train', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Train', 0.8, 'Truck', 0.2),
                ('Ship', 0.5, 'Hydrogen Truck', 0.5) if prioritize_green else ('Ship', 0.5, 'Truck', 0.5),
                ('Train', 0.6, 'Biofuel Truck', 0.4),
                ('Plane', 0.3, 'Electric Truck', 0.7) if prioritize_green else ('Plane', 0.3, 'Truck', 0.7)
            ])
    else:
        if distance_short:
            combinations.extend([
                ('Train', 0.9, 'Electric Truck', 0.1) if prioritize_green else ('Train', 0.9, 'Truck', 0.1),
                ('Hydrogen Truck', 1.0, None, 0.0) if prioritize_green else ('Truck', 1.0, None, 0.0),
                ('Electric Truck', 1.0, None, 0.0) if prioritize_green else ('Train', 1.0, None, 0.0),
                ('Biofuel Truck', 1.0, None, 0.0)
            ])
        else:
            combinations.extend([
                ('Train', 0.7, 'Biofuel Truck', 0.3) if prioritize_green else ('Train', 0.7, 'Truck', 0.3),
                ('Truck', 0.6, 'Train', 0.4),
                ('Electric Truck', 0.5, 'Hydrogen Truck', 0.5) if prioritize_green else ('Truck', 0.5, 'Train', 0.5),
                ('Biofuel Truck', 0.4, 'Train', 0.6)
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
        st.error(f"Database error: {e}")
        raise

def save_packaging(material_type, weight_kg, co2_kg):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            packaging_id = str(uuid.uuid4())
            c.execute('INSERT INTO packaging (id, material_type, weight_kg, co2_kg, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (packaging_id, material_type, weight_kg, co2_kg))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def save_offset(project_type, co2_offset_tons, cost_usd):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            offset_id = str(uuid.uuid4())
            c.execute('INSERT INTO offsets (id, project_type, co2_offset_tons, cost_usd, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (offset_id, project_type, co2_offset_tons, cost_usd))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_emissions():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM emissions', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_packaging():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM packaging', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_offsets():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM offsets', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_suppliers(country=None, city=None, material=None, min_green_score=0):
    try:
        with sqlite3.connect('emissions.db') as conn:
            query = 'SELECT * FROM suppliers WHERE green_score >= ?'
            params = [min_green_score]
            conditions = []
            if country and country != "All":
                conditions.append('country = ?')
                params.append(country)
            if city and city != "All":
                conditions.append('city = ?')
                params.append(city)
            if material:
                conditions.append('LOWER(material) LIKE ?')
                params.append(f'%{material.lower()}%')
            if conditions:
                query += ' AND ' + ' AND '.join(conditions)
            df = pd.read_sql_query(query, conn, params=params)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def calculate_warehouse_savings(warehouse_size_m2, led_percentage, solar_percentage):
    traditional_energy_kwh = warehouse_size_m2 * 100
    led_savings_kwh = traditional_energy_kwh * led_percentage * 0.5
    solar_savings_kwh = traditional_energy_kwh * solar_percentage * 0.3
    total_savings_kwh = led_savings_kwh + solar_savings_kwh
    co2_savings_kg = total_savings_kwh * 0.5
    return round(co2_savings_kg, 2), round(total_savings_kwh, 2)

def calculate_load_optimization(weight_tons, vehicle_capacity_tons, avg_trip_distance_km=100):
    trips_without_optimization = math.ceil(weight_tons / (vehicle_capacity_tons * 0.90))
    optimized_trips = math.ceil(weight_tons / (vehicle_capacity_tons * 0.98))
    trips_saved = max(trips_without_optimization - optimized_trips, 0)
    co2_savings_kg = trips_saved * avg_trip_distance_km * EMISSION_FACTORS['Truck']
    return trips_saved, round(co2_savings_kg, 2)

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

    init_db()

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
    if 'warehouse_inputs' not in st.session_state:
        st.session_state.warehouse_inputs = {'warehouse_size_m2': 1000, 'led_percentage': 0.5, 'solar_percentage': 0.3}
    if 'packaging_inputs' not in st.session_state:
        st.session_state.packaging_inputs = {'material_type': 'Plastic', 'weight_kg': 1.0}
    if 'offset_inputs' not in st.session_state:
        st.session_state.offset_inputs = {'project_type': 'Reforestation', 'co2_offset_tons': 1.0}
    if 'load_inputs' not in st.session_state:
        st.session_state.load_inputs = {'weight_tons': 10.0, 'vehicle_capacity_tons': 20.0, 'avg_trip_distance_km': 100.0}
    if 'energy_inputs' not in st.session_state:
        st.session_state.energy_inputs = {'facility_size_m2': 1000, 'smart_system_usage': 0.5}

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

    # Sidebar navigation
    with st.sidebar:
        st.markdown('<div class="sidebar">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold mb-4 text-gray-800">Navigation</h2>', unsafe_allow_html=True)
        pages = [
            ("Calculate Emissions", "📊"),
            ("Route Visualizer", "🗺️"),
            ("Supplier Lookup", "🔍"),
            ("Reports", "📈"),
            ("Optimized Route Planning", "🚚"),
            ("Green Warehousing", "🏭"),
            ("Sustainable Packaging", "📦"),
            ("Carbon Offsetting", "🌱"),
            ("Efficient Load Management", "🚛"),
            ("Energy Conservation", "⚡️")
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
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Source</h3>', unsafe_allow_html=True)
                source_country = st.selectbox(
                    "Source Country", 
                    list(LOCATIONS.keys()), 
                    index=list(LOCATIONS.keys()).index(st.session_state.source_country),
                    key="calc_source_country"
                )
                source_city = st.selectbox(
                    "Source City", 
                    list(LOCATIONS[source_country].keys()), 
                    index=list(LOCATIONS[source_country].keys()).index(st.session_state.source_city) if st.session_state.source_city in LOCATIONS[source_country] else 0,
                    key="calc_source_city"
                )
                st.session_state.source_country = source_country
                st.session_state.source_city = source_city

                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Destination</h3>', unsafe_allow_html=True)
                dest_country = st.selectbox(
                    "Destination Country", 
                    list(LOCATIONS.keys()), 
                    index=list(LOCATIONS.keys()).index(st.session_state.dest_country),
                    key="calc_dest_country"
                )
                dest_city = st.selectbox(
                    "Destination City", 
                    list(LOCATIONS[dest_country].keys()), 
                    index=list(LOCATIONS[dest_country].keys()).index(st.session_state.dest_city) if st.session_state.dest_city in LOCATIONS[dest_country] else 0,
                    key="calc_dest_city"
                )
                st.session_state.dest_country = dest_country
                st.session_state.dest_city = dest_city

            with col2:
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

                            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Calculation Dashboard</h3>', unsafe_allow_html=True)
                            col3, col4 = st.columns(2)
                            with col3:
                                st.markdown(f'<div class="metric-card"><p>Total Distance</p><p class="font-semibold">{distance_km} km</p></div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="metric-card"><p>Total CO₂ Emissions</p><p class="font-semibold">{co2_kg} kg</p></div>', unsafe_allow_html=True)
                            with col4:
                                st.markdown(f'<div class="metric-card"><p>Emission Factor</p><p class="font-semibold">{EMISSION_FACTORS[transport_mode]} kg CO₂/km/ton</p></div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="metric-card"><p>Weight</p><p class="font-semibold">{weight_tons} tons</p></div>', unsafe_allow_html=True)

                            with st.expander("Calculation Details"):
                                st.markdown("**Distance Calculation**")
                                st.markdown("The distance is calculated using the **Haversine Formula** for great-circle distance.")
                                st.markdown(f"Coordinates: {source_city} ({get_coordinates(source_country, source_city)}), {dest_city} ({get_coordinates(dest_country, dest_city)})")
                                st.markdown("**CO₂ Emission Calculation**")
                                st.markdown("CO₂ = Distance (km) × Weight (tons) × Emission Factor")
                                st.markdown(f"Calculation: {distance_km} km × {weight_tons} tons × {EMISSION_FACTORS[transport_mode]} = {co2_kg} kg")
                        except ValueError as e:
                            st.error(str(e))
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif st.session_state.page == "Route Visualizer":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Emission Hotspot Visualizer</h2>', unsafe_allow_html=True)
            try:
                emissions = get_emissions()
                if not emissions.empty:
                    emissions['source_country'] = emissions['source'].apply(lambda x: x.split(', ')[1])
                    emissions['source_city'] = emissions['source'].apply(lambda x: x.split(', ')[0])
                    emissions['dest_country'] = emissions['destination'].apply(lambda x: x.split(', ')[1])
                    emissions['dest_city'] = emissions['destination'].apply(lambda x: x.split(', ')[0])

                    valid_coords = []
                    for _, row in emissions.iterrows():
                        src_coords = get_coordinates(row['source_country'], row['source_city'])
                        dst_coords = get_coordinates(row['dest_country'], row['dest_city'])
                        if src_coords != (0, 0):
                            valid_coords.append(src_coords)
                        if dst_coords != (0, 0):
                            valid_coords.append(dst_coords)

                    if valid_coords:
                        avg_lat = sum(coord[0] for coord in valid_coords) / len(valid_coords)
                        avg_lon = sum(coord[1] for coord in valid_coords) / len(valid_coords)
                    else:
                        avg_lat, avg_lon = 48.8566, 2.3522

                    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=2, tiles='OpenStreetMap')

                    for _, row in emissions.iterrows():
                        source_coords = get_coordinates(row['source_country'], row['source_city'])
                        dest_coords = get_coordinates(row['dest_country'], row['dest_city'])
                        if source_coords != (0, 0) and dest_coords != (0, 0):
                            color = 'red' if row['co2_kg'] > 1000 else 'orange' if row['co2_kg'] > 500 else 'green'
                            folium.PolyLine(
                                locations=[source_coords, dest_coords],
                                color=color,
                                weight=3,
                                popup=f"{row['source']} to {row['destination']}: {row['co2_kg']} kg"
                            ).add_to(m)
                            folium.Marker(
                                location=source_coords,
                                popup=f"{row['source']}: {row['co2_kg']} kg",
                                icon=folium.Icon(color=color)
                            ).add_to(m)
                            folium.Marker(
                                location=dest_coords,
                                popup=f"{row['destination']}: {row['co2_kg']} kg",
                                icon=folium.Icon(color=color)
                            ).add_to(m)

                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; padding: 10px; background-color: white; border: 2px solid black; border-radius: 5px;">
                        <p><strong>CO₂ Emission Legend</strong></p>
                        <p><span style="color: green;">■</span> Low (&lt;500 kg)</p>
                        <p><span style="color: orange;">■</span> Medium (500-1000 kg)</p>
                        <p><span style="color: red;">■</span> High (&gt;1000 kg)</p>
                    </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))

                    with st.spinner("Loading map..."):
                        folium_static(m, width=1200, height=600)

                    st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Analytics Dashboard</h3>', unsafe_allow_html=True)
                    routes = [f"Route {idx + 1}: {row['source']} to {row['destination']}" for idx, row in emissions.iterrows()]
                    selected_route = st.selectbox("Select Route to Analyze", routes)
                    route_idx = int(selected_route.split(":")[0].split(" ")[1]) - 1
                    row = emissions.iloc[route_idx]

                    source_country = row['source_country']
                    source_city = row['source_city']
                    dest_country = row['dest_country']
                    dest_city = row['dest_city']
                    distance_km = row['distance_km']
                    weight_tons = row['weight_tons']
                    current_co2 = row['co2_kg']
                    current_mode = row['transport_mode']

                    try:
                        best_option, min_co2, breakdown, distances, _ = optimize_route(source_country, source_city, dest_country, dest_city, distance_km, weight_tons, prioritize_green=True)
                        mode1, ratio1, mode2, ratio2 = best_option
                        co2_1, co2_2 = breakdown
                        dist1, dist2 = distances
                        savings = current_co2 - min_co2
                        savings_pct = (savings / current_co2 * 100) if current_co2 != 0 else 0

                        st.markdown('<h4 class="text-lg font-semibold mb-4 text-gray-700">Key Performance Indicators (KPIs)</h4>', unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.markdown(f'<div class="metric-card"><p>Total Distance</p><p class="font-semibold">{distance_km:.2f} km</p></div>', unsafe_allow_html=True)
                        with col2:
                            st.markdown(f'<div class="metric-card"><p>Current CO₂ Emissions</p><p class="font-semibold">{current_co2:.2f} kg</p></div>', unsafe_allow_html=True)
                        with col3:
                            st.markdown(f'<div class="metric-card"><p>Optimized CO₂ Emissions</p><p class="font-semibold">{min_co2:.2f} kg</p></div>', unsafe_allow_html=True)
                        with col4:
                            st.markdown(f'<div class="metric-card"><p>CO₂ Savings</p><p class="font-semibold">{savings:.2f} kg ({savings_pct:.1f}%)</p></div>', unsafe_allow_html=True)

                        tab1, tab2 = st.tabs(["Route Breakdown", "Comparison Chart"])

                        with tab1:
                            st.markdown("**Optimized Route Breakdown**")
                            if mode2:
                                st.markdown(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                                st.markdown(f"- **{mode2}**: {dist2:.2f} km, CO₂: {co2_2:.2f} kg")
                            else:
                                st.markdown(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")

                        with tab2:
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                x=[current_co2, min_co2],
                                y=['Current Route', 'Optimized Route'],
                                orientation='h',
                                name='CO₂ Emissions (kg)',
                                marker_color=['#FF4B4B', '#36A2EB']
                            ))
                            fig.add_trace(go.Bar(
                                x=[distance_km, dist1 if not mode2 else dist1 + dist2],
                                y=['Current Route', 'Optimized Route'],
                                orientation='h',
                                name='Distance (km)',
                                marker_color=['#FF9999', '#66B3FF']
                            ))
                            fig.update_layout(
                                title="Current vs Optimized Route Comparison",
                                barmode='group'
                            )
                            st.plotly_chart(fig, use_container_width=True, key=f"route_comparison_{time.time()}_{selected_route}")
                    except ValueError as e:
                        st.error(f"Error optimizing route: {e}")
                else:
                    st.info("No emission routes to display. Calculate some emissions first!")
            except Exception as e:
                st.error(f"Error loading emissions: {e}")

        elif st.session_state.page == "Supplier Lookup":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Supplier Lookup Dashboard</h2>', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                country = st.selectbox("Country", ["All"] + list(LOCATIONS.keys()))
            with col2:
                cities = ["All"] + list(LOCATIONS.get(country, {}).keys()) if country != "All" else ["All"]
                city = st.selectbox("City", cities)
            with col3:
                material = st.text_input("Material (e.g., Steel, Electronics)")
            with col4:
                min_green_score = st.slider("Minimum Green Score", 0, 100, 50)

            try:
                suppliers = get_suppliers(country if country != "All" else None, 
                                        city if city != "All" else None, 
                                        material or None, min_green_score)

                if not suppliers.empty:
                    st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Key Performance Indicators (KPIs)</h3>', unsafe_allow_html=True)
                    col4, col5, col6, col7 = st.columns(4)
                    with col4:
                        st.markdown(f'<div class="metric-card"><p>Total Suppliers</p><p class="font-semibold">{len(suppliers)}</p></div>', unsafe_allow_html=True)
                    with col5:
                        st.markdown(f'<div class="metric-card"><p>Average Green Score</p><p class="font-semibold">{suppliers["green_score"].mean():.1f}</p></div>', unsafe_allow_html=True)
                    with col6:
                        st.markdown(f'<div class="metric-card"><p>Total Capacity</p><p class="font-semibold">{suppliers["annual_capacity_tons"].sum():,} tons</p></div>', unsafe_allow_html=True)

                    potential_savings = 0
                    if st.session_state.source_country and st.session_state.dest_country:
                        source_country = st.session_state.source_country
                        dest_country = st.session_state.dest_country
                        weight_tons = st.session_state.weight_tons
                        try:
                            distance_km = calculate_distance(source_country, list(LOCATIONS[source_country].keys())[0],
                                                            dest_country, list(LOCATIONS[dest_country].keys())[0])
                            current_co2 = distance_km * weight_tons * EMISSION_FACTORS['Truck']
                            local_suppliers = suppliers[suppliers['country'] == dest_country]
                            if not local_suppliers.empty:
                                potential_savings = current_co2
                                st.markdown(
                                    f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">🌍 Local Sourcing Opportunity: Source from {dest_country} to save {potential_savings:.2f} kg CO₂.</p></div>',
                                    unsafe_allow_html=True
                                )
                            else:
                                st.info(f"No suppliers found in {dest_country}.")
                        except ValueError as e:
                            st.error(f"Error calculating savings: {e}")
                    with col7:
                        st.markdown(f'<div class="metric-card"><p>Potential CO₂ Savings</p><p class="font-semibold">{potential_savings:.2f} kg</p></div>', unsafe_allow_html=True)

                    st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Supplier Insights 📊</h3>', unsafe_allow_html=True)
                    tab1, tab2, tab3 = st.tabs(["Supplier Distribution", "Material Availability", "Supplier Details"])

                    with tab1:
                        fig = px.bar(suppliers.groupby('country').size().reset_index(name='Count'),
                                    x='country', y='Count', title="Suppliers by Country")
                        st.plotly_chart(fig, use_container_width=True, key=f"supplier_distribution_{time.time()}_{country}_{city}_{material}_{min_green_score}")

                    with tab2:
                        fig = px.bar(suppliers.groupby('material')['annual_capacity_tons'].sum().reset_index(),
                                    x='material', y='annual_capacity_tons', title="Material Capacity")
                        st.plotly_chart(fig, use_container_width=True, key=f"material_availability_{time.time()}_{country}_{city}_{material}_{min_green_score}")

                    with tab3:
                        st.dataframe(suppliers[['supplier_name', 'country', 'city', 'material', 'green_score', 'sustainable_practices']])
                else:
                    st.info("No suppliers found for the given criteria.")
            except Exception as e:
                st.error(f"Error loading suppliers: {e}")

        elif st.session_state.page == "Reports":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Emission Reports</h2>', unsafe_allow_html=True)
            try:
                emissions = get_emissions()
                if not emissions.empty:
                    total_co2 = emissions['co2_kg'].sum()
                    avg_co2 = emissions['co2_kg'].mean()
                    total_shipments = len(emissions)
                    total_savings = 0
                    route_data = []
                    for _, row in emissions.iterrows():
                        source_country = row['source'].split(', ')[1]
                        source_city = row['source'].split(', ')[0]
                        dest_country = row['destination'].split(', ')[1]
                        dest_city = row['destination'].split(', ')[0]
                        distance_km = row['distance_km']
                        weight_tons = row['weight_tons']
                        current_co2 = row['co2_kg']
                        current_mode = row['transport_mode']

                        try:
                            best_option, min_co2, breakdown, distances, _ = optimize_route(source_country, source_city, dest_country, dest_city, distance_km, weight_tons, prioritize_green=True)
                            mode1, ratio1, mode2, ratio2 = best_option
                            co2_1, co2_2 = breakdown
                            dist1, dist2 = distances
                            savings = current_co2 - min_co2
                            savings_pct = (savings / current_co2 * 100) if current_co2 != 0 else 0
                            total_savings += savings

                            route_data.append({
                                'Route': f"{source_city}, {source_country} to {dest_city}, {dest_country}",
                                'Old Mode': current_mode,
                                'Old Distance': distance_km,
                                'Old CO₂': current_co2,
                                'New Modes': f"{mode1} + {mode2 if mode2 else 'None'}",
                                'New Distances': f"{dist1:.2f} km ({mode1}) + {dist2:.2f} km ({mode2 if mode2 else 'N/A'})",
                                'New CO₂': min_co2,
                                'Savings': savings
                            })
                        except ValueError as e:
                            st.warning(f"Skipping route optimization for {source_city} to {dest_city}: {e}")

                    tab1, tab2, tab3, tab4 = st.tabs(["Summary", "CO₂ Insights", "Route Optimization", "Detailed Data"])

                    with tab1:
                        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Summary Statistics</h3>', unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.markdown(f'<div class="metric-card"><p>Total CO₂ Emissions</p><p class="font-semibold">{total_co2:.2f} kg</p></div>', unsafe_allow_html=True)
                        with col2:
                            st.markdown(f'<div class="metric-card"><p>Total Shipments</p><p class="font-semibold">{total_shipments}</p></div>', unsafe_allow_html=True)
                        with col3:
                            st.markdown(f'<div class="metric-card"><p>Average CO₂ per Shipment</p><p class="font-semibold">{avg_co2:.2f} kg</p></div>', unsafe_allow_html=True)
                        with col4:
                            st.markdown(f'<div class="metric-card"><p>Total CO₂ Savings</p><p class="font-semibold">{total_savings:.2f} kg</p></div>', unsafe_allow_html=True)

                        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Emission Breakdown by Transport Mode</h3>', unsafe_allow_html=True)
                        mode_summary = emissions.groupby('transport_mode')['co2_kg'].sum().reset_index()
                        fig = px.pie(mode_summary, values='co2_kg', names='transport_mode', title="CO₂ by Mode")
                        st.plotly_chart(fig, use_container_width=True, key=f"emission_breakdown_{time.time()}")

                    with tab2:
                        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">CO₂ Impact Insights</h3>', unsafe_allow_html=True)
                        smartphone_charges = total_co2 * 1000 / 0.008
                        ev_distance = total_co2 / 0.2
                        st.markdown(f"**Energy Equivalent**: The {total_co2:.2f} kg of CO₂ could:")
                        st.markdown(f"- Charge {int(smartphone_charges):,} smartphones.")
                        st.markdown(f"- Power an EV for {ev_distance:.0f} km.")
                        st.markdown(f"**Environmental Fact**: Offset by planting {int(total_co2 * 0.05):,} trees!")

                    with tab3:
                        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Optimization Summary</h3>', unsafe_allow_html=True)
                        currency = st.selectbox("Currency", ['EUR', 'USD', 'AUD', 'SAR'])
                        carbon_price_per_kg = (CARBON_PRICE_EUR_PER_TON / 1000) * EXCHANGE_RATES[currency]
                        total_cost_savings = total_savings * carbon_price_per_kg

                        st.markdown(f"**Carbon Price**: {CARBON_PRICE_EUR_PER_TON:.2f} EUR/tCO₂")
                        st.markdown(f"**Converted**: {carbon_price_per_kg:.4f} {currency}/kg CO₂")
                        st.markdown(f"**Total Savings**: {total_cost_savings:.2f} {currency}")

                        df_routes = pd.DataFrame(route_data)
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=df_routes['Old CO₂'], y=df_routes['Route'], orientation='h', name='Current CO₂', marker_color='#FF4B4B'))
                        fig.add_trace(go.Bar(x=df_routes['New CO₂'], y=df_routes['Route'], orientation='h', name='Optimized CO₂', marker_color='#36A2EB'))
                        fig.update_layout(title="Current vs Optimized Route CO₂", barmode='group')
                        st.plotly_chart(fig, use_container_width=True, key=f"route_optimization_{time.time()}_{currency}")

                        st.dataframe(df_routes[['Route', 'Old Mode', 'Old Distance', 'Old CO₂', 'New Modes', 'New Distances', 'New CO₂', 'Savings']])

                    with tab4:
                        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Detailed Data</h3>', unsafe_allow_html=True)
                        st.dataframe(emissions)
                        csv = emissions.to_csv(index=False)
                        st.download_button(label="Download as CSV", data=csv, file_name="emissions_report.csv", mime="text/csv")
                else:
                    st.info("No emission data available.")
            except Exception as e:
                st.error(f"Error loading emissions: {e}")

        elif st.session_state.page == "Optimized Route Planning":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Optimized Route Planning</h2>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Details</h3>', unsafe_allow_html=True)
                source_country = st.selectbox(
                    "Source Country",
                    list(LOCATIONS.keys()),
                    index=list(LOCATIONS.keys()).index(st.session_state.source_country),
                    key="opt_source_country"
                )
                source_city = st.selectbox(
                    "Source City",
                    list(LOCATIONS[source_country].keys()),
                    index=list(LOCATIONS[source_country].keys()).index(st.session_state.source_city) if st.session_state.source_city in LOCATIONS[source_country] else 0,
                    key="opt_source_city"
                )
                st.session_state.source_country = source_country
                st.session_state.source_city = source_city

                dest_country = st.selectbox(
                    "Destination Country",
                    list(LOCATIONS.keys()),
                    index=list(LOCATIONS.keys()).index(st.session_state.dest_country),
                    key="opt_dest_country"
                )
                dest_city = st.selectbox(
                    "Destination City",
                    list(LOCATIONS[dest_country].keys()),
                    index=list(LOCATIONS[dest_country].keys()).index(st.session_state.dest_city) if st.session_state.dest_city in LOCATIONS[dest_country] else 0,
                    key="opt_dest_city"
                )
                st.session_state.dest_country = dest_country
                st.session_state.dest_city = dest_city

            with col2:
                weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1, key="opt_weight")
                prioritize_green = st.checkbox("Prioritize Green Vehicles", value=True, key="opt_green")
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
                            best_option, min_co2, breakdown, distances, current_co2 = optimize_route(
                                source_country, source_city, dest_country, dest_city, distance_km, weight_tons, prioritize_green
                            )
                            mode1, ratio1, mode2, ratio2 = best_option
                            co2_1, co2_2 = breakdown
                            dist1, dist2 = distances
                            savings = current_co2 - min_co2
                            savings_pct = (savings / current_co2 * 100) if current_co2 > 0 else 0
                            cost_savings = savings * (CARBON_PRICE_EUR_PER_TON / 1000) * EXCHANGE_RATES['USD']
                            trees_equivalent = int(savings * 0.05)

                            st.markdown(f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">Optimized CO₂ Emissions: {min_co2:.2f} kg (Savings: {savings:.2f} kg, {savings_pct:.1f}%)</p></div>', unsafe_allow_html=True)

                            # Route Map
                            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Map</h3>', unsafe_allow_html=True)
                            source_coords = get_coordinates(source_country, source_city)
                            dest_coords = get_coordinates(dest_country, dest_city)
                            if source_coords != (0, 0) and dest_coords != (0, 0):
                                avg_lat = (source_coords[0] + dest_coords[0]) / 2
                                avg_lon = (source_coords[1] + dest_coords[1]) / 2
                                m = folium.Map(location=[avg_lat, avg_lon], zoom_start=4, tiles='OpenStreetMap')

                                # Intermediate point for multi-mode routes
                                if mode2:
                                    # Simple interpolation for intermediate point (e.g., port for Ship-to-Train)
                                    inter_lat = source_coords[0] + (dest_coords[0] - source_coords[0]) * ratio1
                                    inter_lon = source_coords[1] + (dest_coords[1] - source_coords[1]) * ratio1
                                    inter_coords = (inter_lat, inter_lon)

                                    # Segment 1: Source to Intermediate
                                    folium.PolyLine(
                                        locations=[source_coords, inter_coords],
                                        color=TRANSPORT_COLORS[mode1],
                                        weight=4,
                                        popup=f"{mode1}: {dist1:.2f} km, {co2_1:.2f} kg CO₂"
                                    ).add_to(m)
                                    folium.Marker(
                                        location=source_coords,
                                        popup=f"{source_city} (Start): {mode1}",
                                        icon=folium.Icon(color=TRANSPORT_COLORS[mode1])
                                    ).add_to(m)
                                    folium.Marker(
                                        location=inter_coords,
                                        popup=f"Transfer Point: {mode1} to {mode2}",
                                        icon=folium.Icon(color='gray')
                                    ).add_to(m)

                                    # Segment 2: Intermediate to Destination
                                    folium.PolyLine(
                                        locations=[inter_coords, dest_coords],
                                        color=TRANSPORT_COLORS[mode2],
                                        weight=4,
                                        popup=f"{mode2}: {dist2:.2f} km, {co2_2:.2f} kg CO₂"
                                    ).add_to(m)
                                    folium.Marker(
                                        location=dest_coords,
                                        popup=f"{dest_city} (End): {mode2}",
                                        icon=folium.Icon(color=TRANSPORT_COLORS[mode2])
                                    ).add_to(m)
                                else:
                                    # Single mode route
                                    folium.PolyLine(
                                        locations=[source_coords, dest_coords],
                                        color=TRANSPORT_COLORS[mode1],
                                        weight=4,
                                        popup=f"{mode1}: {dist1:.2f} km, {co2_1:.2f} kg CO₂"
                                    ).add_to(m)
                                    folium.Marker(
                                        location=source_coords,
                                        popup=f"{source_city} (Start): {mode1}",
                                        icon=folium.Icon(color=TRANSPORT_COLORS[mode1])
                                    ).add_to(m)
                                    folium.Marker(
                                        location=dest_coords,
                                        popup=f"{dest_city} (End): {mode1}",
                                        icon=folium.Icon(color=TRANSPORT_COLORS[mode1])
                                    ).add_to(m)

                                # Legend
                                legend_html = '''
                                <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; padding: 10px; background-color: white; border: 2px solid black; border-radius: 5px;">
                                    <p><strong>Transport Mode Legend</strong></p>
                                    <p><span style="color: red;">■</span> Truck</p>
                                    <p><span style="color: blue;">■</span> Train</p>
                                    <p><span style="color: green;">■</span> Ship</p>
                                    <p><span style="color: purple;">■</span> Plane</p>
                                    <p><span style="color: cyan;">■</span> Electric Truck</p>
                                    <p><span style="color: orange;">■</span> Biofuel Truck</p>
                                    <p><span style="color: pink;">■</span> Hydrogen Truck</p>
                                    <p><span style="color: gray;">■</span> Transfer Point</p>
                                    <p><strong>CO₂ Emission</strong></p>
                                    <p>Low: &lt;500 kg</p>
                                    <p>Medium: 500-1000 kg</p>
                                    <p>High: &gt;1000 kg</p>
                                </div>
                                '''
                                m.get_root().html.add_child(folium.Element(legend_html))

                                with st.spinner("Loading map..."):
                                    folium_static(m, width=1200, height=600)
                            else:
                                st.error("Cannot display map: Invalid coordinates.")

                            # KPIs
                            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Key Performance Indicators (KPIs)</h3>', unsafe_allow_html=True)
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.markdown(f'<div class="metric-card"><p>CO₂ Savings</p><p class="font-semibold">{savings:.2f} kg</p></div>', unsafe_allow_html=True)
                            with col2:
                                st.markdown(f'<div class="metric-card"><p>Cost Savings</p><p class="font-semibold">${cost_savings:.2f}</p></div>', unsafe_allow_html=True)
                            with col3:
                                st.markdown(f'<div class="metric-card"><p>Trees Equivalent</p><p class="font-semibold">{trees_equivalent}</p></div>', unsafe_allow_html=True)
                            with col4:
                                st.markdown(f'<div class="metric-card"><p>Route Efficiency</p><p class="font-semibold">{savings_pct:.1f}%</p></div>', unsafe_allow_html=True)

                            # Route Details Table
                            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Details</h3>', unsafe_allow_html=True)
                            route_details = [
                                {
                                    'Segment': 'Segment 1',
                                    'Mode': mode1,
                                    'Distance (km)': dist1,
                                    'CO₂ (kg)': co2_1
                                }
                            ]
                            if mode2:
                                route_details.append({
                                    'Segment': 'Segment 2',
                                    'Mode': mode2,
                                    'Distance (km)': dist2,
                                    'CO₂ (kg)': co2_2
                                })
                            st.dataframe(pd.DataFrame(route_details))

                            # Dashboard
                            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Route Optimization Dashboard</h3>', unsafe_allow_html=True)
                            tab1, tab2, tab3 = st.tabs(["Route Breakdown", "CO₂ Comparison", "Mode Contribution"])

                            with tab1:
                                st.markdown("**Optimized Route Breakdown**")
                                if mode2:
                                    st.markdown(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                                    st.markdown(f"- **{mode2}**: {dist2:.2f} km, CO₂: {co2_2:.2f} kg")
                                else:
                                    st.markdown(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")

                            with tab2:
                                fig = go.Figure()
                                fig.add_trace(go.Bar(
                                    x=[current_co2, min_co2],
                                    y=['Current Route', 'Optimized Route'],
                                    name='CO₂ Emissions (kg)',
                                    marker_color=['#FF4B4B', '#36A2EB']
                                ))
                                fig.add_trace(go.Bar(
                                    x=[distance_km, dist1 + dist2],
                                    y=['Current Route', 'Optimized Route'],
                                    name='Distance (km)',
                                    marker_color=['#FF9999', '#66B3FF']
                                ))
                                fig.update_layout(title="Current vs Optimized Route", barmode='group')
                                st.plotly_chart(fig, use_container_width=True, key=f"opt_co2_comparison_{time.time()}_{source_city}_{dest_city}_{weight_tons}_{prioritize_green}")

                            with tab3:
                                labels = [mode1]
                                values = [co2_1]
                                if mode2 and co2_2 > 0:
                                    labels.append(mode2)
                                    values.append(co2_2)
                                if values:
                                    fig = go.Figure()
                                    fig.add_trace(go.Pie(
                                        labels=labels,
                                        values=values,
                                        title="CO₂ Contribution by Mode"
                                    ))
                                    st.plotly_chart(fig, use_container_width=True, key=f"opt_mode_contribution_{time.time()}_{source_city}_{dest_city}_{weight_tons}_{prioritize_green}")
                                else:
                                    st.info("No CO₂ contributions to display.")

                            with st.expander("Efficiency Gauge"):
                                fig = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=savings_pct,
                                    title={'text': "Route Efficiency (%)"},
                                    gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#36A2EB"}}
                                ))
                                st.plotly_chart(fig, use_container_width=True, key=f"opt_efficiency_gauge_{time.time()}_{source_city}_{dest_city}_{weight_tons}_{prioritize_green}")

                        except ValueError as e:
                            st.error(f"Error optimizing route: {e}")
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        elif st.session_state.page == "Green Warehousing":
            st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Green Warehousing</h2>', unsafe_allow_html=True)
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2 = st.columns(2)

            with col1:
                warehouse_size_m2 = st.number_input("Warehouse Size (m²)", min_value=100, max_value=100000, value=st.session_state.warehouse_inputs['warehouse_size_m2'], key="wh_size")
                led_percentage = st.slider("LED Lighting Usage (%)", 0, 100, int(st.session_state.warehouse_inputs['led_percentage'] * 100), key="wh_led") / 100
                solar_percentage = st.slider("Solar Panel Usage (%)", 0, 100, int(st.session_state.warehouse_inputs['solar_percentage'] * 100), key="wh_solar") / 100

                st.session_state.warehouse_inputs = {
                    "warehouse_size_m2": warehouse_size_m2,
                    "led_percentage": led_percentage,
                    "solar_percentage": solar_percentage
                }

            with col2:
                co2_savings_kg, energy_savings_kwh = calculate_warehouse_savings(warehouse_size_m2, led_percentage, solar_percentage)
                cost_savings = energy_savings_kwh * 0.15
                car_miles_equivalent = co2_savings_kg / 0.4 if co2_savings_kg > 0 else 0

                if led_percentage == 0 and solar_percentage == 0:
                    st.warning("No LED or solar usage selected. Increase usage to calculate savings.")

                st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Key Performance Indicators (KPIs)</h3>', unsafe_allow_html=True)
                col3, col4, col5, col6 = st.columns(4)
                with col3:
                    st.markdown(f'<div class="metric-card"><p>CO₂ Savings</p><p class="font-semibold">{co2_savings_kg:.2f} kg/year</p></div>', unsafe_allow_html=True)
                with col4:
                    st.markdown(f'<div class="metric-card"><p>Energy Savings</p><p class="font-semibold">{energy_savings_kwh:.2f} kWh</p></div>', unsafe_allow_html=True)
                with col5:
                    st.markdown(f'<div class="metric-card"><p>Cost Savings</p><p class="font-semibold">${cost_savings:.2f}</p></div>', unsafe_allow_html=True)
                with col6:
                    st.markdown(f'<div class="metric-card"><p>Car Miles Equivalent</p><p class="font-semibold">{int(car_miles_equivalent)} miles</p></div>', unsafe_allow_html=True)

                st.markdown("**Assumptions**:")
                st.markdown("- Traditional warehouse: 100 kWh/m²/year (average for medium-sized warehouses).")
                st.markdown("- LED saves 50% energy, solar saves 30%.")
                st.markdown("- 0.5 kg CO₂ per kWh (grid average), $0.15/kWh, 0.4 kg CO₂/mile (passenger car).")

            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Green Warehousing Dashboard</h3>', unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["Savings Breakdown", "Trend Analysis"])

            with tab1:
                if co2_savings_kg > 0 or energy_savings_kwh > 0:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[co2_savings_kg * led_percentage / (led_percentage + solar_percentage or 1), co2_savings_kg * solar_percentage / (led_percentage + solar_percentage or 1)],
                        y=['LED Lighting', 'Solar Panels'],
                        name="CO₂ Savings (kg)"
                    ))
                    fig.add_trace(go.Bar(
                        x=[energy_savings_kwh * led_percentage / (led_percentage + solar_percentage or 1), energy_savings_kwh * solar_percentage / (led_percentage + solar_percentage or 1)],
                        y=['LED Lighting', 'Solar Panels'],
                        name="Energy Savings (kWh)"
                    ))
                    fig.update_layout(title="Savings by Technology", barmode='stack')
                    st.plotly_chart(fig, use_container_width=True, key=f"warehouse_savings_breakdown_{time.time()}_{warehouse_size_m2}_{led_percentage}_{solar_percentage}")
                else:
                    st.info("No savings to display. Adjust LED or solar usage.")

            with tab2:
                sizes = [max(100, warehouse_size_m2 * i / 5) for i in range(1, 6)]
                co2_trend = [calculate_warehouse_savings(size, led_percentage, solar_percentage)[0] for size in sizes]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=sizes, y=co2_trend, mode='lines+markers', name='CO₂ Savings (kg)'))
                fig.update_layout(title="CO₂ Savings vs Warehouse Size", xaxis_title="Size (m²)", yaxis_title="CO₂ Savings (kg)")
                st.plotly_chart(fig, use_container_width=True, key=f"warehouse_trend_analysis_{time.time()}_{warehouse_size_m2}_{led_percentage}_{solar_percentage}")

            st.markdown('</div>', unsafe_allow_html=True)

       elif st.session_state.page == "Sustainable Packaging"
    st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Sustainable Packaging</h2>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        material_type = st.selectbox("Packaging Material", list(PACKAGING_EMISSIONS.keys()), index=list(PACKAGING_EMISSIONS.keys()).index(st.session_state.packaging_inputs['material_type']), key="pkg_material")
        weight_kg = st.number_input("Packaging Weight (kg)", min_value=0.1, max_value=10000.0, value=st.session_state.packaging_inputs['weight_kg'], key="pkg_weight")

        st.session_state.packaging_inputs = {
            "material_type": material_type,
            "weight_kg": weight_kg
        }

    with col2:
        co2_kg = weight_kg * PACKAGING_EMISSIONS[material_type]
        potential_savings = co2_kg - weight_kg * PACKAGING_EMISSIONS['Biodegradable'] if material_type not in ['Biodegradable', 'Reusable'] else 0
        cost_impact = weight_kg * (PACKAGING_COSTS[material_type] - PACKAGING_COSTS['Biodegradable'])
        plastic_bottles = co2_kg / 0.12 if material_type == 'Plastic' else 0

        st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Key Performance Indicators (KPIs)</h3>', unsafe_allow_html=True)
        col3, col4, col5, col6 = st.columns(4)
        with col3:
            st.markdown(f'<div class="metric-card"><p>CO₂ Emissions</p><p class="font-semibold">{co2_kg:.2f} kg</p></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="metric-card"><p>Potential Savings</p><p class="font-semibold">{potential_savings:.2f} kg</p></div>', unsafe_allow_html=True)
        with col5:
            st.markdown(f'<div class="metric-card"><p>Cost Impact</p><p class="font-semibold">${cost_impact:.2f}</p></div>', unsafe_allow_html=True)
        with col6:
            st.markdown(f'<div class="metric-card"><p>Plastic Bottles</p><p class="font-semibold">{int(plastic_bottles)}</p></div>', unsafe_allow_html=True)

        if material_type not in ['Biodegradable', 'Reusable']:
            st.markdown(f'<div class="bg-blue-100 p-4 rounded-lg"><p class="text-lg font-semibold text-blue-800">Switch to Biodegradable to save {potential_savings:.2f} kg CO₂.</p></div>', unsafe_allow_html=True)

        if st.button("Save Packaging Data", key="save_pkg_button", type="primary"):
            save_packaging(material_type, weight_kg, co2_kg)
            st.markdown(f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">Packaging data saved!</p></div>', unsafe_allow_html=True)

    st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Sustainable Packaging Dashboard</h3>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Material Comparison", "Historical Trends"])

    with tab1:
        materials = list(PACKAGING_EMISSIONS.keys())
        emissions = [weight_kg * PACKAGING_EMISSIONS[m] for m in materials]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=materials, y=emissions, name="CO₂ Emissions (kg)"))
        fig.update_layout(title="CO₂ Emissions by Material")
        st.plotly_chart(fig, use_container_width=True, key=f"packaging_material_comparison_{time.time()}_{material_type}_{weight_kg}")

    with tab2:
        try:
            packaging = get_packaging()
            if not packaging.empty:
                packaging['timestamp'] = pd.to_datetime(packaging['timestamp'], errors='coerce')
                packaging['year_month'] = packaging['timestamp'].dt.to_period('M').astype(str)
                trend_data = packaging.groupby(['year_month', 'material_type'])['co2_kg'].sum().unstack().fillna(0)
                fig = go.Figure()
                for material in trend_data.columns:
                    fig.add_trace(go.Scatter(
                        x=trend_data.index,
                        y=trend_data[material],
                        mode='lines+markers',
                        name=material
                    ))
                fig.update_layout(
                    title="CO₂ Emissions by Packaging Material Over Time",
                    xaxis_title="Month",
                    yaxis_title="CO₂ Emissions (kg)"
                )
                st.plotly_chart(fig, use_container_width=True, key=f"packaging_trend_{time.time()}_{material_type}_{weight_kg}")
            else:
                st.info("No packaging data available for historical trends.")
        except Exception as e:
            st.error(f"Error loading packaging trends: {e}")

st.markdown('</div>', unsafe_allow_html=True)
