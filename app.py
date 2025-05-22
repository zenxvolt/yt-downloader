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
    page_title="YouTube Downloader",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS untuk tampilan minimalis modern
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    .stApp {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1000px;
    }
    
    /* Header */
    .header-container {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .header-subtitle {
        color: #64748b;
        font-size: 1.1rem;
        font-weight: 400;
    }
    
    /* Cards */
    .card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    
    .video-info-card {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* Progress */
    .progress-container {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
    
    /* Success/Error boxes */
    .success-box {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        font-weight: 500;
    }
    
    .error-box {
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        font-weight: 500;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        font-weight: 500;
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.9);
        padding: 0.75rem 1rem;
        font-size: 1rem;
    }
    
    .stSelectbox > div > div > div {
        border-radius: 12px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.9);
    }
    
    /* Remove default styling */
    .stTextInput > label, .stSelectbox > label {
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: rgba(255, 255, 255, 0.8);
        font-size: 0.9rem;
        margin-top: 3rem;
        padding: 1rem;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'clear_trigger' not in st.session_state:
    st.session_state.clear_trigger = False
if 'video_url' not in st.session_state:
    st.session_state.video_url = ""
if 'video_urls' not in st.session_state:
    st.session_state.video_urls = ""
if 'custom_filename' not in st.session_state:
    st.session_state.custom_filename = ""

# Fungsi untuk mengecek dan setup ffmpeg
@st.cache_resource
def setup_ffmpeg():
    """Setup ffmpeg untuk Streamlit Cloud"""
    ffmpeg_path = None
    
    ffmpeg_locations = [
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        shutil.which('ffmpeg'),
        './ffmpeg',
    ]
    
    for location in ffmpeg_locations:
        if location and os.path.isfile(location):
            ffmpeg_path = location
            break
    
    return ffmpeg_path

FFMPEG_PATH = setup_ffmpeg()

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

# Progress Hook Class
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
def download_video(url, output_path, format_selector, output_format, audio_only=False, custom_filename=None, extract_audio=False, audio_format='mp3'):
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
        
        # Custom filename
        if custom_filename:
            ydl_opts['outtmpl'] = os.path.join(output_path, f'{sanitize_filename(custom_filename)}.%(ext)s')
        
        # Audio only mode
        if audio_only:
            if FFMPEG_PATH:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format,
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = 'bestaudio/best'
        
        # Extract audio tambahan
        elif extract_audio and FFMPEG_PATH:
            if 'postprocessors' not in ydl_opts:
                ydl_opts['postprocessors'] = []
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': '192',
            })
        
        # Format conversion untuk video
        if not audio_only and output_format != 'mp4' and FFMPEG_PATH:
            if 'postprocessors' not in ydl_opts:
                ydl_opts['postprocessors'] = []
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegVideoConvertor',
                'preferedformat': output_format,
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return True, "Download berhasil!"
        
    except Exception as e:
        return False, str(e)

# Header
st.markdown("""
<div class="header-container">
    <div class="header-title">📺 YouTube Downloader</div>
    <div class="header-subtitle">Download video YouTube dengan mudah dan cepat</div>
</div>
""", unsafe_allow_html=True)

# Clear All Handler
def clear_all():
    st.session_state.video_url = ""
    st.session_state.video_urls = ""
    st.session_state.custom_filename = ""
    st.session_state.clear_trigger = True

# Main Interface
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    # Download Mode
    download_mode = st.selectbox(
        "Mode Download",
        ["Single Video", "Playlist", "Audio Only", "Batch URLs"],
        key="download_mode"
    )
    
    # URL Input berdasarkan mode
    if download_mode == "Single Video":
        video_url = st.text_input(
            "URL YouTube:",
            placeholder="https://www.youtube.com/watch?v=...",
            value=st.session_state.video_url if not st.session_state.clear_trigger else "",
            key="url_input"
        )
        if video_url != st.session_state.video_url:
            st.session_state.video_url = video_url
            
    elif download_mode == "Playlist":
        video_url = st.text_input(
            "URL Playlist:",
            placeholder="https://www.youtube.com/playlist?list=...",
            value=st.session_state.video_url if not st.session_state.clear_trigger else "",
            key="playlist_input"
        )
        col_start, col_end = st.columns(2)
        with col_start:
            playlist_start = st.number_input("Video mulai dari", min_value=1, value=1)
        with col_end:
            playlist_end = st.number_input("Video sampai", min_value=1, value=100)
            
    elif download_mode == "Batch URLs":
        video_urls = st.text_area(
            "Multiple URLs (satu per baris):",
            height=100,
            placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
            value=st.session_state.video_urls if not st.session_state.clear_trigger else "",
            key="batch_input"
        )
        if video_urls != st.session_state.video_urls:
            st.session_state.video_urls = video_urls
            
    else:  # Audio Only
        video_url = st.text_input(
            "URL untuk Audio:",
            placeholder="https://www.youtube.com/watch?v=...",
            value=st.session_state.video_url if not st.session_state.clear_trigger else "",
            key="audio_input"
        )
        if video_url != st.session_state.video_url:
            st.session_state.video_url = video_url
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Settings
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Pengaturan")
    
    col_set1, col_set2, col_set3 = st.columns(3)
    
    with col_set1:
        quality_preset = st.selectbox(
            "Kualitas Video",
            ["Best Quality", "1080p", "720p", "480p", "Custom"]
        )
        
    with col_set2:
        output_format = st.selectbox(
            "Format Video",
            ["mp4", "webm", "mkv", "avi", "mov"]
        )
        
    with col_set3:
        audio_format = st.selectbox(
            "Format Audio",
            ["mp3", "aac", "ogg", "wav"]
        )
    
    # Additional options
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        extract_audio = st.checkbox("Ekstrak audio terpisah")
        download_subs = st.checkbox("Download subtitle")
    with col_opt2:
        custom_filename = st.text_input(
            "Nama file custom (opsional)",
            value=st.session_state.custom_filename if not st.session_state.clear_trigger else "",
            key="filename_input"
        )
        if custom_filename != st.session_state.custom_filename:
            st.session_state.custom_filename = custom_filename
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="video-info-card">', unsafe_allow_html=True)
    st.subheader("📊 Info Video")
    
    # Get current URL based on mode
    current_url = ""
    if download_mode in ["Single Video", "Playlist", "Audio Only"]:
        current_url = st.session_state.video_url
    
    if current_url:
        with st.spinner("Mengambil info..."):
            video_info = get_video_info(current_url)
            
            if video_info:
                if video_info.get('thumbnail'):
                    st.image(video_info['thumbnail'], width=280)
                
                st.write(f"**{video_info.get('title', 'N/A')[:50]}...**")
                st.write(f"📺 {video_info.get('uploader', 'N/A')}")
                
                duration = video_info.get('duration', 0)
                if duration:
                    minutes, seconds = divmod(duration, 60)
                    st.write(f"⏱️ {minutes:02d}:{seconds:02d}")
                
                view_count = video_info.get('view_count', 0)
                if view_count:
                    st.write(f"👁️ {view_count:,} views")
                
                # Custom format selection
                if quality_preset == "Custom":
                    formats = get_available_formats(video_info)
                    if formats:
                        format_options = []
                        for f in formats[:8]:
                            size_mb = f['filesize'] / (1024*1024) if f['filesize'] else 0
                            format_str = f"{f['resolution']}p {f['ext']}"
                            if size_mb > 0:
                                format_str += f" ({size_mb:.1f}MB)"
                            format_options.append((format_str, f['format_id']))
                        
                        selected_format = st.selectbox(
                            "Format:",
                            options=[opt[0] for opt in format_options],
                            key="format_select"
                        )
            else:
                st.error("❌ URL tidak valid")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Reset clear trigger
if st.session_state.clear_trigger:
    st.session_state.clear_trigger = False

# Download Buttons
st.markdown('<div class="card">', unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

with col_btn1:
    download_btn = st.button("🚀 Mulai Download", type="primary", use_container_width=True)

with col_btn2:
    if st.button("🧹 Clear All", use_container_width=True):
        clear_all()
        st.rerun()

with col_btn3:
    # FFmpeg status
    if FFMPEG_PATH:
        st.success("✅ FFmpeg OK")
    else:
        st.warning("⚠️ FFmpeg Limited")

st.markdown('</div>', unsafe_allow_html=True)

# Download Process
if download_btn:
    current_url = ""
    urls_to_process = []
    
    # Determine URLs to process
    if download_mode == "Single Video" or download_mode == "Audio Only":
        if st.session_state.video_url:
            current_url = st.session_state.video_url
            urls_to_process = [current_url]
    elif download_mode == "Playlist":
        if st.session_state.video_url:
            current_url = st.session_state.video_url
            urls_to_process = [current_url]  # yt-dlp handles playlist internally
    elif download_mode == "Batch URLs":
        if st.session_state.video_urls:
            urls_to_process = [url.strip() for url in st.session_state.video_urls.split('\n') if url.strip()]
    
    if urls_to_process:
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        
        # Determine format selector
        if quality_preset == "Best Quality":
            format_selector = "best"
        elif quality_preset == "1080p":
            format_selector = "best[height<=1080]"
        elif quality_preset == "720p":
            format_selector = "best[height<=720]"
        elif quality_preset == "480p":
            format_selector = "best[height<=480]"
        else:  # Custom
            format_selector = "best"
            if quality_preset == "Custom" and 'selected_format' in locals():
                for opt in format_options:
                    if opt[0] == selected_format:
                        format_selector = opt[1]
                        break
        
        # Process downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            all_downloaded_files = []
            
            for i, url in enumerate(urls_to_process):
                if len(urls_to_process) > 1:
                    st.write(f"📥 Processing {i+1}/{len(urls_to_process)}: {url[:50]}...")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Setup progress hook
                progress_hook = ProgressHook()
                progress_hook.set_streamlit_elements(progress_bar, status_text)
                
                # Download
                success, message = download_video(
                    url, 
                    temp_dir, 
                    format_selector,
                    output_format,
                    audio_only=(download_mode == "Audio Only"),
                    custom_filename=st.session_state.custom_filename if st.session_state.custom_filename else None,
                    extract_audio=extract_audio,
                    audio_format=audio_format
                )
                
                if success:
                    st.markdown('<div class="success-box">✅ Download berhasil!</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="error-box">❌ Error: {message}</div>', unsafe_allow_html=True)
            
            # List and provide download links
            downloaded_files = list(Path(temp_dir).glob("*"))
            all_downloaded_files.extend(downloaded_files)
            
            if downloaded_files:
                st.write("📁 **File siap download:**")
                
                for file_path in downloaded_files:
                    file_size = file_path.stat().st_size / (1024*1024)  # MB
                    col_file1, col_file2 = st.columns([3, 1])
                    
                    with col_file1:
                        st.write(f"📄 {file_path.name} ({file_size:.1f} MB)")
                    
                    with col_file2:
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label="⬇️",
                                data=f.read(),
                                file_name=file_path.name,
                                mime="application/octet-stream",
                                key=f"download_{file_path.name}"
                            )
                
                # ZIP download untuk multiple files
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
                        mime="application/zip",
                        type="primary"
                    )
        
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="warning-box">⚠️ Silakan masukkan URL yang valid!</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
<div class="footer">
    <p>Powered by <strong>yt-dlp</strong> & <strong>ffmpeg</strong> • Built with ❤️ using Streamlit</p>
    <p><em>Gunakan dengan bijak dan hormati hak cipta</em></p>
</div>
""", unsafe_allow_html=True)