import os

# Create the complete fixed app.py
app_code = '''import streamlit as st
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
# SAHLAMA VA KONFIGURATSIYA
# =============================================================================
st.set_page_config(
    page_title="🌾 Xorazm NDVI Monitoring",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS stillar
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f4e79;
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f4e79 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# YORDAMCHI FUNKSIYALAR
# =============================================================================
@st.cache_data(ttl=3600)
def get_xorazm_districts():
    """Xorazm viloyati tumanlari"""
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
    """Simulyatsiya NDVI ma'lumotlari"""
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
        if month in [3, 4, 5]:
            seasonal_factor = 1.3
        elif month in [6, 7, 8]:
            seasonal_factor = 0.9
        elif month in [9, 10]:
            seasonal_factor = 0.7
        else:
            seasonal_factor = 0.4
            
        ndvi = base_ndvi[district] * seasonal_factor + np.random.normal(0, 0.05)
        ndvi = max(0.1, min(0.95, ndvi))
        
        irrigation_factor = 1.1 if district in ["Urganch", "Xiva", "Yangiariq"] else 1.0
        
        data.append({
            "date": date,
            "ndvi": round(ndvi * irrigation_factor, 3),
            "district": district,
            "month": month,
            "season": {3:"Bahor",4:"Bahor",5:"Bahor",6:"Yoz",7:"Yoz",8:"Yoz",
                      9:"Kuz",10:"Kuz",11:"Kuz",12:"Qish",1:"Qish",2:"Qish"}[month]
        })
    
    return pd.DataFrame(data)

def get_ndvi_color(ndvi):
    """NDVI rangi"""
    if ndvi < 0.2:
        return "#8B0000"
    elif ndvi < 0.4:
        return "#FF4500"
    elif ndvi < 0.6:
        return "#FFD700"
    elif ndvi < 0.75:
        return "#7CFC00"
    else:
        return "#006400"

def get_gee_ndvi_url(start_date, end_date, cloud_threshold=20):
    """GEE dan real NDVI URL"""
    try:
        xorazm = ee.Geometry.Rectangle([60.0, 41.0, 61.5, 42.0])
        
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(xorazm)\
            .filterDate(str(start_date), str(end_date))\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))
        
        ndvi = s2.map(lambda i: i.normalizedDifference(['B8', 'B4']).rename('NDVI')).median()
        
        url = ndvi.getMapId({
            'min': -0.2, 
            'max': 0.8,
            'palette': ['#8B0000','#FF4500','#FFD700','#7CFC00','#228B22','#006400']
        })['tile_fetcher'].url_format
        
        return url
    except Exception as e:
        st.error(f"GEE NDVI xato: {e}")
        return None

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.title("🛰️ Boshqaruv Paneli")
    
    ee_ok = init_earth_engine()
    if ee_ok:
        st.success("✅ Google Earth Engine ulandi")
    else:
        st.warning("⚠️ GEE ulanmadi - Simulyatsiya rejimi")
    
    st.markdown("---")
    
    st.subheader("📅 Vaqt Oralig'i")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Boshlanish", datetime(2026, 3, 1))
    with col2:
        end_date = st.date_input("Tugash", datetime(2026, 5, 13))
    
    st.subheader("🏘️ Tumanlar")
    districts = get_xorazm_districts()
    selected_districts = st.multiselect(
        "Tanlang:",
        list(districts.keys()),
        default=["Urganch", "Xiva", "Gurlan"]
    )
    
    st.subheader("🗺️ Vizualizatsiya")
    viz_type = st.radio(
        "Turi:",
        ["GEE Real NDVI", "Choropleth", "Issiqlik Xaritasi", "Markerlar"]
    )
    
    st.subheader("⚙️ Sozlamalar")
    st.checkbox("Legenda", value=True)
    st.checkbox("Koordinata tori", value=False)
    
    st.markdown("---")
    st.info("💡 NDVI: 0.1-0.95. Yuqori = sog'lom o'simlik.")

# =============================================================================
# ASOSIY QISM
# =============================================================================
st.markdown('<h1 class="main-header">🌾 Xorazm Viloyati NDVI Monitoring</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Sentinel-2 + Google Earth Engine</p>', unsafe_allow_html=True)

# Statistika
if selected_districts:
    all_data = []
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        all_data.append(df)
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_ndvi = combined_df['ndvi'].mean()
        st.metric("📊 O'rtacha", f"{avg_ndvi:.3f}")
    
    with col2:
        max_ndvi = combined_df['ndvi'].max()
        st.metric("🌿 Max", f"{max_ndvi:.3f}")
    
    with col3:
        min_ndvi = combined_df['ndvi'].min()
        st.metric("🍂 Min", f"{min_ndvi:.3f}")
    
    with col4:
        healthy = (combined_df['ndvi'] > 0.6).sum() / len(combined_df) * 100
        st.metric("✅ Sog'lom", f"{healthy:.1f}%")

# =============================================================================
# XARITA
# =============================================================================
st.markdown("---")
st.subheader("🗺️ Interaktiv NDVI Xaritasi")

m = folium.Map(location=[41.5, 60.6], zoom_start=9, tiles='CartoDB dark_matter')

# GEE Real NDVI
if viz_type == "GEE Real NDVI" and ee_ok:
    with st.spinner("🛰️ Sentinel-2 yuklanmoqda..."):
        ndvi_url = get_gee_ndvi_url(start_date, end_date)
        
        if ndvi_url:
            folium.TileLayer(
                tiles=ndvi_url,
                attr='Google Earth Engine | Sentinel-2',
                name='🌿 Real NDVI',
                overlay=True,
                control=True,
                opacity=0.9
            ).add_to(m)
            st.success("✅ Haqiqiy NDVI yuklandi!")
        else:
            st.warning("⚠️ NDVI yuklanmadi")

# Choropleth
elif viz_type == "Choropleth" and selected_districts:
    geojson_data = {"type": "FeatureCollection", "features": []}
    
    for name, info in districts.items():
        center = info["center"]
        offset = 0.15
        polygon = [
            [center[0] - offset, center[1] - offset],
            [center[0] - offset, center[1] + offset],
            [center[0] + offset, center[1] + offset],
            [center[0] + offset, center[1] - offset],
            [center[0] - offset, center[1] - offset]
        ]
        geojson_data["features"].append({
            "type": "Feature",
            "properties": {"name": name, "area_km2": info["area"]},
            "geometry": {"type": "Polygon", "coordinates": [polygon]}
        })
    
    ndvi_values = {}
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        ndvi_values[district] = df['ndvi'].iloc[-1]
    
    for feature in geojson_data['features']:
        name = feature['properties']['name']
        feature['properties']['ndvi'] = ndvi_values.get(name, 0)
    
    choropleth = folium.Choropleth(
        geo_data=geojson_data,
        name='NDVI Choropleth',
        data=pd.DataFrame([{"district": k, "ndvi": v} for k, v in ndvi_values.items()]),
        columns=['district', 'ndvi'],
        key_on='feature.properties.name',
        fill_color='YlGn',
        fill_opacity=0.7,
        line_opacity=0.4,
        legend_name='NDVI Qiymati',
        smooth_factor=0.5,
        highlight=True
    ).add_to(m)
    
    choropleth.geojson.add_child(
        folium.features.GeoJsonTooltip(
            fields=['name', 'ndvi', 'area_km2'],
            aliases=['🏘️ Tuman:', '🌿 NDVI:', '📏 Maydon (km²):'],
            localize=True,
            sticky=False,
            labels=True,
            style="""
                background-color: #F0EFEF;
                border: 2px solid black;
                border-radius: 3px;
                box-shadow: 3px;
                font-size: 13px;
            """
        )
    )

# Issiqlik Xaritasi
elif viz_type == "Issiqlik Xaritasi" and selected_districts:
    heat_data = []
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        center = districts[district]["center"]
        latest_ndvi = df['ndvi'].iloc[-1]
        for _ in range(20):
            lat_offset = np.random.normal(0, 0.05)
            lon_offset = np.random.normal(0, 0.05)
            heat_data.append([
                center[0] + lat_offset,
                center[1] + lon_offset,
                latest_ndvi * 100
            ])
    
    HeatMap(
        heat_data,
        radius=25,
        blur=15,
        max_zoom=10,
        gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}
    ).add_to(m)

# Markerlar
elif viz_type == "Markerlar" and selected_districts:
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        center = districts[district]["center"]
        latest_ndvi = df['ndvi'].iloc[-1]
        
        folium.CircleMarker(
            location=center,
            radius=20 + (latest_ndvi * 30),
            popup=f"<b>{district}</b><br>NDVI: {latest_ndvi:.3f}",
            tooltip=f"{district}: NDVI = {latest_ndvi:.3f}",
            color=get_ndvi_color(latest_ndvi),
            fill=True,
            fill_color=get_ndvi_color(latest_ndvi),
            fill_opacity=0.7
        ).add_to(m)

# Plaginlar
Draw(export=True).add_to(m)
MeasureControl(position='topleft', primary_length_unit='kilometers').add_to(m)
MiniMap().add_to(m)
Fullscreen().add_to(m)
folium.LayerControl().add_to(m)

# Xaritani ko'rsatish
col_map, col_info = st.columns([3, 1])

with col_map:
    map_data = st_folium(m, width=800, height=600)

with col_info:
    st.subheader("📋 Tuman Ma'lumotlari")
    
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        latest = df['ndvi'].iloc[-1]
        trend = df['ndvi'].iloc[-1] - df['ndvi'].iloc[-5] if len(df) > 5 else 0
        
        bg_color = '#e8f5e9' if latest > 0.6 else '#fff3e0' if latest > 0.4 else '#ffebee'
        
        st.markdown(f"""
        <div style="padding: 10px; border-radius: 10px; background-color: {bg_color}; margin-bottom: 10px;">
            <h4 style="margin: 0;">{district}</h4>
            <p style="margin: 5px 0; font-size: 1.2rem; font-weight: bold; color: {get_ndvi_color(latest)};">
                NDVI: {latest:.3f}
            </p>
            <p style="margin: 0; font-size: 0.9rem;">
                Trend: {'+' if trend > 0 else ''}{trend:.3f}
            </p>
        </div>
        """, unsafe_allow_html=True)

# =============================================================================
# GRAFIKLAR
# =============================================================================
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📈 Vaqt Qatorlari", "📊 Taqqoslash", "🎯 Tahlil", "💾 Ma'lumotlar"])

with tab1:
    st.subheader("NDVI Dinamikasi")
    
    if selected_districts:
        fig = go.Figure()
        
        for district in selected_districts:
            df = generate_ndvi_data(district, start_date, end_date)
            
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['ndvi'],
                mode='lines+markers',
                name=district,
                line=dict(width=3),
                marker=dict(size=6)
            ))
        
        fig.update_layout(
            title="NDVI O'zgarishlari",
            xaxis_title="Sana",
            yaxis_title="NDQI Qiymati",
            hovermode='x unified',
            template='plotly_white',
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis=dict(range=[0, 1])
        )
        
        fig.add_hrect(y0=0.75, y1=1.0, fillcolor="green", opacity=0.1, line_width=0, annotation_text="A'lo")
        fig.add_hrect(y0=0.5, y1=0.75, fillcolor="yellow", opacity=0.1, line_width=0, annotation_text="Yaxshi")
        fig.add_hrect(y0=0.25, y1=0.5, fillcolor="orange", opacity=0.1, line_width=0, annotation_text="O'rta")
        fig.add_hrect(y0=0, y1=0.25, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Yomon")
        
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Tumanlar Bo'yicha Taqqoslash")
    
    if selected_districts:
        comp_data = []
        for district in selected_districts:
            df = generate_ndvi_data(district, start_date, end_date)
            comp_data.append({
                "Tuman": district,
                "O'rtacha": df['ndvi'].mean(),
                "Maks": df['ndvi'].max(),
                "Min": df['ndvi'].min()
            })
        
        comp_df = pd.DataFrame(comp_data)
        
        col_chart, col_table = st.columns([2, 1])
        
        with col_chart:
            fig = px.bar(
                comp_df,
                x="Tuman",
                y="O'rtacha",
                color="O'rtacha",
                color_continuous_scale="YlGn",
                range_color=[0, 1],
                text="O'rtacha",
                title="O'rtacha NDVI"
            )
            fig.update_traces(texttemplate='%{text:.3f}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        
        with col_table:
            st.dataframe(
                comp_df.style.background_gradient(subset=["O'rtacha"], cmap="YlGn"),
                use_container_width=True,
                hide_index=True
            )

with tab3:
    st.subheader("Avtomat Tahlil")
    
    if selected_districts:
        for district in selected_districts:
            df = generate_ndvi_data(district, start_date, end_date)
            avg = df['ndvi'].mean()
            trend = df['ndvi'].iloc[-1] - df['ndvi'].iloc[0]
            
            if avg > 0.7:
                status = "A'lo holat"
                emoji = "🌟"
            elif avg > 0.5:
                status = "Yaxshi holat"
                emoji = "✅"
            elif avg > 0.3:
                status = "O'rtacha holat"
                emoji = "⚠️"
            else:
                status = "Yomon holat"
                emoji = "🚨"
            
            st.markdown(f"""
            **{district}:** {emoji} {status}
            - O'rtacha NDVI: **{avg:.3f}**
            - Trend: **{'O\'sish' if trend > 0 else 'Pasayish'}** ({abs(trend):.3f})
            - Tavsiya: {'Optimallashtirish' if avg > 0.6 else 'Sug\'orishni oshirish' if avg < 0.4 else 'Saqlash'}
            """)
            st.markdown("---")

with tab4:
    st.subheader("Ma'lumotlarni Yuklab Olish")
    
    if selected_districts:
        export = pd.concat([
            generate_ndvi_data(d, start_date, end_date) for d in selected_districts
        ], ignore_index=True)
        
        st.dataframe(export, use_container_width=True, height=400)
        
        csv = export.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 CSV Yuklab Olish",
            csv,
            f"xorazm_ndvi_{start_date}_{end_date}.csv",
            "text/csv"
        )

# =============================================================================
# PASTGI QISM
# =============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🛰️ <b>Sentinel-2 MSI</b> | ESA Copernicus Programme</p>
    <p>🌾 Xorazm Viloyati NDVI Monitoring</p>
    <p style="font-size: 0.8rem;">© 2026</p>
</div>
""", unsafe_allow_html=True)
'''

# Save to output
output_path = "/mnt/agents/output/app.py"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(app_code)

print(f"✅ app.py saved to: {output_path}")
print(f"📏 File size: {len(app_code)} characters")
