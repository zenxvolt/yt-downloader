import streamlit as st
import yt_dlp
import os
import subprocess
import json
import tempfile
from pathlib import Path
import time
import re
from datetime import datetime
import sys
import platform
import requests
import zipfile
import shutil

# Set page config
st.set_page_config(
    page_title="YouTube Downloader Pro",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding-top: 1rem;
    }
    .stAlert {
        margin-top: 1rem;
    }
    .download-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    .feature-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        border-left: 5px solid #667eea;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
    }
    .info-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
        border: 1px solid #e1e5e9;
    }
    .progress-text {
        font-family: 'Courier New', monospace;
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
    }
    .download-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .status-downloading {
        color: #ffc107;
        font-weight: bold;
    }
    .status-completed {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class FFmpegManager:
    """Manage FFmpeg installation for Streamlit Cloud"""
    
    @staticmethod
    def get_ffmpeg_path():
        """Get FFmpeg path, install if needed"""
        # Check if ffmpeg is already available in system
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return 'ffmpeg'
        except:
            pass
        
        # For Streamlit Cloud, try to use pre-installed or install
        possible_paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            './ffmpeg/ffmpeg',
            './ffmpeg'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If not found, return None and handle gracefully
        return None
    
    @staticmethod
    def setup_ffmpeg():
        """Setup FFmpeg for the application"""
        ffmpeg_path = FFmpegManager.get_ffmpeg_path()
        
        if ffmpeg_path:
            os.environ['FFMPEG_BINARY'] = ffmpeg_path
            return True
        else:
            st.warning("⚠️ FFmpeg not found. Some features may be limited.")
            return False

# Initialize session state
def init_session_state():
    if 'download_history' not in st.session_state:
        st.session_state.download_history = []
    if 'current_download' not in st.session_state:
        st.session_state.current_download = None
    if 'ffmpeg_setup' not in st.session_state:
        st.session_state.ffmpeg_setup = FFmpegManager.setup_ffmpeg()

class YouTubeDownloader:
    def __init__(self, output_path=None):
        self.output_path = output_path or tempfile.mkdtemp()
        self.setup_ydl_opts()
    
    def setup_ydl_opts(self):
        """Setup yt-dlp options"""
        ffmpeg_path = FFmpegManager.get_ffmpeg_path()
        
        self.base_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }
        
        if ffmpeg_path:
            self.base_opts['ffmpeg_location'] = ffmpeg_path
    
    def get_video_info(self, url):
        """Get comprehensive video information"""
        try:
            ydl_opts = {**self.base_opts, 'skip_download': True}
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            st.error(f"Error extracting video info: {str(e)}")
            return None
    
    def get_available_formats(self, info):
        """Get and organize available formats"""
        if not info or 'formats' not in info:
            return {'video': [], 'audio': []}
        
        video_formats = []
        audio_formats = []
        seen_video = set()
        seen_audio = set()
        
        for fmt in info['formats']:
            # Video formats (with audio)
            if (fmt.get('vcodec') != 'none' and 
                fmt.get('acodec') != 'none' and 
                fmt.get('height')):
                
                height = fmt.get('height', 0)
                ext = fmt.get('ext', 'mp4')
                fps = fmt.get('fps', 30)
                filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                vcodec = fmt.get('vcodec', 'unknown')
                
                quality_key = f"{height}p_{ext}"
                if quality_key not in seen_video:
                    video_formats.append({
                        'format_id': fmt['format_id'],
                        'quality': f"{height}p",
                        'ext': ext,
                        'fps': fps,
                        'filesize': filesize,
                        'vcodec': vcodec[:10],
                        'display': f"{height}p ({ext}) - {self.format_bytes(filesize)}"
                    })
                    seen_video.add(quality_key)
            
            # Audio-only formats
            elif (fmt.get('acodec') != 'none' and 
                  fmt.get('vcodec') == 'none'):
                
                abr = fmt.get('abr', 0)
                ext = fmt.get('ext', 'mp3')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                acodec = fmt.get('acodec', 'unknown')
                
                quality_key = f"{abr}kbps_{ext}"
                if quality_key not in seen_audio and abr:
                    audio_formats.append({
                        'format_id': fmt['format_id'],
                        'quality': f"{int(abr)}kbps",
                        'ext': ext,
                        'filesize': filesize,
                        'acodec': acodec[:10],
                        'display': f"Audio {int(abr)}kbps ({ext}) - {self.format_bytes(filesize)}"
                    })
                    seen_audio.add(quality_key)
        
        # Sort formats
        video_formats.sort(key=lambda x: int(x['quality'][:-1]), reverse=True)
        audio_formats.sort(key=lambda x: int(x['quality'][:-4]), reverse=True)
        
        return {
            'video': video_formats[:10],  # Top 10 video formats
            'audio': audio_formats[:5]    # Top 5 audio formats
        }
    
    def format_bytes(self, bytes_val):
        """Format bytes to human readable"""
        if not bytes_val:
            return "Unknown size"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} TB"
    
    def download_with_progress(self, url, format_id, custom_name=None):
        """Download with real progress tracking"""
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        download_info = {
            'status': 'starting',
            'progress': 0,
            'speed': 0,
            'eta': 0,
            'filename': ''
        }
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    if d.get('total_bytes'):
                        progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif d.get('total_bytes_estimate'):
                        progress = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                    else:
                        progress = 0
                    
                    download_info.update({
                        'status': 'downloading',
                        'progress': progress,
                        'speed': d.get('speed', 0),
                        'eta': d.get('eta', 0),
                        'filename': d.get('filename', '')
                    })
                    
                    # Update UI
                    progress_placeholder.progress(min(progress / 100, 1.0))
                    
                    speed_str = f"{download_info['speed']/1024/1024:.1f} MB/s" if download_info['speed'] else "-- MB/s"
                    eta_str = f"{download_info['eta']}s" if download_info['eta'] else "--s"
                    
                    status_placeholder.markdown(f"""
                    <div class="progress-text">
                        📥 Downloading: {progress:.1f}% <br>
                        🚀 Speed: {speed_str} <br>
                        ⏱️ ETA: {eta_str}
                    </div>
                    """, unsafe_allow_html=True)
                    
                except Exception as e:
                    pass
            
            elif d['status'] == 'finished':
                download_info['status'] = 'finished'
                download_info['filename'] = d.get('filename', '')
                progress_placeholder.progress(1.0)
                status_placeholder.success("✅ Download completed!")
        
        # Setup download options
        filename_template = '%(title)s.%(ext)s'
        if custom_name:
            filename_template = f'{custom_name}.%(ext)s'
        
        ydl_opts = {
            **self.base_opts,
            'format': format_id,
            'outtmpl': os.path.join(self.output_path, filename_template),
            'progress_hooks': [progress_hook],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, download_info.get('filename', '')
        except Exception as e:
            status_placeholder.error(f"❌ Download failed: {str(e)}")
            return False, str(e)

def render_header():
    """Render application header"""
    st.markdown("""
    <div class="download-card">
        <h1>📺 YouTube Downloader Pro</h1>
        <p>🚀 Professional YouTube video and audio downloader powered by yt-dlp</p>
        <p>✨ Deploy-ready for Streamlit Cloud with advanced features</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render sidebar with settings"""
    with st.sidebar:
        st.header("⚙️ Download Settings")
        
        # Basic settings
        st.subheader("📁 Output Settings")
        custom_name = st.text_input(
            "Custom Filename", 
            placeholder="Leave empty for original name",
            help="Specify custom name for downloaded file"
        )
        
        # Advanced settings
        st.subheader("🔧 Advanced Options")
        
        download_type = st.radio(
            "Download Type",
            ["Video + Audio", "Audio Only", "Video Only"],
            help="Choose what to download"
        )
        
        if download_type == "Audio Only":
            audio_format = st.selectbox(
                "Audio Format",
                ["mp3", "m4a", "wav", "flac", "ogg"]
            )
            audio_quality = st.selectbox(
                "Audio Quality",
                ["best", "320", "256", "192", "128", "96"]
            )
        
        # Additional options
        st.subheader("📝 Additional Options")
        embed_subs = st.checkbox("Embed Subtitles", help="Embed subtitles into video")
        embed_thumbnail = st.checkbox("Embed Thumbnail", help="Embed thumbnail as cover art")
        
        # System info
        st.subheader("🖥️ System Info")
        ffmpeg_status = "✅ Available" if st.session_state.ffmpeg_setup else "❌ Not Found"
        st.write(f"FFmpeg: {ffmpeg_status}")
        st.write(f"Platform: {platform.system()}")
        
        return {
            'custom_name': custom_name,
            'download_type': download_type,
            'audio_format': audio_format if download_type == "Audio Only" else None,
            'audio_quality': audio_quality if download_type == "Audio Only" else None,
            'embed_subs': embed_subs,
            'embed_thumbnail': embed_thumbnail
        }

def render_main_content(settings):
    """Render main content area"""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🔗 Enter Video URL")
        
        url_input = st.text_input(
            "",
            placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            help="Paste any YouTube video URL here"
        )
        
        if url_input:
            if not url_input.startswith(('https://www.youtube.com/', 'https://youtu.be/', 'https://m.youtube.com/')):
                st.error("❌ Please enter a valid YouTube URL")
                return
            
            downloader = YouTubeDownloader()
            
            # Get video info
            with st.spinner("🔍 Analyzing video..."):
                video_info = downloader.get_video_info(url_input)
            
            if video_info:
                render_video_info(video_info)
                render_format_selection(video_info, downloader, settings, url_input)
            else:
                st.error("❌ Could not retrieve video information. Please check the URL.")
    
    with col2:
        render_download_panel()

def render_video_info(info):
    """Render video information card"""
    st.success("✅ Video found and analyzed!")
    
    # Video info card
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    
    col_info1, col_info2 = st.columns([2, 1])
    
    with col_info1:
        st.markdown("### 📋 Video Details")
        title = info.get('title', 'Unknown Title')
        st.write(f"**Title:** {title}")
        st.write(f"**Channel:** {info.get('uploader', 'Unknown')}")
        st.write(f"**Duration:** {info.get('duration_string', 'Unknown')}")
        st.write(f"**Views:** {info.get('view_count', 0):,}")
        st.write(f"**Upload Date:** {info.get('upload_date', 'Unknown')}")
        
        # Description preview
        description = info.get('description', '')
        if description:
            st.write(f"**Description:** {description[:100]}...")
    
    with col_info2:
        # Thumbnail
        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            try:
                st.image(thumbnail_url, width=250, caption="Video Thumbnail")
            except:
                st.write("🖼️ Thumbnail not available")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_format_selection(info, downloader, settings, url):
    """Render format selection and download options"""
    st.markdown("### 🎥 Available Formats")
    
    formats = downloader.get_available_formats(info)
    
    if settings['download_type'] == "Audio Only":
        available_formats = formats['audio']
        format_type = "Audio"
    else:
        available_formats = formats['video'] + formats['audio']
        format_type = "Video/Audio"
    
    if not available_formats:
        st.error("❌ No compatible formats found")
        return
    
    # Format selection
    format_options = [fmt['display'] for fmt in available_formats]
    
    selected_idx = st.selectbox(
        f"Choose {format_type} Format:",
        range(len(format_options)),
        format_func=lambda x: format_options[x]
    )
    
    selected_format = available_formats[selected_idx]
    
    # Format details
    col_detail1, col_detail2, col_detail3 = st.columns(3)
    
    with col_detail1:
        st.metric("Quality", selected_format['quality'])
    with col_detail2:
        st.metric("Format", selected_format['ext'].upper())
    with col_detail3:
        st.metric("Size", downloader.format_bytes(selected_format['filesize']))
    
    # Download buttons
    st.markdown("### ⬇️ Download Options")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("🚀 Download Now", type="primary", use_container_width=True):
            start_download(url, selected_format, downloader, settings, info)
    
    with col_btn2:
        if st.button("📋 Copy Video Info", use_container_width=True):
            video_info_text = f"""
Title: {info.get('title', 'Unknown')}
Channel: {info.get('uploader', 'Unknown')}
URL: {url}
Duration: {info.get('duration_string', 'Unknown')}
Views: {info.get('view_count', 0):,}
            """
            st.code(video_info_text.strip())
    
    with col_btn3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

def start_download(url, format_info, downloader, settings, video_info):
    """Start the download process"""
    st.markdown("### 📥 Downloading...")
    
    # Add to current download
    st.session_state.current_download = {
        'url': url,
        'format': format_info,
        'settings': settings,
        'video_info': video_info,
        'status': 'downloading',
        'start_time': datetime.now()
    }
    
    # Perform download
    success, result = downloader.download_with_progress(
        url, 
        format_info['format_id'],
        settings.get('custom_name')
    )
    
    if success:
        # Add to history
        st.session_state.download_history.append({
            'title': video_info.get('title', 'Unknown'),
            'format': format_info['display'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'completed',
            'filename': result
        })
        
        st.success("🎉 Download completed successfully!")
        
        # Provide download link (if file exists and accessible)
        if os.path.exists(result):
            st.download_button(
                label="💾 Download File",
                data=open(result, 'rb').read(),
                file_name=os.path.basename(result),
                mime="application/octet-stream"
            )
    else:
        st.error(f"❌ Download failed: {result}")
    
    # Clear current download
    st.session_state.current_download = None

def render_download_panel():
    """Render download status and history panel"""
    st.header("📊 Download Status")
    
    # Current download
    if st.session_state.current_download:
        download = st.session_state.current_download
        
        st.markdown("### 🔄 Currently Downloading")
        st.write(f"**Title:** {download['video_info']['title'][:40]}...")
        st.write(f"**Format:** {download['format']['display']}")
        st.write(f"**Started:** {download['start_time'].strftime('%H:%M:%S')}")
        
        # This would show real progress in actual implementation
        with st.spinner("Downloading in progress..."):
            pass
    
    # Download history
    if st.session_state.download_history:
        st.markdown("### 📜 Recent Downloads")
        
        for i, item in enumerate(reversed(st.session_state.download_history[-5:])):
            status_color = "status-completed" if item['status'] == 'completed' else "status-error"
            
            with st.expander(f"📄 {item['title'][:30]}..."):
                st.write(f"**Format:** {item['format']}")
                st.write(f"**Time:** {item['timestamp']}")
                st.markdown(f"**Status:** <span class='{status_color}'>{item['status'].title()}</span>", 
                           unsafe_allow_html=True)
                
                col_hist1, col_hist2 = st.columns(2)
                with col_hist1:
                    if st.button("🗑️ Remove", key=f"remove_{i}"):
                        st.session_state.download_history.remove(item)
                        st.rerun()
                with col_hist2:
                    if st.button("📋 Copy Info", key=f"copy_{i}"):
                        st.code(f"Title: {item['title']}\nFormat: {item['format']}\nTime: {item['timestamp']}")
    else:
        st.info("📭 No downloads yet")

def render_features():
    """Render features section"""
    st.markdown("---")
    st.header("✨ Features & Capabilities")
    
    col1, col2, col3, col4 = st.columns(4)
    
    features = [
        ("🎥", "HD Video Download", "Download videos up to 4K quality"),
        ("🎵", "Audio Extraction", "High-quality MP3, FLAC, M4A"),
        ("⚡", "Fast Processing", "Optimized with yt-dlp engine"),
        ("☁️", "Cloud Ready", "Deployed on Streamlit Cloud")
    ]
    
    for i, (icon, title, desc) in enumerate(features):
        with [col1, col2, col3, col4][i]:
            st.markdown(f"""
            <div class="feature-box">
                <h3 style="margin:0; color:#333;">{icon} {title}</h3>
                <p style="margin:0.5rem 0 0 0; color:#666;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Technical details
    with st.expander("🔧 Technical Information"):
        st.markdown("""
        ### System Requirements:
        - **Python 3.8+** with required packages
        - **yt-dlp** for YouTube processing
        - **FFmpeg** for media processing (auto-configured)
        
        ### Supported Formats:
        **Video:** MP4, WebM, AVI, MKV  
        **Audio:** MP3, M4A, WAV, FLAC, OGG
        
        ### Cloud Deployment:
        This app is optimized for **Streamlit Cloud** with automatic dependency management.
        """)

def render_footer():
    """Render footer"""
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 2rem; color: #666;">
        <h4>📺 YouTube Downloader Pro</h4>
        <p>Built with ❤️ using <strong>Streamlit</strong> & <strong>yt-dlp</strong></p>
        <p><small>⚠️ Please respect copyright laws and YouTube's Terms of Service</small></p>
        <p><small>🌟 Star this project if you find it useful!</small></p>
    </div>
    """, unsafe_allow_html=True)

def main():
    """Main application function"""
    # Initialize
    init_session_state()
    
    # Render components
    render_header()
    settings = render_sidebar()
    render_main_content(settings)
    render_features()
    render_footer()

if __name__ == "__main__":
    main()