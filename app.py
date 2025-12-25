import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Geocoder
import pandas as pd
import plotly.express as px
import rasterio
import os
import numpy as np
from folium.plugins import Geocoder, Fullscreen  # <--- Tambahkan Fullscreen di sini
from geopy.geocoders import Nominatim  # Import baru
import geopandas as gpd
from shapely.geometry import Point
from streamlit_js_eval import get_geolocation
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
# --- KONFIGURASI HALAMAN ---
st.set_page_config (layout="wide", page_title="Analisis Curah Hujan")

st.markdown("""
    <style>
    div.stButton > button:first-child {
        width: 100%;
        height: 50px;
        font-weight: bold;
        background-color: #007bff;
        color: white;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)
# --- OPTIMASI TAMPILAN MOBILE ---
st.markdown("""
    <style>
    /* 1. Atur Padding Halaman agar lebih luas di HP */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
    }
    
    /* 2. Responsif Peta: Desktop 600px, HP 350px */
    iframe[title="streamlit_folium.st_folium"] {
        width: 100% !important;
    }
    @media only screen and (max-width: 768px) {
        iframe[title="streamlit_folium.st_folium"] {
            height: 350px !important;
        }
    }
    
    /* 3. Menghilangkan elemen footer bawaan Streamlit agar bersih */
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)
st.markdown("""
    <style>
    /* Tampilan Desktop (Layar Besar) */
    iframe[title="streamlit_folium.st_folium"] {
        height: 600px;
    }

    /* Tampilan HP (Layar Kecil - max lebar 768px) */
    @media only screen and (max-width: 768px) {
        iframe[title="streamlit_folium.st_folium"] {
            height: 350px !important; /* Peta jadi lebih pendek di HP */
        }
    }
    </style>
    """, unsafe_allow_html=True)
# --- CSS HACK UNTUK MENGUBAH KURSOR ---
st.markdown("""
    <style>
    /* Mengubah kursor saat berada di area peta */
    .leaflet-grab {
        cursor: default !important;
    }
    
    /* Mengubah kursor saat "grabbing" (sedang menahan klik untuk geser) */
    .leaflet-dragging .leaflet-grab {
        cursor: default !important; 
    }

    /* Opsional: Mengubah kursor saat hover di atas marker/fitur interaktif */
    .leaflet-interactive {
        cursor: default !important;
    }
    </style>
    """, unsafe_allow_html=True)
# --- JUDUL & HEADER ---
st.title("🌧️ Dashboard Monitoring Curah Hujan")
st.markdown("""
**Instruksi:** 1. Gunakan fitur pencarian untuk menemukan lokasi.
2. **Klik di mana saja pada peta** untuk melihat analisis grafik curah hujan.
""")

# --- SETUP PATH OTOMATIS (RELATIVE PATH) ---
# Pastikan Anda meletakkan file .tif di folder bernama 'data' di sebelah script ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "data") 

# --- FUNGSI UTAMA ---
# --- LOAD DATA SHP SEKALI SAJA (Di luar fungsi agar cepat) ---
# Gunakan cache agar aplikasi tidak lambat saat loading file SHP yang berat
@st.cache_data
def load_shp_data():
    shp_path = "data/shp/Administrasi_Desa.shp" # Sesuaikan dengan path file Anda
    gdf = gpd.read_file(shp_path)
    # Pastikan koordinat SHP adalah WGS84 (Lat/Lon)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf

# Panggil fungsi load
gdf_indo = load_shp_data()

def get_location_details_shp(lat, lon):
    try:
        # 1. Buat titik berdasarkan koordinat klik
        pnt = Point(lon, lat)
        
        # 2. Cek titik tersebut masuk ke poligon mana
        # 'within' mengecek apakah titik ada di dalam poligon
        match = gdf_indo[gdf_indo.contains(pnt)]
        
        if not match.empty:
            # Ambil baris pertama yang cocok
            row = match.iloc[0]
            
            # Sesuaikan nama kolom di bawah dengan header file SHP dari BIG
            # Biasanya BIG menggunakan nama: NAMOBJ (Desa), WADMKC (Kecamatan), WADMKK (Kabupaten)
            desa = row.get('DESA', 'Tidak Terdata')
            kecamatan = row.get('KECAMATAN', 'Tidak Terdata')
            kabupaten = row.get('KAB_KOTA', 'Tidak Terdata')
            
            return f"{desa}, Kec. {kecamatan}, {kabupaten}"
        else:
            return "Koordinat di luar wilayah administrasi"
    except Exception as e:
        return f"Kesalahan membaca SHP: {e}"
def get_rainfall_data(lon, lat):
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    real_data_normal = []
    real_data_current = []
    
    # Cek folder data
    if not os.path.exists(DATA_FOLDER):
        st.error(f"Folder data tidak ditemukan di: {DATA_FOLDER}")
        return pd.DataFrame({"Bulan": months, "Normal": [None]*12, "Tahun Berjalan": [None]*12})

    for i in range(1, 13):
        # Pastikan nama file sesuai (perhatikan penggunaan 's' atau tidak)
        file_n = os.path.join(DATA_FOLDER, f"normal_months_{i}.tif")
        file_c = os.path.join(DATA_FOLDER, f"current_months_{i}.tif")

        # --- Helper Function Membaca Nilai ---
        def read_val(filepath, x, y):
            # 1. Jika file tidak ada, kembalikan None (bukan 0)
            if not os.path.exists(filepath):
                return None 
            
            try:
                with rasterio.open(filepath) as src:
                    # Logika transformasi koordinat sebaiknya ditambahkan disini jika perlu (seperti jawaban sebelumnya)
                    try:
                        row, col = src.index(x, y)
                    except:
                        return None # Jika koordinat di luar bounds

                    if 0 <= row < src.height and 0 <= col < src.width:
                        data = src.read(1)
                        val = data[row, col]
                        
                        # Anggap nilai negatif (misal -9999) sebagai NoData -> None
                        if val < 0: 
                            return None
                        
                        # Kembalikan nilai asli (termasuk jika nilainya 0 curah hujan)
                        return float(val)
                    
                    return None # Di luar area gambar
            except Exception as e:
                return None # Jika error baca file

        real_data_normal.append(read_val(file_n, lon, lat))
        real_data_current.append(read_val(file_c, lon, lat))

    return pd.DataFrame({
        "Bulan": months,
        "Normal": real_data_normal,
        "Tahun Berjalan": real_data_current
    })

# --- LAYOUT APLIKASI ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Peta Interaktif")
    
    # 1. Inisialisasi Session State jika belum ada
    if 'center' not in st.session_state:
        st.session_state['center'] = [-4.8666, 105.0568] # Default Lampung
    if 'zoom' not in st.session_state:
        st.session_state['zoom'] = 8
    if 'user_location' not in st.session_state:
        st.session_state['user_location'] = None

    # 2. Tombol GPS (Menggunakan streamlit-js-eval atau streamlit-geolocation)
    if st.button("📍 Temukan Lokasi Saya"):
        loc = get_geolocation()
        if loc:
            lat = loc['coords']['latitude']
            lon = loc['coords']['longitude']
            # Simpan koordinat GPS secara khusus
            st.session_state['user_location'] = [lat, lon]
            st.session_state['center'] = [lat, lon]
            st.session_state['zoom'] = 15
            st.rerun()
# 2. LETAKKAN DI SINI UNTUK CEK DATA
    if 'user_location' in st.session_state:
        st.write(f"🔍 Status GPS: **{st.session_state['user_location']}**")
    else:
        st.write("🔍 Status GPS: **Belum terdeteksi**")
    # 3. Buat Objek Peta
    m = folium.Map(
        location=st.session_state['center'], 
        zoom_start=st.session_state['zoom']
    )

    # 4. TAMBAHKAN MARKER GPS (Jika data ada)
    if st.session_state['user_location']:
        folium.Marker(
            st.session_state['user_location'],
            popup="Lokasi Anda Saat Ini",
            icon=folium.Icon(color='red', icon='user', prefix='fa') # Ikon orang warna merah
        ).add_to(m)
        
        # Tambahkan lingkaran biru transparan di sekitar GPS (Akurasi)
        folium.Circle(
            radius=100,
            location=st.session_state['user_location'],
            color='blue',
            fill=True,
            fill_opacity=0.2
        ).add_to(m)

    # Tambahkan fitur peta lainnya (Geocoder, dll)
    m.add_child(folium.LatLngPopup())
    
    # Tampilkan Peta
    map_output = st_folium(m, height=600, use_container_width=True)
    
 


with col2:
    st.subheader("Analisis Lokasi")
    
    if map_output['last_clicked']:
        click_lat = map_output['last_clicked']['lat']
        click_lng = map_output['last_clicked']['lng']
        # --- AMBIL INFORMASI ALAMAT ---
        with st.spinner("Mencari nama daerah..."):
            alamat_lengkap = get_location_details_shp(click_lat, click_lng)
        
        # Tampilkan alamat di dashboard
        st.success(f"📍 **Lokasi:** {alamat_lengkap}")
        st.caption(f"Koordinat: {click_lat:.4f}, {click_lng:.4f}")
        
        st.info(f"📍 Koordinat: {click_lat:.4f}, {click_lng:.4f}")
        
        # Ambil data
        df_rain = get_rainfall_data(click_lng, click_lat)
        # Update Judul Grafik dengan Alamat
        fig = px.line(df_rain, x="Bulan", y=["Normal", "Tahun Berjalan"],
                      markers=True,
                      title=f"Tren Curah Hujan<br><sup>{alamat_lengkap}</sup>",
                      color_discrete_map={"Normal": "gray", "Tahun Berjalan": "blue"})
        
        # Plotly
        fig = px.line(df_rain, x="Bulan", y=["Normal", "Tahun Berjalan"],
                      markers=True,
                      title="Grafik Curah Hujan (mm)",
                      color_discrete_map={"Normal": "gray", "Tahun Berjalan": "blue"})
       # 3. LETAKKAN DI SINI (Konfigurasi Tampilan)
        fig.update_layout(
            legend=dict(
                orientation="h",   # Horizontal (mendatar)
                yanchor="bottom",
                y=1.1,             # Taruh sedikit di atas grafik
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=20, r=20, t=40, b=20), # Margin tipis agar pas di layar HP
            height=400 
        )
        
        # 4. Tampilkan ke Streamlit
        st.plotly_chart(fig, use_container_width=True)
        
        # with st.expander("Lihat Data Tabel"):
           # st.dataframe(df_rain)
        

            
    else:

        st.warning("👈 Klik peta untuk analisis.")































