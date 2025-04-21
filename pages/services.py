import streamlit as st

st.title("Our Services")
st.write("- CO₂ Emission Calculation")
st.write("- Route Optimization")
st.write("- Supplier Management")
st.write("- Reporting")

# Footer with corrected links
st.markdown("""
<div style='text-align: center; padding: 10px; background-color: #f0f0f0;'>
    <a href='/contact' style='margin: 0 10px;'>Contact</a>
    <a href='/services' style='margin: 0 10px;'>Services</a>
    <a href='/about' style='margin: 0 10px;'>About</a>
</div>
""", unsafe_allow_html=True)