import streamlit as st

st.title("🌍 NDVI GIS Dashboard")

st.write("Sizning birinchi GIS web ilovangiz ishga tushdi 🎉")

year = st.slider("Yilni tanlang", 2015, 2024)

st.success(f"Tanlangan yil: {year}")
