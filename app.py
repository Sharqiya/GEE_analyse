import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from datetime import datetime

st.set_page_config(page_title="Xorazm NDVI", layout="wide")

def init_earth_engine():
    try:
        service_account = st.secrets["earth_engine"]["service_account"]
        private_key = st.secrets["earth_engine"]["private_key"]
        project = st.secrets["earth_engine"]["project"]
        
        credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
        ee.Initialize(credentials, project=project)
        return True
    except Exception as e:
        st.sidebar.error(f"❌ Xato: {str(e)}")
        return False

with st.sidebar:
    st.title("🛰️ NDVI")
    ee_ok = init_earth_engine()
    if ee_ok:
        st.success("✅ GEE ulandi!")
    else:
        st.error("❌ GEE ulanmadi")
    
    start = st.date_input("Boshlanish", datetime(2026, 4, 1))
    end = st.date_input("Tugash", datetime(2026, 5, 13))

st.title("🌾 Xorazm NDVI")

m = folium.Map(location=[41.5, 60.6], zoom_start=9, tiles='CartoDB dark_matter')

if ee_ok:
    try:
        xorazm = ee.Geometry.Rectangle([60.0, 41.0, 61.5, 42.0])
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(xorazm).filterDate(str(start), str(end))\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        ndvi = s2.map(lambda i: i.normalizedDifference(['B8', 'B4']).rename('NDVI')).median()
        
        url = ndvi.getMapId({
            'min': -0.2, 'max': 0.8,
            'palette': ['#8B0000','#FF4500','#FFD700','#7CFC00','#228B22','#006400']
        })['tile_fetcher'].url_format
        
        folium.TileLayer(tiles=url, attr='GEE|Sentinel-2', name='NDVI', overlay=True, opacity=0.9).add_to(m)
    except Exception as e:
        st.error(f"NDVI xato: {e}")

folium.LayerControl().add_to(m)
st_folium(m, width=900, height=600)
