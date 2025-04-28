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

# Initialize SQLite database
def init_db():
    """
    Initialize the SQLite database with suppliers, emissions, packaging, and offsets tables.
    Inserts sample supplier data if not already present.
    """
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            # Create suppliers table with sustainable_practices column
            c.execute('''CREATE TABLE IF NOT EXISTS suppliers 
                        (id TEXT PRIMARY KEY, supplier_name TEXT, country TEXT, city TEXT, 
                         material TEXT, green_score INTEGER, annual_capacity_tons INTEGER, 
                         sustainable_practices TEXT)''')
            # Create emissions table
            c.execute('''CREATE TABLE IF NOT EXISTS emissions 
                        (id TEXT PRIMARY KEY, source TEXT, destination TEXT, 
                         transport_mode TEXT, distance_km REAL, co2_kg REAL, 
                         weight_tons REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            # Create packaging table
            c.execute('''CREATE TABLE IF NOT EXISTS packaging 
                        (id TEXT PRIMARY KEY, material_type TEXT, weight_kg REAL, 
                         co2_kg REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            # Create offsets table
            c.execute('''CREATE TABLE IF NOT EXISTS offsets 
                        (id TEXT PRIMARY KEY, project_type TEXT, co2_offset_tons REAL, 
                         cost_usd REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            # Insert expanded supplier data with sustainable practices
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
    """Get coordinates for a given country and city."""
    return LOCATIONS.get(country, {}).get(city, (0, 0))

def calculate_distance(country1, city1, country2, city2):
    """Calculate great-circle distance using Haversine formula."""
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
    """Calculate CO₂ emissions for a shipment."""
    emission_factor = EMISSION_FACTORS.get(transport_mode)
    if emission_factor is None:
        raise ValueError(f"Invalid transport mode: {transport_mode}")
    co2_kg = distance_km * weight_tons * emission_factor
    return round(co2_kg, 2)

def optimize_route(country1, city1, country2, city2, distance_km, weight_tons, prioritize_green=False):
    """
    Optimize transport route to minimize CO₂ emissions, with optional green vehicle preference.
    Returns: (best_option, min_co2, breakdown, distances, current_co2)
    """
    intercontinental = country1 != country2
    distance_short = distance_km < 1000
    distance_medium = 1000 <= distance_km < 5000
    distance_long = distance_km >= 5000

    # Calculate current CO₂ using default mode (Truck)
    current_co2 = distance_km * weight_tons * EMISSION_FACTORS['Truck']

    combinations = []
    if intercontinental:
        if distance_long:
            combinations.extend([
                ('Ship', 0.9, 'Train', 0.1),
                ('Ship', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Ship', 0.8, 'Truck', 0.2),
                ('Plane', 0.5, 'Ship', 0.5)
            ])
        elif distance_medium:
            combinations.extend([
                ('Ship', 0.7, 'Train', 0.3),
                ('Plane', 0.4, 'Hydrogen Truck', 0.6) if prioritize_green else ('Plane', 0.4, 'Truck', 0.6),
                ('Ship', 0.6, 'Plane', 0.4)
            ])
        else:
            combinations.extend([
                ('Train', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Train', 0.8, 'Truck', 0.2),
                ('Ship', 0.5, 'Truck', 0.5),
                ('Plane', 0.3, 'Truck', 0.7)
            ])
    else:
        if distance_short:
            combinations.extend([
                ('Train', 0.9, 'Electric Truck', 0.1) if prioritize_green else ('Train', 0.9, 'Truck', 0.1),
                ('Electric Truck', 1.0, None, 0.0) if prioritize_green else ('Truck', 1.0, None, 0.0),
                ('Train', 1.0, None, 0.0)
            ])
        else:
            combinations.extend([
                ('Train', 0.7, 'Biofuel Truck', 0.3) if prioritize_green else ('Train', 0.7, 'Truck', 0.3),
                ('Truck', 0.6, 'Train', 0.4),
                ('Plane', 0.3, 'Truck', 0.7)
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
    """Save emission data to the SQLite database."""
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
    """Save packaging emission data to the SQLite database."""
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
    """Save carbon offset data to the SQLite database."""
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
    """Retrieve all emission records from the database."""
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM emissions', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_packaging():
    """Retrieve all packaging emission records from the database."""
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM packaging', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_offsets():
    """Retrieve all carbon offset records from the database."""
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM offsets', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_suppliers(country=None, city=None, material=None, min_green_score=0):
    """Retrieve suppliers based on filters, prioritizing green suppliers."""
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
    """Calculate CO₂ and energy savings from green warehousing technologies."""
    traditional_energy_kwh = warehouse_size_m2 * 100  # 100 kWh/m²/year
    led_savings_kwh = traditional_energy_kwh * led_percentage * 0.5  # 50% savings
    solar_savings_kwh = traditional_energy_kwh * solar_percentage * 0.3  # 30% savings
    total_savings_kwh = led_savings_kwh + solar_savings_kwh
    co2_savings_kg = total_savings_kwh * 0.5  # 0.5 kg CO₂ per kWh
    return round(co2_savings_kg, 2), round(total_savings_kwh, 2)

def calculate_load_optimization(weight_tons, vehicle_capacity_tons, avg_trip_distance_km=100):
    """Calculate CO₂ savings from efficient load management."""
    trips_without_optimization = math.ceil(weight_tons / (vehicle_capacity_tons * 0.90))  # 90% capacity
    optimized_trips = math.ceil(weight_tons / (vehicle_capacity_tons * 0.98))  # 98% capacity
    trips_saved = max(trips_without_optimization - optimized_trips, 0)  # Ensure non-negative
    co2_savings_kg = trips_saved * avg_trip_distance_km * EMISSION_FACTORS['Truck']
    return trips_saved, round(co2_savings_kg, 2)

def main():
    st.set_page_config(page_title="CO₂ Emission Calculator", layout="wide")
    
    # Apply custom CSS for button and sidebar styling
    st.markdown("""
        <style>
        .stButton > button {
            min-width: 140px;
            font-size: 14px;
            white-space: nowrap;
            padding: 8px 12px;
            text-align: center;
            border-radius: 5px;
            margin: 5px;
            background-color: #E8F5E9;
            color: #2E7D32;
            border: 1px solid #2E7D32;
        }
        .stButton > button:hover {
            background-color: #C8E6C9;
        }
        div[data-testid="stSidebar"] {
            background-color: #F5F5F5;
        }
        div[data-testid="stSidebar"] .stRadio > label {
            background-color: #E8F5E9;
            color: #2E7D32;
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
            width: 100%;
            text-align: center;
        }
        div[data-testid="stSidebar"] .stRadio > label:hover {
            background-color: #C8E6C9;
        }
        div[data-testid="stSidebar"] .stRadio > label[data-baseweb="radio"] > div {
            border-color: #2E7D32;
        }
        </style>
    """, unsafe_allow_html=True)
    
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
    # Initialize session state for inputs to force KPI updates
    if 'opt_inputs' not in st.session_state:
        st.session_state.opt_inputs = {}
    if 'warehouse_inputs' not in st.session_state:
        st.session_state.warehouse_inputs = {}
    if 'packaging_inputs' not in st.session_state:
        st.session_state.packaging_inputs = {}
    if 'offset_inputs' not in st.session_state:
        st.session_state.offset_inputs = {}
    if 'load_inputs' not in st.session_state:
        st.session_state.load_inputs = {}
    if 'energy_inputs' not in st.session_state:
        st.session_state.energy_inputs = {}

    # Sidebar navigation
    with st.sidebar:
        st.markdown(
            """
            <div style='display: flex; align-items: center; padding: 10px;'>
                <h2 style='margin: 0; font-size: 24px; color: #2E7D32;'>Carbon 360</h2>
            </div>
            <hr style='margin: 10px 0;'>
            """,
            unsafe_allow_html=True
        )
        page = st.radio(
            "Navigate",
            [
                "Calculate Emissions",
                "Route Visualizer",
                "Supplier Lookup",
                "Reports",
                "Optimized Route Planning",
                "Green Warehousing",
                "Sustainable Packaging",
                "Carbon Offsetting",
                "Efficient Load Management",
                "Energy Conservation"
            ],
            index=[
                "Calculate Emissions",
                "Route Visualizer",
                "Supplier Lookup",
                "Reports",
                "Optimized Route Planning",
                "Green Warehousing",
                "Sustainable Packaging",
                "Carbon Offsetting",
                "Efficient Load Management",
                "Energy Conservation"
            ].index(st.session_state.page),
        )
        st.session_state.page = page

    # Main content logo
    st.markdown(
        """
        <div style='display: flex; align-items: center; padding: 10px;'>
            <h1 style='margin: 0; font-size: 28px; color: #2E7D32;'>Carbon 360</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Page content
    if page == "Calculate Emissions":
        st.header("Calculate CO₂ Emissions")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Source")
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
            
            st.subheader("Destination")
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
            transport_mode = st.selectbox("Transport Mode", list(EMISSION_FACTORS.keys()))
            weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1)
            st.session_state.weight_tons = weight_tons
            try:
                distance_km = calculate_distance(source_country, source_city, dest_country, dest_city)
                st.write(f"Estimated Distance: {distance_km} km")
            except ValueError as e:
                st.error(str(e))
                distance_km = 0.0
        
        if st.button("Calculate") and distance_km > 0:
            source = f"{source_city}, {source_country}"
            destination = f"{dest_city}, {dest_country}"
            try:
                co2_kg = calculate_co2(source_country, source_city, dest_country, dest_city, transport_mode, distance_km, weight_tons)
                st.success(f"Estimated CO₂ Emissions: {co2_kg} kg")
                save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons)
                
                st.subheader("Calculation Dashboard")
                col3, col4 = st.columns(2)
                with col3:
                    st.metric("Total Distance", f"{distance_km} km")
                    st.metric("Total CO₂ Emissions", f"{co2_kg} kg")
                with col4:
                    st.metric("Emission Factor", f"{EMISSION_FACTORS[transport_mode]} kg CO₂/km/ton")
                    st.metric("Weight", f"{weight_tons} tons")
                
                with st.expander("How were these values calculated?"):
                    st.write("**Distance Calculation**")
                    st.write("The distance between two cities is calculated using the **Haversine Formula**.")
                    st.write(f"Coordinates: {source_city} ({get_coordinates(source_country, source_city)}), {dest_city} ({get_coordinates(dest_country, dest_city)})")
                    
                    st.write("**CO₂ Emission Calculation**")
                    st.write("CO₂ = Distance (km) * Weight (tons) * Emission Factor")
                    st.write(f"Calculation: {distance_km} km * {weight_tons} tons * {EMISSION_FACTORS[transport_mode]} = {co2_kg} kg")
            except ValueError as e:
                st.error(str(e))
    
    elif page == "Route Visualizer":
        st.header("Emission Hotspot Visualizer")
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
                    <p><span style="color: green;">■</span> Low (<500 kg)</p>
                    <p><span style="color: orange;">■</span> Medium (500-1000 kg)</p>
                    <p><span style="color: red;">■</span> High (>1000 kg)</p>
                </div>
                '''
                m.get_root().html.add_child(folium.Element(legend_html))
                
                with st.spinner("Loading map..."):
                    folium_static(m, width=1200, height=600)
                
                st.subheader("Route Analytics Dashboard")
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
                    
                    st.subheader("Key Performance Indicators (KPIs)")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Distance", f"{distance_km:.2f} km")
                    with col2:
                        st.metric("Current CO₂ Emissions", f"{current_co2:.2f} kg")
                    with col3:
                        st.metric("Optimized CO₂ Emissions", f"{min_co2:.2f} kg")
                    with col4:
                        st.metric("CO₂ Savings", f"{savings:.2f} kg ({savings_pct:.1f}% reduction)")
                    
                    tab1, tab2 = st.tabs(["Route Breakdown", "Comparison Chart"])
                    
                    with tab1:
                        st.write("**Optimized Route Breakdown**")
                        if mode2:
                            st.write(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                            st.write(f"- **{mode2}**: {dist2:.2f} km, CO₂: {co2_2:.2f} kg")
                        else:
                            st.write(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                    
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
                        st.plotly_chart(fig, use_container_width=True, key=f"route_comparison_{time.time()}")
                except ValueError as e:
                    st.error(f"Error optimizing route: {e}")
            else:
                st.info("No emission routes to display. Calculate some emissions first!")
        except Exception as e:
            st.error(f"Error loading emissions: {e}")
    
    elif page == "Supplier Lookup":
        st.header("Supplier Lookup Dashboard")
        
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
                st.subheader("Key Performance Indicators (KPIs)")
                col4, col5, col6, col7 = st.columns(4)
                with col4:
                    st.metric("Total Suppliers", len(suppliers))
                with col5:
                    st.metric("Average Green Score", f"{suppliers['green_score'].mean():.1f}")
                with col6:
                    st.metric("Total Capacity", f"{suppliers['annual_capacity_tons'].sum():,} tons")
                
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
                            st.success(
                                f"🌍 **Local Sourcing Opportunity**: Source from {dest_country} to save {potential_savings:.2f} kg CO₂."
                            )
                        else:
                            st.info(f"No suppliers found in {dest_country}.")
                    except ValueError as e:
                        st.error(f"Error calculating savings: {e}")
                with col7:
                    st.metric("Potential CO₂ Savings", f"{potential_savings:.2f} kg")
                
                st.subheader("Supplier Insights 📊")
                tab1, tab2, tab3 = st.tabs(["Supplier Distribution", "Material Availability", "Supplier Details"])
                
                with tab1:
                    fig = px.bar(suppliers.groupby('country').size().reset_index(name='Count'),
                                x='country', y='Count', title="Suppliers by Country")
                    st.plotly_chart(fig, use_container_width=True, key=f"supplier_distribution_{time.time()}")
                
                with tab2:
                    fig = px.bar(suppliers.groupby('material')['annual_capacity_tons'].sum().reset_index(),
                                x='material', y='annual_capacity_tons', title="Material Capacity")
                    st.plotly_chart(fig, use_container_width=True, key=f"material_availability_{time.time()}")
                
                with tab3:
                    st.dataframe(suppliers[['supplier_name', 'country', 'city', 'material', 'green_score', 'sustainable_practices']])
            else:
                st.info("No suppliers found for the given criteria.")
        except Exception as e:
            st.error(f"Error loading suppliers: {e}")
    
    elif page == "Reports":
        st.header("Emission Reports")
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
                    st.subheader("Summary Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total CO₂ Emissions", f"{total_co2:.2f} kg")
                    with col2:
                        st.metric("Total Shipments", f"{total_shipments}")
                    with col3:
                        st.metric("Average CO₂ per Shipment", f"{avg_co2:.2f} kg")
                    with col4:
                        st.metric("Total CO₂ Savings", f"{total_savings:.2f} kg")
                    
                    st.subheader("Emission Breakdown by Transport Mode")
                    mode_summary = emissions.groupby('transport_mode')['co2_kg'].sum().reset_index()
                    fig = px.pie(mode_summary, values='co2_kg', names='transport_mode', title="CO₂ by Mode")
                    st.plotly_chart(fig, use_container_width=True, key=f"emission_breakdown_{time.time()}")
                
                with tab2:
                    st.subheader("CO₂ Impact Insights")
                    smartphone_charges = total_co2 * 1000 / 0.008
                    ev_distance = total_co2 / 0.2
                    st.write(f"**Energy Equivalent**: The {total_co2:.2f} kg of CO₂ could:")
                    st.write(f"- Charge {int(smartphone_charges):,} smartphones.")
                    st.write(f"- Power an EV for {ev_distance:.0f} km.")
                    st.write(f"**Environmental Fact**: Offset by planting {int(total_co2 * 0.05):,} trees!")
                
                with tab3:
                    st.subheader("Route Optimization Summary")
                    currency = st.selectbox("Currency", ['EUR', 'USD', 'AUD', 'SAR'])
                    carbon_price_per_kg = (CARBON_PRICE_EUR_PER_TON / 1000) * EXCHANGE_RATES[currency]
                    total_cost_savings = total_savings * carbon_price_per_kg
                    
                    st.write(f"**Carbon Price**: {CARBON_PRICE_EUR_PER_TON:.2f} EUR/tCO₂")
                    st.write(f"**Converted**: {carbon_price_per_kg:.4f} {currency}/kg CO₂")
                    st.write(f"**Total Savings**: {total_cost_savings:.2f} {currency}")
                    
                    df_routes = pd.DataFrame(route_data)
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=df_routes['Old CO₂'], y=df_routes['Route'], orientation='h', name='Current CO₂', marker_color='#FF4B4B'))
                    fig.add_trace(go.Bar(x=df_routes['New CO₂'], y=df_routes['Route'], orientation='h', name='Optimized CO₂', marker_color='#36A2EB'))
                    fig.update_layout(title="Current vs Optimized Route CO₂", barmode='group')
                    st.plotly_chart(fig, use_container_width=True, key=f"route_optimization_{time.time()}")
                    st.dataframe(df_routes[['Route', 'Old Mode', 'Old Distance', 'Old CO₂', 'New Modes', 'New Distances', 'New CO₂', 'Savings']])
                
                with tab4:
                    st.subheader("Detailed Data")
                    st.dataframe(emissions)
                    csv = emissions.to_csv(index=False)
                    st.download_button(label="Download as CSV", data=csv, file_name="emissions_report.csv", mime="text/csv")
            else:
                st.info("No emission data available.")
        except Exception as e:
            st.error(f"Error loading emissions: {e}")
    
    elif page == "Optimized Route Planning":
        st.header("Optimized Route Planning")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Route Details")
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
            weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1)
            st.session_state.weight_tons = weight_tons
            prioritize_green = st.checkbox("Prioritize Green Vehicles", value=True)
            try:
                distance_km = calculate_distance(source_country, source_city, dest_country, dest_city)
                st.write(f"Estimated Distance: {distance_km} km")
            except ValueError as e:
                st.error(str(e))
                distance_km = 0.0
        
        # Update session state for inputs
        st.session_state.opt_inputs = {
            "source_country": source_country,
            "source_city": source_city,
            "dest_country": dest_country,
            "dest_city": dest_city,
            "weight_tons": weight_tons,
            "prioritize_green": prioritize_green,
            "distance_km": distance_km
        }
        
        if st.button("Optimize Route") and distance_km > 0:
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
                trees_equivalent = int(savings * 0.05)  # 20 kg CO₂ per tree
                
                st.success(f"Optimized CO₂ Emissions: {min_co2:.2f} kg")
                
                # Display route map
                st.subheader("Route Map")
                source_coords = get_coordinates(source_country, source_city)
                dest_coords = get_coordinates(dest_country, dest_city)
                if source_coords != (0, 0) and dest_coords != (0, 0):
                    avg_lat = (source_coords[0] + dest_coords[0]) / 2
                    avg_lon = (source_coords[1] + dest_coords[1]) / 2
                    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=4, tiles='OpenStreetMap')
                    color = 'red' if min_co2 > 1000 else 'orange' if min_co2 > 500 else 'green'
                    folium.PolyLine(
                        locations=[source_coords, dest_coords],
                        color=color,
                        weight=3,
                        popup=f"{source_city} to {dest_city}: {min_co2:.2f} kg CO₂"
                    ).add_to(m)
                    folium.Marker(
                        location=source_coords,
                        popup=f"{source_city}: {min_co2:.2f} kg",
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                    folium.Marker(
                        location=dest_coords,
                        popup=f"{dest_city}: {min_co2:.2f} kg",
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                    with st.spinner("Loading map..."):
                        folium_static(m, width=1200, height=600)
                else:
                    st.error("Cannot display map: Invalid coordinates.")
                
                st.subheader("Key Performance Indicators (KPIs)")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("CO₂ Savings", f"{savings:.2f} kg")
                with col2:
                    st.metric("Cost Savings", f"${cost_savings:.2f}")
                with col3:
                    st.metric("Trees Equivalent", f"{trees_equivalent}")
                with col4:
                    st.metric("Route Efficiency", f"{savings_pct:.1f}%")
                
                st.subheader("Route Optimization Dashboard")
                tab1, tab2, tab3 = st.tabs(["Route Breakdown", "CO₂ Comparison", "Mode Contribution"])
                
                with tab1:
                    st.write("**Optimized Route Breakdown**")
                    if mode2:
                        st.write(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                        st.write(f"- **{mode2}**: {dist2:.2f} km, CO₂: {co2_2:.2f} kg")
                    else:
                        st.write(f"- **{mode1}**: {dist1:.2f} km, CO₂: {co2_1:.2f} kg")
                
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
                    st.plotly_chart(fig, use_container_width=True, key=f"opt_co2_comparison_{time.time()}")
                
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
                        st.plotly_chart(fig, use_container_width=True, key=f"opt_mode_contribution_{time.time()}")
                    else:
                        st.info("No CO₂ contributions to display.")
                
                with st.expander("Efficiency Gauge"):
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=savings_pct,
                        title={'text': "Route Efficiency (%)"},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#36A2EB"}}
                    ))
                    st.plotly_chart(fig, use_container_width=True, key=f"opt_efficiency_gauge_{time.time()}")
            except ValueError as e:
                st.error(f"Error optimizing route: {e}")
    
    elif page == "Green Warehousing":
        st.header("Green Warehousing")
        col1, col2 = st.columns(2)
        
        with col1:
            warehouse_size_m2 = st.number_input("Warehouse Size (m²)", min_value=100, max_value=100000, value=1000)
            led_percentage = st.slider("LED Lighting Usage (%)", 0, 100, 50) / 100
            solar_percentage = st.slider("Solar Panel Usage (%)", 0, 100, 30) / 100
        
        # Update session state for inputs
        st.session_state.warehouse_inputs = {
            "warehouse_size_m2": warehouse_size_m2,
            "led_percentage": led_percentage,
            "solar_percentage": solar_percentage
        }
        
        with col2:
            co2_savings_kg, energy_savings_kwh = calculate_warehouse_savings(warehouse_size_m2, led_percentage, solar_percentage)
            cost_savings = energy_savings_kwh * 0.15  # $0.15/kWh
            car_miles_equivalent = co2_savings_kg / 0.4 if co2_savings_kg > 0 else 0  # 0.4 kg CO₂/mile
            
            if led_percentage == 0 and solar_percentage == 0:
                st.warning("No LED or solar usage selected. Increase usage to calculate savings.")
            
            st.subheader("Key Performance Indicators (KPIs)")
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                st.metric("CO₂ Savings", f"{co2_savings_kg:.2f} kg/year")
            with col4:
                st.metric("Energy Savings", f"{energy_savings_kwh:.2f} kWh")
            with col5:
                st.metric("Cost Savings", f"${cost_savings:.2f}")
            with col6:
                st.metric("Car Miles Equivalent", f"{int(car_miles_equivalent)} miles")
            
            st.write("**Assumptions**:")
            st.write("- Traditional warehouse: 100 kWh/m²/year (average for medium-sized warehouses).")
            st.write("- LED saves 50% energy, solar saves 30%.")
            st.write("- 0.5 kg CO₂ per kWh (grid average), $0.15/kWh, 0.4 kg CO₂/mile (passenger car).")
        
        st.subheader("Green Warehousing Dashboard")
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
                st.plotly_chart(fig, use_container_width=True, key=f"warehouse_savings_breakdown_{time.time()}")
            else:
                st.info("No savings to display. Adjust LED or solar usage.")
        
        with tab2:
            sizes = [max(100, warehouse_size_m2 * i / 5) for i in range(1, 6)]  # Dynamic range based on input
            co2_trend = [calculate_warehouse_savings(size, led_percentage, solar_percentage)[0] for size in sizes]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sizes, y=co2_trend, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Warehouse Size", xaxis_title="Size (m²)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key=f"warehouse_trend_analysis_{time.time()}")
    
    elif page == "Sustainable Packaging":
        st.header("Sustainable Packaging")
        col1, col2 = st.columns(2)
        
        with col1:
            material_type = st.selectbox("Packaging Material", list(PACKAGING_EMISSIONS.keys()))
            weight_kg = st.number_input("Packaging Weight (kg)", min_value=0.1, max_value=10000.0, value=1.0)
        
        # Update session state for inputs
        st.session_state.packaging_inputs = {
            "material_type": material_type,
            "weight_kg": weight_kg
        }
        
        with col2:
            co2_kg = weight_kg * PACKAGING_EMISSIONS[material_type]
            potential_savings = co2_kg - weight_kg * PACKAGING_EMISSIONS['Biodegradable'] if material_type not in ['Biodegradable', 'Reusable'] else 0
            cost_impact = weight_kg * (PACKAGING_COSTS[material_type] - PACKAGING_COSTS['Biodegradable'])
            plastic_bottles = co2_kg / 0.12 if material_type == 'Plastic' else 0  # 0.12 kg CO₂ per bottle
            
            st.subheader("Key Performance Indicators (KPIs)")
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                st.metric("CO₂ Emissions", f"{co2_kg:.2f} kg")
            with col4:
                st.metric("Potential Savings", f"{potential_savings:.2f} kg")
            with col5:
                st.metric("Cost Impact", f"${cost_impact:.2f}")
            with col6:
                st.metric("Plastic Bottles", f"{int(plastic_bottles)}")
            
            if material_type not in ['Biodegradable', 'Reusable']:
                st.info(f"Switch to Biodegradable to save {potential_savings:.2f} kg CO₂.")
            
            if st.button("Save Packaging Data"):
                save_packaging(material_type, weight_kg, co2_kg)
                st.success("Packaging data saved!")
        
        st.subheader("Sustainable Packaging Dashboard")
        tab1, tab2 = st.tabs(["Material Comparison", "Historical Trends"])
        
        with tab1:
            materials = list(PACKAGING_EMISSIONS.keys())
            emissions = [weight_kg * PACKAGING_EMISSIONS[m] for m in materials]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=materials, y=emissions, name="CO₂ Emissions (kg)"))
            fig.update_layout(title="CO₂ Emissions by Material")
            st.plotly_chart(fig, use_container_width=True, key=f"packaging_material_comparison_{time.time()}")
        
        with tab2:
            try:
                packaging = get_packaging()
                if not packaging.empty:
                    packaging['timestamp'] = pd.to_datetime(packaging['timestamp'], errors='coerce')
                    packaging = packaging.dropna(subset=['timestamp'])  # Drop invalid timestamps
                    trend_data = packaging.groupby(packaging['timestamp'].dt.date)['co2_kg'].sum().reset_index()
                    if not trend_data.empty:
                        fig = px.line(trend_data, x='timestamp', y='co2_kg', title="Packaging Emissions Over Time")
                        st.plotly_chart(fig, use_container_width=True, key=f"packaging_historical_trends_{time.time()}")
                    else:
                        st.info("No valid packaging data available for trends.")
                else:
                    st.info("No packaging data available. Save some packaging data first!")
            except Exception as e:
                st.error(f"Error loading packaging data: {e}")
    
    elif page == "Carbon Offsetting":
        st.header("Carbon Offsetting Programs")
        col1, col2 = st.columns(2)
        
        with col1:
            project_type = st.selectbox("Offset Project", list(OFFSET_COSTS.keys()))
            co2_offset_tons = st.number_input("CO₂ to Offset (tons)", min_value=0.1, max_value=10000.0, value=1.0)
        
        # Update session state for inputs
        st.session_state.offset_inputs = {
            "project_type": project_type,
            "co2_offset_tons": co2_offset_tons
        }
        
        with col2:
            cost_usd = co2_offset_tons * OFFSET_COSTS[project_type]
            trees_equivalent = int(co2_offset_tons * 1000 * 0.05)  # 20 kg CO₂ per tree
            efficiency = cost_usd / co2_offset_tons if co2_offset_tons > 0 else 0
            
            st.subheader("Key Performance Indicators (KPIs)")
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                st.metric("CO₂ Offset", f"{co2_offset_tons:.2f} tons")
            with col4:
                st.metric("Offset Cost", f"${cost_usd:.2f}")
            with col5:
                st.metric("Trees Equivalent", f"{trees_equivalent}")
            with col6:
                st.metric("Efficiency", f"${efficiency:.2f}/ton")
            
            st.write(f"**Project**: {project_type}")
            st.write(f"Offsetting {co2_offset_tons} tons CO₂")
            
            if st.button("Save Offset"):
                save_offset(project_type, co2_offset_tons, cost_usd)
                st.success("Offset data saved!")
        
        st.subheader("Carbon Offsetting Dashboard")
        tab1, tab2 = st.tabs(["Project Distribution", "Cost vs Offset"])
        
        with tab1:
            try:
                offsets = get_offsets()
                if not offsets.empty:
                    project_summary = offsets.groupby('project_type')['co2_offset_tons'].sum().reset_index()
                    fig = px.pie(project_summary, values='co2_offset_tons', names='project_type', title="CO₂ Offset by Project")
                    st.plotly_chart(fig, use_container_width=True, key=f"offset_project_distribution_{time.time()}")
                else:
                    st.info("No offset data available. Save some offset data first!")
            except Exception as e:
                st.error(f"Error loading offset data: {e}")
        
        with tab2:
            try:
                if not offsets.empty:
                    project_summary = offsets.groupby('project_type').agg({'co2_offset_tons': 'sum', 'cost_usd': 'sum'}).reset_index()
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=project_summary['co2_offset_tons'],
                        y=project_summary['project_type'],
                        name='CO₂ Offset (tons)',
                        marker_color='#36A2EB'
                    ))
                    fig.add_trace(go.Bar(
                        x=project_summary['cost_usd'],
                        y=project_summary['project_type'],
                        name='Cost (USD)',
                        marker_color='#FF9999'
                    ))
                    fig.update_layout(title="Cost vs CO₂ Offset", barmode='group')
                    st.plotly_chart(fig, use_container_width=True, key=f"offset_cost_vs_offset_{time.time()}")
                else:
                    st.info("No offset data available. Save some offset data first!")
            except Exception as e:
                st.error(f"Error loading offset data: {e}")
    
    elif page == "Efficient Load Management":
        st.header("Efficient Load Management")
        col1, col2 = st.columns(2)
        
        with col1:
            weight_tons = st.number_input("Total Weight (tons)", min_value=0.1, max_value=100000.0, value=10.0)
            vehicle_capacity_tons = st.number_input("Vehicle Capacity (tons)", min_value=1.0, max_value=100.0, value=20.0)
            avg_trip_distance_km = st.number_input("Average Trip Distance (km)", min_value=1.0, max_value=10000.0, value=100.0)
        
        # Update session state for inputs
        st.session_state.load_inputs = {
            "weight_tons": weight_tons,
            "vehicle_capacity_tons": vehicle_capacity_tons,
            "avg_trip_distance_km": avg_trip_distance_km
        }
        
        with col2:
            trips_saved, co2_savings_kg = calculate_load_optimization(weight_tons, vehicle_capacity_tons, avg_trip_distance_km)
            fuel_savings_usd = trips_saved * avg_trip_distance_km * 0.1 * 1.5  # 0.1 liter/km/ton, $1.5/liter
            flights_equivalent = co2_savings_kg / 1000  # 1000 kg CO₂ per flight
            
            if trips_saved == 0:
                st.warning("No trips saved. Increase total weight or reduce vehicle capacity to enable optimization.")
            
            st.subheader("Key Performance Indicators (KPIs)")
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                st.metric("Trips Saved", f"{trips_saved}")
            with col4:
                st.metric("CO₂ Savings", f"{co2_savings_kg:.2f} kg")
            with col5:
                st.metric("Fuel Cost Savings", f"${fuel_savings_usd:.2f}")
            with col6:
                st.metric("Flights Equivalent", f"{int(flights_equivalent)}")
            
            st.write("**Assumptions**:")
            st.write("- Non-optimized: 90% vehicle capacity.")
            st.write("- Optimized: 98% vehicle capacity.")
            st.write("- Truck emissions: 0.096 kg CO₂/km/ton (diesel HGV).")
            st.write("- Fuel: 0.1 liter/km/ton (average for heavy trucks), $1.5/liter (diesel price).")
        
        st.subheader("Load Management Dashboard")
        tab1, tab2 = st.tabs(["Savings Breakdown", "Weight Sensitivity"])
        
        with tab1:
            if trips_saved > 0 or co2_savings_kg > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=[trips_saved], y=['Trips Saved'], name="Trips"))
                fig.add_trace(go.Bar(x=[co2_savings_kg], y=['CO₂ Savings (kg)'], name="CO₂"))
                fig.update_layout(title="Load Optimization Savings", barmode='group')
                st.plotly_chart(fig, use_container_width=True, key=f"load_savings_breakdown_{time.time()}")
            else:
                st.info("No savings to display. Adjust inputs to enable optimization.")
        
        with tab2:
            weights = [max(0.1, weight_tons * i / 5) for i in range(1, 6)]  # Dynamic range based on input
            savings = [calculate_load_optimization(w, vehicle_capacity_tons, avg_trip_distance_km)[1] for w in weights]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=weights, y=savings, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Total Weight", xaxis_title="Weight (tons)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key=f"load_weight_sensitivity_{time.time()}")
    
    elif page == "Energy Conservation":
        st.header("Energy Conservation in Facilities")
        col1, col2 = st.columns(2)
        
        with col1:
            facility_size_m2 = st.number_input("Facility Size (m²)", min_value=100, max_value=100000, value=1000)
            smart_system_usage = st.slider("Smart System Usage (%)", 0, 100, 50) / 100
        
        # Update session state for inputs
        st.session_state.energy_inputs = {
            "facility_size_m2": facility_size_m2,
            "smart_system_usage": smart_system_usage
        }
        
        with col2:
            energy_savings_kwh = facility_size_m2 * 120 * smart_system_usage * 0.4  # 120 kWh/m²/year, 40% savings
            co2_savings_kg = energy_savings_kwh * 0.5  # 0.5 kg CO₂ per kWh
            cost_savings = energy_savings_kwh * 0.15  # $0.15/kWh
            households_equivalent = energy_savings_kwh / 10000  # 10,000 kWh/year per household
            
            if smart_system_usage == 0:
                st.warning("No smart systems selected. Increase Smart System Usage to calculate savings.")
            
            st.subheader("Key Performance Indicators (KPIs)")
            col3, col4, col5, col6 = st.columns(4)
            with col3:
                st.metric("CO₂ Savings", f"{co2_savings_kg:.2f} kg/year")
            with col4:
                st.metric("Energy Savings", f"{energy_savings_kwh:.2f} kWh")
            with col5:
                st.metric("Cost Savings", f"${cost_savings:.2f}")
            with col6:
                st.metric("Households Equivalent", f"{int(households_equivalent)}")
            
            st.write("**Assumptions**:")
            st.write("- Facility: 120 kWh/m²/year (average for industrial facilities).")
            st.write("- Smart systems (e.g., IoT, automation) save 40% energy.")
            st.write("- 0.5 kg CO₂/kWh (grid average), $0.15/kWh (commercial rate).")
        
        st.subheader("Energy Conservation Dashboard")
        tab1, tab2 = st.tabs(["Savings Breakdown", "Smart System Impact"])
        
        with tab1:
            if co2_savings_kg > 0 or energy_savings_kwh > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=[co2_savings_kg],
                    y=['Smart Systems'],
                    name="CO₂ Savings (kg)"
                ))
                fig.add_trace(go.Bar(
                    x=[energy_savings_kwh],
                    y=['Smart Systems'],
                    name="Energy Savings (kWh)"
                ))
                fig.update_layout(title="Savings from Smart Systems", barmode='group')
                st.plotly_chart(fig, use_container_width=True, key=f"energy_savings_breakdown_{time.time()}")
            else:
                st.info("No savings to display. Increase Smart System Usage.")
        
        with tab2:
            usage_levels = [i / 100 for i in range(0, 101, 10)]  # 0% to 100% in 10% steps
            co2_trend = [facility_size_m2 * 120 * usage * 0.4 * 0.5 for usage in usage_levels]  # CO₂ savings
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[u * 100 for u in usage_levels], y=co2_trend, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Smart System Usage", xaxis_title="Usage (%)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key=f"energy_smart_system_impact_{time.time()}")

if __name__ == "__main__":
    main()
