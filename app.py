import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, Draw, MeasureControl, MiniMap, Fullscreen
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import requests
import json
from branca.colormap import linear, StepColormap
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .info-box {
        background-color: #f0f8ff;
        padding: 1rem;
        border-left: 5px solid #1f4e79;
        border-radius: 5px;
        margin: 1rem 0;
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
    """Xorazm viloyati tumanlari geoJSON ma'lumotlari"""
    # Xorazm viloyati tumanlari koordinatalari (taxminiy aniq koordinatalar)
    districts = {
        "Urganch": {"center": [41.55, 60.63], "area": 450, "color": "#FF6B6B"},
        "Xiva": {"center": [41.38, 60.37], "area": 380, "color": "#4ECDC4"},
        "Gurlan": {"center": [41.85, 60.40], "area": 320, "color": "#45B7D1"},
        "Shovot": {"center": [41.65, 60.30], "area": 290, "color": "#96CEB4"},
        "Yangiariq": {"center": [41.30, 60.55], "area": 410, "color": "#FFEAA7"},
        "Yangibozor": {"center": [41.73, 60.55], "area": 350, "color": "#DDA0DD"},
        "Xonqa": {"center": [41.47, 60.78], "area": 270, "color": "#98D8C8"},
        "Bog'ot": {"center": [41.35, 60.85], "area": 310, "color": "#F7DC6F"},
        "Tuproqqal'a": {"center": [41.75, 61.15], "area": 520, "color": "#BB8FCE"},
        "Qo'rg'ontepa": {"center": [41.25, 61.30], "area": 440, "color": #85C1E9"},
    }
    return districts

@st.cache_data(ttl=1800)
def generate_ndvi_data(district, date_start, date_end):
    """Sentinel-2 dan olingan NDVI ma'lumotlarini simulyatsiya qilish"""
    np.random.seed(42)
    dates = pd.date_range(start=date_start, end=date_end, freq='5D')
    
    # Xorazm viloyati uchun realistik NDVI qiymatlari (0.1 dan 0.85 gacha)
    base_ndvi = {
        "Urganch": 0.45, "Xiva": 0.52, "Gurlan": 0.38, "Shovot": 0.41,
        "Yangiariq": 0.48, "Yangibozor": 0.43, "Xonqa": 0.50, "Bog'ot": 0.35,
        "Tuproqqal'a": 0.40, "Qo'rg'ontepa": 0.33
    }
    
    data = []
    for date in dates:
        # Mavsumiy o'zgarishlar (bahor - yuqori, yoz - o'rta, kuz - pasayish)
        month = date.month
        if month in [3, 4, 5]:  # Bahor
            seasonal_factor = 1.3
        elif month in [6, 7, 8]:  # Yoz
            seasonal_factor = 0.9
        elif month in [9, 10]:  # Kuz
            seasonal_factor = 0.7
        else:  # Qish
            seasonal_factor = 0.4
            
        ndvi = base_ndvi[district] * seasonal_factor + np.random.normal(0, 0.05)
        ndvi = max(0.1, min(0.95, ndvi))  # 0.1 va 0.95 orasida cheklash
        
        # Sug'orish ta'siri (paxta va g'allalar uchun farq)
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

def create_xorazm_geojson():
    """Xorazm viloyati tumanlari uchun GeoJSON yaratish"""
    districts = get_xorazm_districts()
    
    features = []
    for name, info in districts.items():
        # Har bir tuman uchun polygon yaratish (taxminiy chegaralar)
        center = info["center"]
        offset = 0.15
        
        polygon = [
            [center[0] - offset, center[1] - offset],
            [center[0] - offset, center[1] + offset],
            [center[0] + offset, center[1] + offset],
            [center[0] + offset, center[1] - offset],
            [center[0] - offset, center[1] - offset]
        ]
        
        features.append({
            "type": "Feature",
            "properties": {
                "name": name,
                "area_km2": info["area"],
                "center_lat": center[0],
                "center_lon": center[1]
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [polygon]
            }
        })
    
    return {"type": "FeatureCollection", "features": features}

def get_ndvi_color(ndvi):
    """NDVI qiymatiga qarab rang qaytarish"""
    if ndvi < 0.2:
        return "#8B0000"  # Qizil - yomon
    elif ndvi < 0.4:
        return "#FF4500"  # To'q qizil - o'rta past
    elif ndvi < 0.6:
        return "#FFD700"  # Sariq - o'rta
    elif ndvi < 0.75:
        return "#7CFC00"  # Yashil - yaxshi
    else:
        return "#006400"  # To'q yashil - a'lo

# =============================================================================
# SIDEBAR - BOSHQARUV PANELI
# =============================================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Flag_of_Uzbekistan.svg/1200px-Flag_of_Uzbekistan.svg.png", width=100)
    st.title("🛰️ Boshqaruv Paneli")
    
    st.markdown("---")
    
    # Vaqt oralig'i tanlash
    st.subheader("📅 Vaqt Oralig'i")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Boshlanish", datetime(2026, 3, 1))
    with col2:
        end_date = st.date_input("Tugash", datetime(2026, 5, 13))
    
    # Tuman tanlash
    st.subheader("🏘️ Tuman Tanlash")
    districts = get_xorazm_districts()
    selected_districts = st.multiselect(
        "Tumanlarni tanlang:",
        list(districts.keys()),
        default=["Urganch", "Xiva", "Gurlan"]
    )
    
    # Xarita qatlami
    st.subheader("🗺️ Xarita Qatlami")
    map_style = st.selectbox(
        "Xarita uslubi:",
        ["OpenStreetMap", "Satellite (Esri)", "Terrain", "CartoDB Positron"],
        index=1
    )
    
    # NDVI vizualizatsiya turi
    st.subheader("📊 Vizualizatsiya")
    viz_type = st.radio(
        "Ko'rinish turi:",
        ["Choropleth", "Issiqlik Xaritasi", "Markerlar", "3D Bar"]
    )
    
    # Qo'shimcha sozlamalar
    st.subheader("⚙️ Sozlamalar")
    show_legend = st.checkbox("Legenda ko'rsatish", value=True)
    show_grid = st.checkbox("Koordinata to'rini ko'rsatish", value=False)
    auto_refresh = st.checkbox("Avto-yangilash (5 daqiqa)", value=False)
    
    st.markdown("---")
    st.info("💡 **Maslahat:** NDVI qiymatlari 0.1 dan 0.95 gacha. Yuqori qiymat = sog'lom o'simlik.")

# =============================================================================
# ASOSIY SARVLAMA
# =============================================================================
st.markdown('<h1 class="main-header">🌾 Xorazm Viloyati NDVI Monitoring Tizimi</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Sentinel-2 Sun\'iy Yo\'ldosh Ma\'lumotlari Asosida</p>', unsafe_allow_html=True)

# Yuqori statistika kartalari
if selected_districts:
    all_data = []
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        all_data.append(df)
    
    combined_df = pd.concat(all_data, ignore_index=True)
    latest_data = combined_df.groupby('district')['ndvi'].last().reset_index()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_ndvi = combined_df['ndvi'].mean()
        st.metric(
            label="📊 O'rtacha NDVI",
            value=f"{avg_ndvi:.3f}",
            delta=f"{((avg_ndvi - 0.45) / 0.45 * 100):.1f}%" if avg_ndvi != 0.45 else None
        )
    
    with col2:
        max_ndvi = combined_df['ndvi'].max()
        max_district = combined_df[combined_df['ndvi'] == max_ndvi]['district'].iloc[0]
        st.metric(
            label="🌿 Maksimal NDVI",
            value=f"{max_ndvi:.3f}",
            help=f"{max_district} tumanida"
        )
    
    with col3:
        min_ndvi = combined_df['ndvi'].min()
        min_district = combined_df[combined_df['ndvi'] == min_ndvi]['district'].iloc[0]
        st.metric(
            label="🍂 Minimal NDVI",
            value=f"{min_ndvi:.3f}",
            help=f"{min_district} tumanida"
        )
    
    with col4:
        healthy_area = (combined_df['ndvi'] > 0.6).sum() / len(combined_df) * 100
        st.metric(
            label="✅ Sog'lom Maydon",
            value=f"{healthy_area:.1f}%",
            help="NDVI > 0.6"
        )

# =============================================================================
# ASOSIY XARITA
# =============================================================================
st.markdown("---")
st.subheader("🗺️ Interaktiv NDVI Xaritasi")

# Xarita yaratish
map_tiles = {
    "OpenStreetMap": "OpenStreetMap",
    "Satellite (Esri)": "Esri WorldImagery",
    "Terrain": "Stamen Terrain",
    "CartoDB Positron": "CartoDB positron"
}

m = folium.Map(
    location=[41.5, 60.6],
    zoom_start=9,
    tiles=map_tiles.get(map_style, "OpenStreetMap"),
    control_scale=True
)

# Qo'shimcha xarita qatlami (satellite uchun)
if map_style == "Satellite (Esri)":
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)

# Choropleth qatlami
if viz_type == "Choropleth" and selected_districts:
    geojson_data = create_xorazm_geojson()
    
    # So'nggi NDVI qiymatlarini olish
    ndvi_values = {}
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        ndvi_values[district] = df['ndvi'].iloc[-1]
    
    # GeoJSON ga NDVI qiymatlarini qo'shish
    for feature in geojson_data['features']:
        name = feature['properties']['name']
        feature['properties']['ndvi'] = ndvi_values.get(name, 0)
    
    # Choropleth
    choropleth = folium.Choropleth(
        geo_data=geojson_data,
        name='NDVI Choropleth',
        data=pd.DataFrame([
            {"district": k, "ndvi": v} for k, v in ndvi_values.items()
        ]),
        columns=['district', 'ndvi'],
        key_on='feature.properties.name',
        fill_color='YlGn',
        fill_opacity=0.7,
        line_opacity=0.4,
        legend_name='NDVI Qiymati',
        smooth_factor=0.5,
        highlight=True
    ).add_to(m)
    
    # Tooltip qo'shish
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

elif viz_type == "Issiqlik Xaritasi":
    # HeatMap uchun ma'lumotlar
    heat_data = []
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        center = districts[district]["center"]
        latest_ndvi = df['ndvi'].iloc[-1]
        # Ko'proq nuqtalar yaratish (simulyatsiya)
        for _ in range(20):
            lat_offset = np.random.normal(0, 0.05)
            lon_offset = np.random.normal(0, 0.05)
            heat_data.append([
                center[0] + lat_offset,
                center[1] + lon_offset,
                latest_ndvi * 100  # Intensivlik
            ])
    
    HeatMap(
        heat_data,
        radius=25,
        blur=15,
        max_zoom=10,
        gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}
    ).add_to(m)

elif viz_type == "Markerlar":
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        center = districts[district]["center"]
        latest_ndvi = df['ndvi'].iloc[-1]
        
        folium.CircleMarker(
            location=center,
            radius=20 + (latest_ndvi * 30),
            popup=f"""
                <b>{district}</b><br>
                NDVI: {latest_ndvi:.3f}<br>
                Sana: {end_date}<br>
                <hr>
                {'✅ Sog\'lom' if latest_ndvi > 0.6 else '⚠️ O\'rta' if latest_ndvi > 0.4 else '❌ Yomon'}
            """,
            tooltip=f"{district}: NDVI = {latest_ndvi:.3f}",
            color=get_ndvi_color(latest_ndvi),
            fill=True,
            fill_color=get_ndvi_color(latest_ndvi),
            fill_opacity=0.7
        ).add_to(m)

# Qo'shimcha plaginlar
Draw(export=True).add_to(m)
MeasureControl(position='topleft', primary_length_unit='kilometers').add_to(m)
MiniMap().add_to(m)
Fullscreen().add_to(m)

# Layer control
folium.LayerControl().add_to(m)

# Xaritani ko'rsatish
col_map, col_info = st.columns([3, 1])

with col_map:
    map_data = st_folium(m, width=800, height=600, returned_objects=["last_active_drawing", "bounds"])
    
    # Tanlangan hudud ma'lumotlari
    if map_data['last_active_drawing']:
        st.success(f"📍 Tanlangan hudud: {map_data['last_active_drawing']}")

with col_info:
    st.subheader("📋 Tuman Ma'lumotlari")
    
    for district in selected_districts:
        df = generate_ndvi_data(district, start_date, end_date)
        latest = df['ndvi'].iloc[-1]
        trend = df['ndvi'].iloc[-1] - df['ndvi'].iloc[-5] if len(df) > 5 else 0
        
        with st.container():
            st.markdown(f"""
            <div style="padding: 10px; border-radius: 10px; background-color: {'#e8f5e9' if latest > 0.6 else '#fff3e0' if latest > 0.4 else '#ffebee'}; margin-bottom: 10px;">
                <h4 style="margin: 0;">{district}</h4>
                <p style="margin: 5px 0; font-size: 1.2rem; font-weight: bold; color: {get_ndvi_color(latest)};">
                    NDVI: {latest:.3f}
                </p>
                <p style="margin: 0; font-size: 0.9rem;">
                    📈 Trend: {'+' if trend > 0 else ''}{trend:.3f}
                </p>
            </div>
            """, unsafe_allow_html=True)

# =============================================================================
# GRAFIKLAR VA Tahlillar
# =============================================================================
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["📈 Vaqt Qatorlari", "📊 Taqqoslash", "🎯 Tahlil", "💾 Ma'lumotlar"])

with tab1:
    st.subheader("NDVI Dinamikasi (Vaqt bo'yicha)")
    
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
                marker=dict(size=6),
                hovertemplate='<b>%{fullData.name}</b><br>Sana: %{x}<br>NDVI: %{y:.3f}<extra></extra>'
            ))
        
        fig.update_layout(
            title="NDVI O'zgarishlari",
            xaxis_title="Sana",
            yaxis_title="NDVI Qiymati",
            hovermode='x unified',
            template='plotly_white',
            height=500,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            yaxis=dict(range=[0, 1])
        )
        
        # Mavsumiy oralig'lar
        fig.add_hrect(y0=0.75, y1=1.0, line_width=0, fillcolor="green", opacity=0.1, annotation_text="A'lo")
        fig.add_hrect(y0=0.5, y1=0.75, line_width=0, fillcolor="yellow", opacity=0.1, annotation_text="Yaxshi")
        fig.add_hrect(y0=0.25, y1=0.5, line_width=0, fillcolor="orange", opacity=0.1, annotation_text="O'rta")
        fig.add_hrect(y0=0, y1=0.25, line_width=0, fillcolor="red", opacity=0.1, annotation_text="Yomon")
        
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Tumanlar Bo'yicha Taqqoslash")
    
    if selected_districts:
        comparison_data = []
        for district in selected_districts:
            df = generate_ndvi_data(district, start_date, end_date)
            comparison_data.append({
                "Tuman": district,
                "O'rtacha NDVI": df['ndvi'].mean(),
                "Maksimal": df['ndvi'].max(),
                "Minimal": df['ndvi'].min(),
                "St.Kopma": df['ndvi'].std()
            })
        
        comp_df = pd.DataFrame(comparison_data)
        
        col_chart, col_table = st.columns([2, 1])
        
        with col_chart:
            fig = px.bar(
                comp_df,
                x="Tuman",
                y="O'rtacha NDVI",
                color="O'rtacha NDVI",
                color_continuous_scale="YlGn",
                range_color=[0, 1],
                text="O'rtacha NDVI",
                title="O'rtacha NDVI Bo'yicha Taqqoslash"
            )
            fig.update_traces(texttemplate='%{text:.3f}', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col_table:
            st.dataframe(
                comp_df.style.background_gradient(subset=["O'rtacha NDVI"], cmap="YlGn"),
                use_container_width=True,
                hide_index=True
            )

with tab3:
    st.subheader("🤖 Avtomat Tahlil")
    
    if selected_districts:
        for district in selected_districts:
            df = generate_ndvi_data(district, start_date, end_date)
            avg = df['ndvi'].mean()
            trend = df['ndvi'].iloc[-1] - df['ndvi'].iloc[0]
            
            col_icon, col_text = st.columns([1, 4])
            
            with col_icon:
                if avg > 0.7:
                    st.markdown("## 🌟")
                elif avg > 0.5:
                    st.markdown("## ✅")
                elif avg > 0.3:
                    st.markdown("## ⚠️")
                else:
                    st.markdown("## 🚨")
            
            with col_text:
                status = "A'lo holat" if avg > 0.7 else "Yaxshi holat" if avg > 0.5 else "O'rtacha holat" if avg > 0.3 else "Yomon holat"
                st.markdown(f"""
                **{district}:** {status}
                - O'rtacha NDVI: **{avg:.3f}**
                - Umumiy trend: **{'O'sish 📈' if trend > 0 else 'Pasayish 📉'}** ({abs(trend):.3f})
                - Tavsiya: {'Sug\'orishni optimallashtirish' if avg > 0.6 else 'Sug\'orishni oshirish' if avg < 0.4 else 'Joriy holatni saqlash'}
                """)
            
            st.markdown("---")

with tab4:
    st.subheader("💾 Ma'lumotlarni Yuklab Olish")
    
    if selected_districts:
        # Barcha ma'lumotlarni birlashtirish
        all_export = pd.concat([
            generate_ndvi_data(d, start_date, end_date) for d in selected_districts
        ], ignore_index=True)
        
        st.dataframe(all_export, use_container_width=True, height=400)
        
        # CSV yuklab olish
        csv = all_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 CSV sifatida yuklab olish",
            data=csv,
            file_name=f"xorazm_ndvi_{start_date}_{end_date}.csv",
            mime="text/csv"
        )
        
        # JSON yuklab olish
        json_data = all_export.to_json(orient='records', force_ascii=False)
        st.download_button(
            label="📥 JSON sifatida yuklab olish",
            data=json_data,
            file_name=f"xorazm_ndvi_{start_date}_{end_date}.json",
            mime="application/json"
        )

# =============================================================================
# PASTGI QISM
# =============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🛰️ Ma'lumotlar manbai: <b>Sentinel-2 MSI</b> | ESA Copernicus Programme</p>
    <p>🌾 Xorazm Viloyati Qishloq Xo'jaligi va Sug'orish Tizimlari Monitoringi</p>
    <p style="font-size: 0.8rem;">© 2026 | So'nggi yangilanish: {}</p>
</div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)
