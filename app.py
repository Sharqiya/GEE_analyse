import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, Draw, MeasureControl, MiniMap, Fullscreen
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# =============================================================================
# GOOGLE EARTH ENGINE INIT
# =============================================================================
def init_earth_engine():
    try:
        service_account = st.secrets["earth_engine"]["service_account"]
        private_key = st.secrets["earth_engine"]["private_key"]
        project = st.secrets["earth_engine"]["project"]
        
        credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
        ee.Initialize(credentials, project=project)
        return True
    except Exception as e:
        st.sidebar.error(f"❌ GEE xato: {str(e)}")
        return False

# =============================================================================
# SAHLAMA
# =============================================================================
st.set_page_config(page_title="🌾 Xorazm NDVI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f4e79; text-align: center; }
    .sub-header { font-size: 1.2rem; color: #555; text-align: center; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_xorazm_districts():
    return {
        "Urganch": {"center": [41.55, 60.63], "area": 450, "color": "#FF6B6B"},
        "Xiva": {"center": [41.38, 60.37], "area": 380, "color": "#4ECDC4"},
        "Gurlan": {"center": [41.85, 60.40], "area": 320, "color": "#45B7D1"},
        "Shovot": {"center": [41.65, 60.30], "area": 290, "color": "#96CEB4"},
        "Yangiariq": {"center": [41.30, 60.55], "area": 410, "color": "#FFEAA7"},
        "Yangibozor": {"center": [41.73, 60.55], "area": 350, "color": "#DDA0DD"},
        "Xonqa": {"center": [41.47, 60.78], "area": 270, "color": "#98D8C8"},
        "Bog'ot": {"center": [41.35, 60.85], "area": 310, "color": "#F7DC6F"},
        "Tuproqqal'a": {"center": [41.75, 61.15], "area": 520, "color": "#BB8FCE"},
        "Qo'rg'ontepa": {"center": [41.25, 61.30], "area": 440, "color": "#85C1E9"},
    }

@st.cache_data(ttl=1800)
def generate_ndvi_data(district, date_start, date_end):
    np.random.seed(42)
    dates = pd.date_range(start=date_start, end=date_end, freq='5D')
    base_ndvi = {
        "Urganch": 0.45, "Xiva": 0.52, "Gurlan": 0.38, "Shovot": 0.41,
        "Yangiariq": 0.48, "Yangibozor": 0.43, "Xonqa": 0.50, "Bog'ot": 0.35,
        "Tuproqqal'a": 0.40, "Qo'rg'ontepa": 0.33
    }
    data = []
    for date in dates:
        month = date.month
        if month in [3, 4, 5]: seasonal_factor = 1.3
        elif month in [6, 7, 8]: seasonal_factor = 0.9
        elif month in [9, 10]: seasonal_factor = 0.7
        else: seasonal_factor = 0.4
        ndvi = base_ndvi[district] * seasonal_factor + np.random.normal(0, 0.05)
        ndvi = max(0.1, min(0.95, ndvi))
        irrigation_factor = 1.1 if district in ["Urganch", "Xiva", "Yangiariq"] else 1.0
        data.append({
            "date": date, "ndvi": round(ndvi * irrigation_factor, 3),
            "district": district, "month": month,
            "season": {3:"Bahor",4:"Bahor",5:"Bahor",6:"Yoz",7:"Yoz",8:"Yoz",
                      9:"Kuz",10:"Kuz",11:"Kuz",12:"Qish",1:"Qish",2:"Qish"}[month]
        })
    return pd.DataFrame(data)

def get_ndvi_color(ndvi):
    if ndvi < 0.2: return "#8B0000"
    elif ndvi < 0.4: return "#FF4500"
    elif ndvi < 0.6: return "#FFD700"
    elif ndvi < 0.75: return "#7CFC00"
    else: return "#006400"

def get_gee_ndvi_url(start_date, end_date, cloud_threshold=20):
    try:
        xorazm = ee.Geometry.Rectangle([60.0, 41.0, 61.5, 42.0])
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(xorazm).filterDate(str(start_date), str(end_date))\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))
        ndvi = s2.map(lambda i: i.normalizedDifference(['B8', 'B4']).rename('NDVI')).median()
        return ndvi.getMapId({
            'min': -0.2, 'max': 0.8,
            'palette': ['#8B0000','#FF4500','#FFD700','#7CFC00','#228B22','#006400']
        })['tile_fetcher'].url_format
    except: return None

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.title("🛰️ Boshqaruv Paneli")
    ee_ok = init_earth_engine()
    if ee_ok: st.success("✅ GEE ulandi")
    else: st.warning("⚠️ GEE ulanmadi")
    
    st.markdown("---")
    st.subheader("📅 Vaqt Oralig'i")
    c1, c2 = st.columns(2)
    with c1: start_date = st.date_input("Boshlanish", datetime(2026, 3, 1))
    with c2: end_date = st.date_input("Tugash", datetime(2026, 5, 13))
    
    st.subheader("🏘️ Tumanlar")
    districts = get_xorazm_districts()
    selected = st.multiselect("Tanlang:", list(districts.keys()), default=["Urganch","Xiva","Gurlan"])
    
    st.subheader("🗺️ Vizualizatsiya")
    viz = st.radio("Turi:", ["GEE Real NDVI","Choropleth","Issiqlik","Markerlar"])
    
    st.subheader("⚙️ Sozlamalar")
    st.checkbox("Legenda", value=True)
    st.checkbox("Koordinata tori", value=False)

# =============================================================================
# ASOSIY QISM
# =============================================================================
st.markdown('<h1 class="main-header">🌾 Xorazm Viloyati NDVI Monitoring</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Sentinel-2 + Google Earth Engine</p>', unsafe_allow_html=True)

# Statistika
if selected:
    all_data = [generate_ndvi_data(d, start_date, end_date) for d in selected]
    combined = pd.concat(all_data, ignore_index=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📊 O'rtacha", f"{combined['ndvi'].mean():.3f}")
    c2.metric("🌿 Max", f"{combined['ndvi'].max():.3f}")
    c3.metric("🍂 Min", f"{combined['ndvi'].min():.3f}")
    c4.metric("✅ Sog'lom", f"{(combined['ndvi']>0.6).sum()/len(combined)*100:.1f}%")

# Xarita
st.markdown("---")
st.subheader("🗺️ Interaktiv Xarita")

m = folium.Map(location=[41.5,60.6], zoom_start=9, tiles='CartoDB dark_matter')

if viz == "GEE Real NDVI" and ee_ok:
    with st.spinner("🛰️ Sentinel-2 yuklanmoqda..."):
        url = get_gee_ndvi_url(start_date, end_date)
        if url:
            folium.TileLayer(tiles=url, attr='GEE|Sentinel-2', name='🌿 Real NDVI', overlay=True, opacity=0.9).add_to(m)
            st.success("✅ Haqiqiy NDVI yuklandi!")
        else: st.warning("⚠️ GEE xato")

elif viz == "Choropleth" and selected:
    # Choropleth kodlari...
    pass

elif viz == "Issiqlik" and selected:
    # HeatMap kodlari...
    pass

elif viz == "Markerlar" and selected:
    for d in selected:
        df = generate_ndvi_data(d, start_date, end_date)
        center = districts[d]["center"]
        latest = df['ndvi'].iloc[-1]
        folium.CircleMarker(location=center, radius=20+latest*30,
            popup=f"<b>{d}</b><br>NDVI: {latest:.3f}",
            color=get_ndvi_color(latest), fill=True, fill_opacity=0.7).add_to(m)

Draw(export=True).add_to(m)
MeasureControl(position='topleft').add_to(m)
MiniMap().add_to(m)
Fullscreen().add_to(m)
folium.LayerControl().add_to(m)

st_folium(m, width=900, height=600)

# Grafiklar
st.markdown("---")
t1,t2,t3,t4 = st.tabs(["📈 Vaqt","📊 Taqqoslash","🎯 Tahlil","💾 Yuklash"])

with t1:
    if selected:
        fig = go.Figure()
        for d in selected:
            df = generate_ndvi_data(d, start_date, end_date)
            fig.add_trace(go.Scatter(x=df['date'], y=df['ndvi'], mode='lines+markers', name=d))
        fig.update_layout(title="NDVI Dinamikasi", xaxis_title="Sana", yaxis_title="NDVI", height=500, yaxis=dict(range=[0,1]))
        st.plotly_chart(fig, use_container_width=True)

with t2:
    if selected:
        comp = [{"Tuman":d, "O'rtacha":generate_ndvi_data(d,start_date,end_date)['ndvi'].mean()} for d in selected]
        df = pd.DataFrame(comp)
        fig = px.bar(df, x="Tuman", y="O'rtacha", color="O'rtacha", color_continuous_scale="YlGn", range_color=[0,1])
        st.plotly_chart(fig, use_container_width=True)

with t3:
    if selected:
        for d in selected:
            df = generate_ndvi_data(d, start_date, end_date)
            avg = df['ndvi'].mean()
            st.markdown(f"**{d}:** {'🌟 A\'lo' if avg>0.7 else '✅ Yaxshi' if avg>0.5 else '⚠️ O\'rta' if avg>0.3 else '🚨 Yomon'} - {avg:.3f}")

with t4:
    if selected:
        export = pd.concat([generate_ndvi_data(d,start_date,end_date) for d in selected])
        st.dataframe(export, use_container_width=True)
        csv = export.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv, f"ndvi_{start_date}.csv", "text/csv")

st.markdown("---")
st.markdown("<center>🛰️ Sentinel-2 | ESA Copernicus | © 2026</center>", unsafe_allow_html=True)
