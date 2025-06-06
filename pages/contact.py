import streamlit as st

st.title("Contact Us")
st.write("Email: contact@antova.com")
st.write("Phone: +49 176 7267 8553")

# Footer with corrected links
st.markdown("""
<div style='text-align: center; padding: 10px; background-color: #f0f0f0;'>
    <a href='/contact' style='margin: 0 10px;'>Contact</a>
    <a href='/services' style='margin: 0 10px;'>Services</a>
    <a href='/about' style='margin: 0 10px;'>About</a>
</div>
""", unsafe_allow_html=True)
