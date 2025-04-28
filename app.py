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

# [Previous functions: init_db, get_coordinates, calculate_distance, calculate_co2, optimize_route, 
# save_emission, save_packaging, save_offset, get_emissions, get_packaging, get_offsets, 
# get_suppliers, calculate_warehouse_savings, calculate_load_optimization remain unchanged]

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
    if 'dest_country' not in st.session_state or st.session_state.dest_country not in LOCATIONS:
        st.session_state.dest_country = next(iter(LOCATIONS))
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
    if page == "Optimized Route Planning":
        st.header("Optimized Route Planning")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Route Details")
            source_country = st.selectbox("Source Country", list(LOCATIONS.keys()), key="opt_source_country")
            source_city = st.selectbox("Source City", list(LOCATIONS[source_country].keys()), key="opt_source_city")
            dest_country = st.selectbox("Destination Country", list(LOCATIONS.keys()), key="opt_dest_country")
            dest_city = st.selectbox("Destination City", list(LOCATIONS[dest_country].keys()), key="opt_dest_city")
        
        with col2:
            weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=1.0, step=0.1)
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
                    st.plotly_chart(fig, use_container_width=True, key="opt_co2_comparison")
                
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
                        st.plotly_chart(fig, use_container_width=True, key="opt_mode_contribution")
                    else:
                        st.info("No CO₂ contributions to display.")
                
                with st.expander("Efficiency Gauge"):
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=savings_pct,
                        title={'text': "Route Efficiency (%)"},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#36A2EB"}}
                    ))
                    st.plotly_chart(fig, use_container_width=True, key="opt_efficiency_gauge")
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
                st.plotly_chart(fig, use_container_width=True, key="warehouse_savings_breakdown")
            else:
                st.info("No savings to display. Adjust LED or solar usage.")
        
        with tab2:
            sizes = [500, 1000, 2000, 5000, 10000]
            co2_trend = [calculate_warehouse_savings(size, led_percentage, solar_percentage)[0] for size in sizes]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=sizes, y=co2_trend, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Warehouse Size", xaxis_title="Size (m²)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key="warehouse_trend_analysis")
    
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
            st.plotly_chart(fig, use_container_width=True, key="packaging_material_comparison")
        
        with tab2:
            try:
                packaging = get_packaging()
                if not packaging.empty:
                    packaging['timestamp'] = pd.to_datetime(packaging['timestamp'])
                    trend_data = packaging.groupby(packaging['timestamp'].dt.date)['co2_kg'].sum().reset_index()
                    fig = px.line(trend_data, x='timestamp', y='co2_kg', title="Packaging Emissions Over Time")
                    st.plotly_chart(fig, use_container_width=True, key="packaging_historical_trends")
                else:
                    st.info("No packaging data available.")
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
                    fig = px.pie(offsets.groupby('project_type')['co2_offset_tons'].sum().reset_index(),
                                values='co2_offset_tons', names='project_type', title="CO₂ Offset by Project")
                    st.plotly_chart(fig, use_container_width=True, key="offset_project_distribution")
                else:
                    st.info("No offset data available.")
            except Exception as e:
                st.error(f"Error loading offset data: {e}")
        
        with tab2:
            try:
                if not offsets.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=offsets.groupby('project_type')['co2_offset_tons'].sum(),
                        y=list(OFFSET_COSTS.keys()),
                        name='CO₂ Offset (tons)',
                        marker_color='#36A2EB'
                    ))
                    fig.add_trace(go.Bar(
                        x=offsets.groupby('project_type')['cost_usd'].sum(),
                        y=list(OFFSET_COSTS.keys()),
                        name='Cost (USD)',
                        marker_color='#FF9999'
                    ))
                    fig.update_layout(title="Cost vs CO₂ Offset", barmode='group')
                    st.plotly_chart(fig, use_container_width=True, key="offset_cost_vs_offset")
                else:
                    st.info("No offset data available.")
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
                st.plotly_chart(fig, use_container_width=True, key="load_savings_breakdown")
            else:
                st.info("No savings to display. Adjust inputs to enable optimization.")
        
        with tab2:
            weights = [weight_tons * i / 5 for i in range(1, 6)]
            savings = [calculate_load_optimization(w, vehicle_capacity_tons, avg_trip_distance_km)[1] for w in weights]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=weights, y=savings, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Total Weight", xaxis_title="Weight (tons)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key="load_weight_sensitivity")
    
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
                fig.add_trace(go.Bar(x=[co2_savings_kg], y=['Smart Systems'], name="CO₂ Savings (kg)"))
                fig.add_trace(go.Bar(x=[energy_savings_kwh], y=['Smart Systems'], name="Energy Savings (kWh)"))
                fig.update_layout(title="Energy Conservation Savings", barmode='group')
                st.plotly_chart(fig, use_container_width=True, key="energy_savings_breakdown")
            else:
                st.info("No savings to display. Increase Smart System Usage.")
        
        with tab2:
            usages = [0.2, 0.4, 0.6, 0.8, 1.0]
            savings = [facility_size_m2 * 120 * u * 0.4 * 0.5 for u in usages]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[u*100 for u in usages], y=savings, mode='lines+markers', name='CO₂ Savings (kg)'))
            fig.update_layout(title="CO₂ Savings vs Smart System Usage", xaxis_title="Usage (%)", yaxis_title="CO₂ Savings (kg)")
            st.plotly_chart(fig, use_container_width=True, key="energy_smart_system_impact")

    # [Other pages: Calculate Emissions, Route Visualizer, Supplier Lookup, Reports remain unchanged]

if __name__ == "__main__":
    main()
