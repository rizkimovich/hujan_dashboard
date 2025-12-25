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

# --- KONFIGURASI HALAMAN ---
st.set_page_config (layout="wide", page_title="Analisis Curah Hujan")
st.markdown("""
    <style>
    /* Mengurangi ruang kosong di bagian atas */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
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
    
    # 1. Inisialisasi Peta
    m = folium.Map(location=[-4.8666, 105.0568], zoom_start=8)
    
    # 2. TAMBAHKAN SCRIPT FULLSCREEN DI SINI
    from folium.plugins import Fullscreen, Geocoder # Pastikan sudah di-import
    
    Fullscreen(
        position='topright', # Posisi tombol di pojok kanan atas
        title='Perbesar Layar', 
        title_cancel='Keluar', 
        force_separate_button=True
    ).add_to(m)

    # 3. Tambahkan fitur lainnya (seperti Geocoder atau Popup)
    Geocoder().add_to(m)
    m.add_child(folium.LatLngPopup()) 

    # 4. Tampilkan peta ke Streamlit
    map_output = st_folium(m, height=600, use_container_width=True)

with col2:
    st.subheader("Analisis Lokasi")
    
    if map_output['last_clicked']:
        click_lat = map_output['last_clicked']['lat']
        click_lng = map_output['last_clicked']['lng']
        
        st.info(f"📍 Koordinat: {click_lat:.4f}, {click_lng:.4f}")
        
        # Ambil data
        df_rain = get_rainfall_data(click_lng, click_lat)
        
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
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Lihat Data Tabel"):
            st.dataframe(df_rain)
            
    else:

        st.warning("👈 Klik peta untuk analisis.")

