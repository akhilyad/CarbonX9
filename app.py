import streamlit as st
import pandas as pd
import sqlite3
import folium
from streamlit_folium import folium_static
import plotly.express as px
from math import radians, sin, cos, sqrt, atan2

# Database connection
conn = sqlite3.connect('emissions.db')
cursor = conn.cursor()

# Sample supplier data (if not already in DB)
cursor.execute('''
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT,
    country TEXT,
    city TEXT,
    material TEXT,
    green_score REAL,
    capacity REAL
)
''')
# Insert sample data if table is empty
cursor.execute("SELECT COUNT(*) FROM suppliers")
if cursor.fetchone()[0] == 0:
    sample_suppliers = [
        ('Supplier A', 'USA', 'New York', 'Steel', 85.0, 1000.0),
        ('Supplier B', 'China', 'Shanghai', 'Steel', 70.0, 2000.0),
        ('Supplier C', 'Germany', 'Berlin', 'Electronics', 90.0, 500.0),
    ]
    cursor.executemany("INSERT INTO suppliers (name, country, city, material, green_score, capacity) VALUES (?, ?, ?, ?, ?, ?)", sample_suppliers)
    conn.commit()

# Emission factors (DEFRA based)
EMISSION_FACTORS = {
    'Truck': 0.096,
    'Train': 0.017,
    'Ship': 0.015,
    'Plane': 0.602
}

# Haversine formula for distance calculation
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

# Coordinates for cities (simplified)
CITY_COORDS = {
    ('USA', 'New York'): (40.7128, -74.0060),
    ('China', 'Shanghai'): (31.2304, 121.4737),
    ('Germany', 'Berlin'): (52.5200, 13.4050),
}

def get_coordinates(country, city):
    return CITY_COORDS.get((country, city), (0, 0))

# CO2 calculation
def calculate_co2(country1, city1, country2, city2, transport_mode, weight_tons):
    lat1, lon1 = get_coordinates(country1, city1)
    lat2, lon2 = get_coordinates(country2, city2)
    distance_km = calculate_distance(lat1, lon1, lat2, lon2)
    emission_factor = EMISSION_FACTORS.get(transport_mode, 0.096)
    co2_kg = distance_km * weight_tons * emission_factor
    return round(co2_kg, 2)

# Save emission data
def save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons):
    cursor.execute('''
    INSERT INTO emissions (source, destination, transport_mode, distance_km, co2_kg, weight_tons)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (source, destination, transport_mode, distance_km, co2_kg, weight_tons))
    conn.commit()

# Main function
def main():
    # Initialize session_state.page if not set
    if 'page' not in st.session_state:
        st.session_state.page = "Calculate Emissions"

    # Add logo to sidebar
    st.sidebar.image('logo.png', use_column_width=True)

    # Navigation
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    with col1:
        st.markdown("<div style='display: flex; align-items: center;'><h1 style='margin: 0; font-size: 28px; color: #2E7D32;'>Carbon 360</h1></div>", unsafe_allow_html=True)
    with col2:
        if st.button("Calculate Emissions", key="nav_calculate"):
            st.session_state.page = "Calculate Emissions"
    with col3:
        if st.button("Route Visualizer", key="nav_visualizer"):
            st.session_state.page = "Route Visualizer"
    with col4:
        if st.button("Supplier Lookup", key="nav_supplier"):
            st.session_state.page = "Supplier Lookup"
    with col5:
        if st.button("Reports", key="nav_reports"):
            st.session_state.page = "Reports"

    # Page content
    if st.session_state.page == "Calculate Emissions":
        st.header("Calculate Emissions")
        source_country = st.selectbox("Source Country", ["USA", "China", "Germany"])
        source_city = st.selectbox("Source City", ["New York", "Shanghai", "Berlin"])
        dest_country = st.selectbox("Destination Country", ["USA", "China", "Germany"])
        dest_city = st.selectbox("Destination City", ["New York", "Shanghai", "Berlin"])
        transport_mode = st.selectbox("Transport Mode", ["Truck", "Train", "Ship", "Plane"])
        weight_tons = st.number_input("Weight (tons)", min_value=0.0, value=1.0)
        if st.button("Calculate"):
            source = f"{source_city}, {source_country}"
            destination = f"{dest_city}, {dest_country}"
            distance_km = calculate_distance(*get_coordinates(source_country, source_city), *get_coordinates(dest_country, dest_city))
            co2_kg = calculate_co2(source_country, source_city, dest_country, dest_city, transport_mode, weight_tons)
            st.success(f"Estimated CO₂ Emissions: {co2_kg} kg")
            save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons)
            # Additional metrics and expanders (retained)

    elif st.session_state.page == "Route Visualizer":
        st.header("Route Visualizer")
        # Placeholder for existing Route Visualizer content
        m = folium.Map(location=[40.7128, -74.0060], zoom_start=10)
        folium.Marker([40.7128, -74.0060], popup="New York").add_to(m)
        folium_static(m)

    elif st.session_state.page == "Supplier Lookup":
        st.header("Supplier Lookup")
        # Placeholder for existing Supplier Lookup content
        suppliers = pd.read_sql_query("SELECT * FROM suppliers", conn)
        st.dataframe(suppliers)

    elif st.session_state.page == "Reports":
        st.header("Reports")
        # Placeholder for existing Reports content
        emissions = pd.read_sql_query("SELECT * FROM emissions", conn)
        st.dataframe(emissions)

    # Footer with corrected links
    st.markdown("""
    <div style='text-align: center; padding: 10px; background-color: #f0f0f0;'>
        <a href='/contact' style='margin: 0 10px;'>Contact</a>
        <a href='/services' style='margin: 0 10px;'>Services</a>
        <a href='/about' style='margin: 0 10px;'>About</a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()