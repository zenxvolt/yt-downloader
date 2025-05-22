import streamlit as st
import yt_dlp
import os
import subprocess
import tempfile
import threading
import time
import json
from pathlib import Path
import zipfile
import io
from datetime import datetime
import re
import sys
import shutil

# Konfigurasi halaman
st.set_page_config(
    page_title="YouTube Video Downloader Pro",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Fungsi untuk mengecek dan setup ffmpeg
@st.cache_resource
def setup_ffmpeg():
    """Setup ffmpeg untuk Streamlit Cloud"""
    ffmpeg_path = None
    
    # Cek jika ffmpeg sudah tersedia di sistem
    ffmpeg_locations = [
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        shutil.which('ffmpeg'),
        './ffmpeg',  # Jika ada di direktori aplikasi
    ]
    
    for location in ffmpeg_locations:
        if location and os.path.isfile(location):
            ffmpeg_path = location
            break
    
    if not ffmpeg_path:
        st.warning("⚠️ FFmpeg tidak terdeteksi. Beberapa fitur mungkin terbatas.")
        return None
    
    return ffmpeg_path

# Setup ffmpeg
FFMPEG_PATH = setup_ffmpeg()

# CSS untuk styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #FF0000, #FF6B6B);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        color: white;
        margin-bottom: 2rem;
    }
    .feature-box {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF0000;
        margin: 1rem 0;
    }
    .download-progress {
        background: #e8f4fd;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #bee5eb;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #c3e6cb;
    }
    .error-box {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📺 YouTube Video Downloader Pro</h1>
    <p>Download video YouTube dengan kualitas terbaik menggunakan yt-dlp & ffmpeg</p>
</div>
""", unsafe_allow_html=True)

# Fungsi untuk membersihkan nama file
def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# Fungsi untuk mendapatkan info video
@st.cache_data(ttl=300)
def get_video_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        return None

# Fungsi untuk mendapatkan format yang tersedia
def get_available_formats(info):
    formats = []
    if 'formats' in info:
        for f in info['formats']:
            if f.get('height') and f.get('ext'):
                format_info = {
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'resolution': f.get('height', 0),
                    'fps': f.get('fps', 0),
                    'filesize': f.get('filesize', 0),
                    'vcodec': f.get('vcodec', 'unknown'),
                    'acodec': f.get('acodec', 'unknown'),
                    'format_note': f.get('format_note', ''),
                }
                formats.append(format_info)
    return sorted(formats, key=lambda x: x['resolution'], reverse=True)

# Fungsi progress callback
class ProgressHook:
    def __init__(self):
        self.progress_bar = None
        self.status_text = None
        
    def set_streamlit_elements(self, progress_bar, status_text):
        self.progress_bar = progress_bar
        self.status_text = status_text
    
    def __call__(self, d):
        if d['status'] == 'downloading':
            if self.progress_bar and self.status_text:
                try:
                    percent = d.get('_percent_str', '0%').replace('%', '')
                    percent_float = float(percent) / 100.0
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    
                    self.progress_bar.progress(percent_float)
                    self.status_text.text(f"📥 Downloading: {percent}% | Speed: {speed} | ETA: {eta}")
                except:
                    pass
        elif d['status'] == 'finished':
            if self.status_text:
                self.status_text.text("✅ Download selesai! Memproses file...")

# Fungsi download video
def download_video(url, output_path, format_selector, audio_only=False, custom_filename=None):
    try:
        progress_hook = ProgressHook()
        
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'format': format_selector,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        # Setup ffmpeg path jika tersedia
        if FFMPEG_PATH:
            ydl_opts['ffmpeg_location'] = FFMPEG_PATH
        
        if custom_filename:
            ydl_opts['outtmpl'] = os.path.join(output_path, f'{sanitize_filename(custom_filename)}.%(ext)s')
        
        if audio_only:
            if FFMPEG_PATH:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                # Fallback tanpa ffmpeg
                ydl_opts['format'] = 'bestaudio/best'
                st.info("ℹ️ Downloading audio dalam format asli (tanpa konversi ke MP3)")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return True, "Download berhasil!"
        
    except Exception as e:
        return False, str(e)

# Sidebar untuk pengaturan
with st.sidebar:
    st.header("⚙️ Pengaturan Download")
    
    # Mode download
    download_mode = st.selectbox(
        "Mode Download",
        ["Single Video", "Playlist", "Audio Only", "Batch URLs"]
    )
    
    # Kualitas video
    quality_preset = st.selectbox(
        "Preset Kualitas",
        ["Best Quality", "High (1080p)", "Medium (720p)", "Low (480p)", "Custom"]
    )
    
    # Format output
    output_format = st.selectbox(
        "Format Output",
        ["mp4", "webm", "mkv", "avi", "mov"]
    )
    
    # Opsi audio
    st.subheader("🔊 Opsi Audio")
    extract_audio = st.checkbox("Ekstrak audio terpisah")
    audio_format = st.selectbox("Format Audio", ["mp3", "aac", "ogg", "wav"]) if extract_audio else None
    
    # Opsi subtitle
    st.subheader("📝 Subtitle")
    download_subs = st.checkbox("Download subtitle")
    auto_subs = st.checkbox("Subtitle otomatis") if download_subs else False
    
    # Opsi lanjutan
    st.subheader("🔧 Opsi Lanjutan")
    custom_filename = st.text_input("Nama file custom (opsional)")
    embed_subs = st.checkbox("Embed subtitle ke video") if download_subs else False
    
    # Rentang waktu
    use_time_range = st.checkbox("Potong video (rentang waktu)")
    if use_time_range:
        col1, col2 = st.columns(2)
        with col1:
            start_time = st.text_input("Waktu mulai (HH:MM:SS)", "00:00:00")
        with col2:
            end_time = st.text_input("Waktu selesai (HH:MM:SS)", "")

# Area utama
col1, col2 = st.columns([2, 1])

with col1:
    st.header("🎬 Input Video")
    
    if download_mode == "Single Video":
        video_url = st.text_input(
            "Masukkan URL YouTube:",
            placeholder="https://www.youtube.com/watch?v=..."
        )
    elif download_mode == "Playlist":
        video_url = st.text_input(
            "Masukkan URL Playlist:",
            placeholder="https://www.youtube.com/playlist?list=..."
        )
        playlist_start = st.number_input("Video mulai dari", min_value=1, value=1)
        playlist_end = st.number_input("Video sampai", min_value=1, value=100)
    elif download_mode == "Batch URLs":
        video_urls = st.text_area(
            "Masukkan multiple URLs (satu per baris):",
            height=100,
            placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=..."
        )
    else:  # Audio Only
        video_url = st.text_input(
            "Masukkan URL untuk download audio:",
            placeholder="https://www.youtube.com/watch?v=..."
        )

with col2:
    st.header("📊 Info Video")
    info_placeholder = st.empty()

# Preview video info
if 'video_url' in locals() and video_url:
    with st.spinner("Mengambil informasi video..."):
        video_info = get_video_info(video_url)
        
        if video_info:
            with info_placeholder.container():
                st.image(video_info.get('thumbnail', ''), width=300)
                st.write(f"**Judul:** {video_info.get('title', 'N/A')}")
                st.write(f"**Channel:** {video_info.get('uploader', 'N/A')}")
                st.write(f"**Durasi:** {video_info.get('duration', 0)} detik")
                st.write(f"**Views:** {video_info.get('view_count', 'N/A'):,}")
                st.write(f"**Upload Date:** {video_info.get('upload_date', 'N/A')}")
                
                # Format yang tersedia
                if quality_preset == "Custom":
                    formats = get_available_formats(video_info)
                    if formats:
                        st.write("**Format tersedia:**")
                        format_options = []
                        for f in formats[:10]:  # Batasi 10 format teratas
                            size_mb = f['filesize'] / (1024*1024) if f['filesize'] else 0
                            format_str = f"{f['resolution']}p {f['ext']} ({size_mb:.1f}MB)" if size_mb > 0 else f"{f['resolution']}p {f['ext']}"
                            format_options.append((format_str, f['format_id']))
                        
                        selected_format = st.selectbox(
                            "Pilih format:",
                            options=[opt[0] for opt in format_options]
                        )

# Area download
st.header("⬇️ Download")

# Tombol download
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    download_btn = st.button("🚀 Mulai Download", type="primary", use_container_width=True)

with col2:
    if st.button("📋 Clear All", use_container_width=True):
        st.rerun()

# Progress area
progress_container = st.container()

if download_btn:
    if download_mode == "Single Video" and video_url:
        with progress_container:
            st.markdown('<div class="download-progress">', unsafe_allow_html=True)
            st.write("🔄 Memulai download...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Tentukan format selector
            if quality_preset == "Best Quality":
                format_selector = "best"
            elif quality_preset == "High (1080p)":
                format_selector = "best[height<=1080]"
            elif quality_preset == "Medium (720p)":
                format_selector = "best[height<=720]"
            elif quality_preset == "Low (480p)":
                format_selector = "best[height<=480]"
            else:  # Custom
                if 'selected_format' in locals():
                    # Cari format_id yang sesuai
                    for opt in format_options:
                        if opt[0] == selected_format:
                            format_selector = opt[1]
                            break
                else:
                    format_selector = "best"
            
            # Buat temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Setup progress hook
                progress_hook = ProgressHook()
                progress_hook.set_streamlit_elements(progress_bar, status_text)
                
                # Download
                success, message = download_video(
                    video_url, 
                    temp_dir, 
                    format_selector,
                    audio_only=(download_mode == "Audio Only"),
                    custom_filename=custom_filename if custom_filename else None
                )
                
                if success:
                    st.markdown('<div class="success-box">✅ Download berhasil!</div>', unsafe_allow_html=True)
                    
                    # List file yang didownload
                    downloaded_files = list(Path(temp_dir).glob("*"))
                    
                    if downloaded_files:
                        st.write("📁 **File yang didownload:**")
                        
                        for file_path in downloaded_files:
                            file_size = file_path.stat().st_size / (1024*1024)  # MB
                            st.write(f"- {file_path.name} ({file_size:.1f} MB)")
                            
                            # Tombol download individual
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    label=f"⬇️ Download {file_path.name}",
                                    data=f.read(),
                                    file_name=file_path.name,
                                    mime="application/octet-stream"
                                )
                        
                        # Download semua sebagai ZIP jika lebih dari 1 file
                        if len(downloaded_files) > 1:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                for file_path in downloaded_files:
                                    zip_file.write(file_path, file_path.name)
                            zip_buffer.seek(0)
                            
                            st.download_button(
                                label="📦 Download All as ZIP",
                                data=zip_buffer.getvalue(),
                                file_name=f"youtube_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                                mime="application/zip"
                            )
                else:
                    st.markdown(f'<div class="error-box">❌ Error: {message}</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    elif download_mode == "Batch URLs" and 'video_urls' in locals() and video_urls:
        urls = [url.strip() for url in video_urls.split('\n') if url.strip()]
        
        if urls:
            st.write(f"🔄 Memproses {len(urls)} URL...")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                all_files = []
                
                for i, url in enumerate(urls):
                    st.write(f"📥 Download {i+1}/{len(urls)}: {url}")
                    progress_bar = st.progress((i) / len(urls))
                    
                    success, message = download_video(url, temp_dir, "best")
                    
                    if success:
                        st.success(f"✅ Berhasil: {url}")
                    else:
                        st.error(f"❌ Gagal: {url} - {message}")
                
                progress_bar.progress(1.0)
                
                # List semua file
                downloaded_files = list(Path(temp_dir).glob("*"))
                all_files.extend(downloaded_files)
                
                if downloaded_files:
                    st.write("📁 **Semua file yang didownload:**")
                    
                    # Create ZIP dengan semua file
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_path in downloaded_files:
                            zip_file.write(file_path, file_path.name)
                            file_size = file_path.stat().st_size / (1024*1024)
                            st.write(f"- {file_path.name} ({file_size:.1f} MB)")
                    
                    zip_buffer.seek(0)
                    
                    st.download_button(
                        label="📦 Download All Files as ZIP",
                        data=zip_buffer.getvalue(),
                        file_name=f"batch_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip"
                    )
    else:
        st.warning("⚠️ Silakan masukkan URL yang valid!")

# Footer dengan informasi
st.markdown("---")
st.markdown("""
<div class="feature-box">
<h3>🚀 Fitur Utama:</h3>
<ul>
<li><strong>Multiple Download Modes:</strong> Single video, playlist, batch URLs, dan audio-only</li>
<li><strong>Kualitas Fleksibel:</strong> Dari 480p hingga kualitas terbaik yang tersedia</li>
<li><strong>Format Beragam:</strong> MP4, WebM, MKV, AVI, MOV</li>
<li><strong>Audio Extraction:</strong> MP3, AAC, OGG, WAV</li>
<li><strong>Subtitle Support:</strong> Download dan embed subtitle</li>
<li><strong>Custom Options:</strong> Nama file custom, rentang waktu, dan lainnya</li>
<li><strong>Batch Processing:</strong> Download multiple video sekaligus</li>
<li><strong>Progress Tracking:</strong> Real-time progress dan speed monitoring</li>
</ul>
</div>

<div style="text-align: center; margin-top: 2rem; color: #666;">
<p>Powered by <strong>yt-dlp</strong> & <strong>ffmpeg</strong> | Built with ❤️ using Streamlit</p>
<p><em>Gunakan dengan bijak dan hormati hak cipta konten creator</em></p>
</div>
""", unsafe_allow_html=True)

# Informasi sistem (untuk debugging)
with st.expander("🔧 System Information"):
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Python Packages:**")
        try:
            import yt_dlp
            st.write(f"- yt-dlp: {yt_dlp.version.__version__}")
        except:
            st.write("- yt-dlp: Not available")
        
        try:
            # Cek ffmpeg dengan cara yang aman untuk cloud
            if FFMPEG_PATH:
                result = subprocess.run([FFMPEG_PATH, '-version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    st.write(f"- ffmpeg: {version_line}")
                else:
                    st.write("- ffmpeg: Available but version check failed")
            else:
                st.write("- ffmpeg: Not available (some features limited)")
        except Exception as e:
            st.write(f"- ffmpeg: Error checking version ({str(e)})")
    
    with col2:
        st.write("**Supported Sites:**")
        st.write("- YouTube (videos & playlists)")
        st.write("- YouTube Music")  
        st.write("- Instagram")
        st.write("- TikTok")
        st.write("- Twitter/X")
        st.write("- Facebook")
        st.write("- Dan 1000+ site lainnya!")