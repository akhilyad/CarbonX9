import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import folium_static
import uuid
import math
import plotly.express as px
import plotly.graph_objects as go

# Initialize SQLite database
def init_db():
    """
    Initialize the SQLite database with suppliers and emissions tables.
    Inserts sample supplier data if not already present.
    
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            # Create suppliers table
            c.execute('''CREATE TABLE IF NOT EXISTS suppliers 
                        (id TEXT PRIMARY KEY, supplier_name TEXT, country TEXT, city TEXT, 
                         material TEXT, green_score INTEGER, annual_capacity_tons INTEGER)''')
            # Create emissions table
            c.execute('''CREATE TABLE IF NOT EXISTS emissions 
                        (id TEXT PRIMARY KEY, source TEXT, destination TEXT, 
                         transport_mode TEXT, distance_km REAL, co2_kg REAL, 
                         weight_tons REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            # Insert expanded supplier data
            sample_suppliers = [
                # United Kingdom - London
                (str(uuid.uuid4()), 'UK Steel Co', 'United Kingdom', 'London', 'Steel', 85, 50000),
                (str(uuid.uuid4()), 'London Tech Supplies', 'United Kingdom', 'London', 'Electronics', 70, 20000),
                (str(uuid.uuid4()), 'British Textiles Ltd', 'United Kingdom', 'London', 'Textiles', 65, 30000),
                # France - Paris
                (str(uuid.uuid4()), 'French Steelworks', 'France', 'Paris', 'Steel', 80, 45000),
                (str(uuid.uuid4()), 'Paris Electronics Hub', 'France', 'Paris', 'Electronics', 75, 25000),
                (str(uuid.uuid4()), 'ChemFrance', 'France', 'Paris', 'Chemicals', 60, 40000),
                # USA - New York
                (str(uuid.uuid4()), 'American Steel Corp', 'USA', 'New York', 'Steel', 75, 60000),
                (str(uuid.uuid4()), 'NY Tech Innovate', 'USA', 'New York', 'Electronics', 80, 30000),
                (str(uuid.uuid4()), 'US Textile Giants', 'USA', 'New York', 'Textiles', 70, 35000),
                # China - Shanghai
                (str(uuid.uuid4()), 'China Steel Group', 'China', 'Shanghai', 'Steel', 65, 80000),
                (str(uuid.uuid4()), 'Shanghai Electronics', 'China', 'Shanghai', 'Electronics', 60, 50000),
                (str(uuid.uuid4()), 'EastChem Co', 'China', 'Shanghai', 'Chemicals', 55, 60000),
                # Japan - Tokyo
                (str(uuid.uuid4()), 'Nippon Steel', 'Japan', 'Tokyo', 'Steel', 80, 55000),
                (str(uuid.uuid4()), 'Tokyo Tech Solutions', 'Japan', 'Tokyo', 'Electronics', 85, 40000),
                (str(uuid.uuid4()), 'Japan Textiles', 'Japan', 'Tokyo', 'Textiles', 70, 30000),
                # Australia - Sydney
                (str(uuid.uuid4()), 'Aussie Steelworks', 'Australia', 'Sydney', 'Steel', 75, 40000),
                (str(uuid.uuid4()), 'Sydney Chem Supplies', 'Australia', 'Sydney', 'Chemicals', 65, 35000),
                (str(uuid.uuid4()), 'Aus Textiles', 'Australia', 'Sydney', 'Textiles', 70, 25000)
            ]
            c.executemany('INSERT OR IGNORE INTO suppliers VALUES (?, ?, ?, ?, ?, ?, ?)', sample_suppliers)
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

# DEFRA-based emission factors (kg CO₂ per km per ton)
EMISSION_FACTORS = {
    'Truck': 0.096,  # HGV, diesel
    'Train': 0.028,  # Freight train
    'Ship': 0.016,   # Container ship
    'Plane': 0.602   # Cargo plane
}

# Country-city structure with coordinates (latitude, longitude)
LOCATIONS = {
    'United Kingdom': {
        'London': (51.5074, -0.1278),
    },
    'France': {
        'Paris': (48.8566, 2.3522),
    },
    'USA': {
        'New York': (40.7128, -74.0060),
    },
    'China': {
        'Shanghai': (31.2304, 121.4737),
    },
    'Japan': {
        'Tokyo': (35.6762, 139.6503),
    },
    'Australia': {
        'Sydney': (-33.8688, 151.2093),
    }
}

# Carbon pricing data (as of April 2025, based on EU ETS)
CARBON_PRICE_EUR_PER_TON = 65.89  # EU ETS price
EXCHANGE_RATES = {
    'EUR': 1.0,
    'USD': 1.06,  # Approximate
    'AUD': 1.62,  # Approximate
    'SAR': 3.98   # Approximate
}

def get_coordinates(country, city):
    """
    Get the coordinates (latitude, longitude) for a given country and city.
    
    Args:
        country (str): The country name.
        city (str): The city name.
    
    Returns:
        tuple: (latitude, longitude) or (0, 0) if not found.
    """
    return LOCATIONS.get(country, {}).get(city, (0, 0))

def calculate_distance(country1, city1, country2, city2):
    """
    Calculate the great-circle distance between two cities using the Haversine formula.
    
    Args:
        country1 (str): Source country.
        city1 (str): Source city.
        country2 (str): Destination country.
        city2 (str): Destination city.
    
    Returns:
        float: Distance in kilometers, rounded to 2 decimal places.
    
    Raises:
        ValueError: If coordinates are not found for the given cities.
    """
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
    """
    Calculate CO₂ emissions for a shipment.
    
    Args:
        country1 (str): Source country.
        city1 (str): Source city.
        country2 (str): Destination country.
        city2 (str): Destination city.
        transport_mode (str): Mode of transport (Truck, Train, Ship, Plane).
        distance_km (float): Distance in kilometers.
        weight_tons (float): Weight in tons.
    
    Returns:
        float: CO₂ emissions in kilograms, rounded to 2 decimal places.
    
    Raises:
        ValueError: If transport_mode is invalid.
    """
    emission_factor = EMISSION_FACTORS.get(transport_mode)
    if emission_factor is None:
        raise ValueError(f"Invalid transport mode: {transport_mode}")
    co2_kg = distance_km * weight_tons * emission_factor
    return round(co2_kg, 2)

def optimize_route(country1, city1, country2, city2, distance_km, weight_tons):
    """
    Optimize transport route by combining modes to minimize CO₂ emissions.
    
    Args:
        country1 (str): Source country.
        city1 (str): Source city.
        country2 (str): Destination country.
        city2 (str): Destination city.
        distance_km (float): Total distance in kilometers.
        weight_tons (float): Weight in tons.
    
    Returns:
        tuple: (best_option, min_co2, breakdown, distances)
            - best_option: (mode1, ratio1, mode2, ratio2)
            - min_co2: Total CO₂ emissions for the best option
            - breakdown: CO₂ emissions for each mode
            - distances: Distance for each mode
    """
    intercontinental = country1 != country2
    distance_short = distance_km < 1000
    distance_medium = 1000 <= distance_km < 5000
    distance_long = distance_km >= 5000

    combinations = []
    if intercontinental:
        if distance_long:
            combinations.extend([
                ('Ship', 0.9, 'Train', 0.1),
                ('Ship', 0.8, 'Truck', 0.2),
                ('Plane', 0.5, 'Ship', 0.5)
            ])
        elif distance_medium:
            combinations.extend([
                ('Ship', 0.7, 'Train', 0.3),
                ('Plane', 0.4, 'Truck', 0.6),
                ('Ship', 0.6, 'Plane', 0.4)
            ])
        else:
            combinations.extend([
                ('Train', 0.8, 'Truck', 0.2),
                ('Ship', 0.5, 'Truck', 0.5),
                ('Plane', 0.3, 'Truck', 0.7)
            ])
    else:
        if distance_short:
            combinations.extend([
                ('Train', 0.9, 'Truck', 0.1),
                ('Truck', 1.0, None, 0.0),
                ('Train', 1.0, None, 0.0)
            ])
        else:
            combinations.extend([
                ('Train', 0.7, 'Truck', 0.3),
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
    
    return best_option, round(min_co2, 2), best_breakdown, best_distances

def save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons):
    """
    Save emission data to the SQLite database.
    
    Args:
        source (str): Source location (city, country).
        destination (str): Destination location (city, country).
        transport_mode (str): Mode of transport.
        distance_km (float): Distance in kilometers.
        co2_kg (float): CO₂ emissions in kilograms.
        weight_tons (float): Weight in tons.
    
    Raises:
        sqlite3.Error: If a database error occurs.
    """
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

def get_emissions():
    """
    Retrieve all emission records from the database.
    
    Returns:
        pd.DataFrame: DataFrame containing emission data.
    
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM emissions', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_suppliers(country=None, city=None, material=None):
    """
    Retrieve suppliers from the database based on filters.
    
    Args:
        country (str, optional): Filter by country.
        city (str, optional): Filter by city.
        material (str, optional): Filter by material (case-insensitive).
    
    Returns:
        pd.DataFrame: DataFrame containing supplier data.
    
    Raises:
        sqlite3.Error: If a database error occurs.
    """
    try:
        with sqlite3.connect('emissions.db') as conn:
            query = 'SELECT * FROM suppliers'
            params = []
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
                query += ' WHERE ' + ' AND '.join(conditions)
            df = pd.read_sql_query(query, conn, params=params)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def main():
    st.set_page_config(page_title="CO₂ Emission Calculator", layout="wide")
    init_db()

    # Initialize session state for page navigation and sourcing data
    if 'page' not in st.session_state:
        st.session_state.page = "Calculate Emissions"
    if 'source_country' not in st.session_state or st.session_state.source_country not in LOCATIONS:
        st.session_state.source_country = next(iter(LOCATIONS))  # Default to first country
    if 'dest_country' not in st.session_state or st.session_state.dest_country not in LOCATIONS:
        st.session_state.dest_country = next(iter廉政