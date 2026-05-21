import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, Draw, MeasureControl, MiniMap, Fullscreen
import numpy as np
import pandas as pd
from datetime import datetime
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
        st.sidebar.error(f"GEE xato: {str(e)}")
        return False

# =============================================================================
# SAHLAMA
# =============================================================================
st.set_page_config(page_title="Xorazm NDVI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f4e79; text-align: center; }
    .sub-header { font-size: 1.2rem; color: #555; text-align: center; margin-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_xorazm_districts():
    return {
        "Urganch": {"center": [41.55, 60.63], "area": 450},
        "Xiva": {"center": [41.38, 60.37], "area": 380},
        "Gurlan": {"center": [41.85, 60.40], "area": 320},
        "Shovot": {"center": [41.65, 60.30], "area": 290},
        "Yangiariq": {"center": [41.30, 60.55], "area": 410},
        "Yangibozor": {"center": [41.73, 60.55], "area": 350},
        "Xonqa": {"center": [41.47, 60.78], "area": 270},
        "Bog'ot": {"center": [41.35, 60.85], "area": 310},
        "Tuproqqal'a": {"center": [41.75, 61.15], "area": 520},
        "Qo'rg'ontepa": {"center": [41.25, 61.30], "area": 440},
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

if selected:
    all_data = [generate_ndvi_data(d, start_date, end_date) for d in selected]
    combined = pd.concat(all_data, ignore_index=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("📊 O'rtacha", f"{combined['ndvi'].mean():.3f}")
    c2.metric("🌿 Max", f"{combined['ndvi'].max():.3f}")
    c3.metric("🍂 Min", f"{combined['ndvi'].min():.3f}")
    c4.metric("✅ Sog'lom", f"{(combined['ndvi']>0.6).sum()/len(combined)*100:.1f}%")

st.markdown("---")
st.subheader("🗺️ Interaktiv Xarita")

m = folium.Map(location=[41.5,60.6], zoom_start=9, tiles='CartoDB dark_matter')

if viz == "GEE Real NDVI" and ee_ok:
    with st.spinner("🛰️ Sentinel-2 yuklanmoqda..."):
        url = get_gee_ndvi_url(start_date, end_date)
        if url:
            folium.TileLayer(tiles=url, attr='GEE|Sentinel-2', name='🌿 Real NDVI', overlay=True, opacity=0.9).add_to(m)
            st.success("✅ Haqiqiy NDVI yuklandi!")

elif viz == "Choropleth" and selected:
    geojson_data = {"type": "FeatureCollection", "features": []}
    for name, info in districts.items():
        center = info["center"]
        offset = 0.15
        polygon = [
            [center[0]-offset, center[1]-offset], [center[0]-offset, center[1]+offset],
            [center[0]+offset, center[1]+offset], [center[0]+offset, center[1]-offset],
            [center[0]-offset, center[1]-offset]
        ]
        geojson_data["features"].append({
            "type": "Feature", "properties": {"name": name, "area_km2": info["area"]},
            "geometry": {"type": "Polygon", "coordinates": [polygon]}
        })
    ndvi_values = {}
    for d in selected:
        df = generate_ndvi_data(d, start_date, end_date)
        ndvi_values[d] = df['ndvi'].iloc[-1]
    for f in geojson_data['features']:
        f['properties']['ndvi'] = ndvi_values.get(f['properties']['name'], 0)
    choropleth = folium.Choropleth(
        geo_data=geojson_data, name='NDVI', data=pd.DataFrame([{"district":k,"ndvi":v} for k,v in ndvi_values.items()]),
        columns=['district','ndvi'], key_on='feature.properties.name', fill_color='YlGn',
        fill_opacity=0.7, line_opacity=0.4, legend_name='NDVI', smooth_factor=0.5, highlight=True
    ).add_to(m)
    choropleth.geojson.add_child(folium.features.GeoJsonTooltip(
        fields=['name','ndvi','area_km2'], aliases=['Tuman:','NDVI:','Maydon:'],
        style="background-color: #F0EFEF; border: 2px solid black; font-size: 13px;"
    ))

elif viz == "Issiqlik" and selected:
    heat_data = []
    for d in selected:
        df = generate_ndvi_data(d, start_date, end_date)
        center = districts[d]["center"]
        latest = df['ndvi'].iloc[-1]
        for _ in range(20):
            heat_data.append([center[0]+np.random.normal(0,0.05), center[1]+np.random.normal(0,0.05), latest*100])
    HeatMap(heat_data, radius=25, blur=15, max_zoom=10, gradient={0.4:'blue',0.65:'lime',1:'red'}).add_to(m)

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

col_map, col_info = st.columns([3, 1])
with col_map:
    st_folium(m, width=800, height=600)
with col_info:
    st.subheader("📋 Tuman Ma'lumotlari")
    for d in selected:
        df = generate_ndvi_data(d, start_date, end_date)
        latest = df['ndvi'].iloc[-1]
        trend = df['ndvi'].iloc[-1] - df['ndvi'].iloc[-5] if len(df) > 5 else 0
        bg = '#e8f5e9' if latest > 0.6 else '#fff3e0' if latest > 0.4 else '#ffebee'
        st.markdown(f"""
        <div style="padding:10px;border-radius:10px;background-color:{bg};margin-bottom:10px;">
            <h4 style="margin:0;">{d}</h4>
            <p style="margin:5px 0;font-size:1.2rem;font-weight:bold;color:{get_ndvi_color(latest)};">NDVI: {latest:.3f}</p>
            <p style="margin:0;font-size:0.9rem;">Trend: {'+' if trend>0 else ''}{trend:.3f}</p>
        </div>
        """, unsafe_allow_html=True)

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
            if avg > 0.7: status, emoji = "A'lo", "🌟"
            elif avg > 0.5: status, emoji = "Yaxshi", "✅"
            elif avg > 0.3: status, emoji = "O'rtacha", "⚠️"
            else: status, emoji = "Yomon", "🚨"
            st.markdown(f"**{d}:** {emoji} {status} - {avg:.3f}")
            st.markdown("---")

with t4:
    if selected:
        export = pd.concat([generate_ndvi_data(d,start_date,end_date) for d in selected])
        st.dataframe(export, use_container_width=True)
        csv = export.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv, f"ndvi_{start_date}.csv", "text/csv")

st.markdown("---")
st.markdown("<center>🛰️ Sentinel-2 | ESA Copernicus | © 2026</center>", unsafe_allow_html=True)
