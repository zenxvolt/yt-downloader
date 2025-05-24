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
        """Setup yt-dlp options with HD support"""
        ffmpeg_path = FFmpegManager.get_ffmpeg_path()
        
        self.base_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            # Enable merging of video and audio for HD formats
            'format': 'best[height<=1080]/best',
            'merge_output_format': 'mp4',
            # Prefer free formats
            'prefer_free_formats': True,
            # Add headers to avoid some blocks
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        if ffmpeg_path:
            self.base_opts['ffmpeg_location'] = ffmpeg_path
            # Enable post-processing for format conversion
            self.base_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
    
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
        """Get and organize available formats with HD support"""
        if not info or 'formats' not in info:
            return {'video': [], 'audio': [], 'combined': []}
        
        video_formats = []
        audio_formats = []
        combined_formats = []
        seen_video = set()
        seen_audio = set()
        seen_combined = set()
        
        for fmt in info['formats']:
            format_id = fmt.get('format_id', '')
            height = fmt.get('height', 0)
            width = fmt.get('width', 0)
            ext = fmt.get('ext', 'mp4')
            fps = fmt.get('fps', 30)
            filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
            vcodec = fmt.get('vcodec', 'unknown')
            acodec = fmt.get('acodec', 'unknown')
            
            # Combined video+audio formats (older/lower quality)
            if (vcodec != 'none' and acodec != 'none' and height > 0):
                quality_key = f"{height}p_combined"
                if quality_key not in seen_combined and height <= 720:  # Usually combined formats are lower quality
                    combined_formats.append({
                        'format_id': format_id,
                        'quality': f"{height}p",
                        'ext': ext,
                        'fps': fps,
                        'filesize': filesize,
                        'type': 'combined',
                        'display': f"{height}p Combined ({ext}) - {self.format_bytes(filesize)}"
                    })
                    seen_combined.add(quality_key)
            
            # High-quality video-only formats
            elif (vcodec != 'none' and acodec == 'none' and height > 0):
                quality_key = f"{height}p_video"
                if quality_key not in seen_video:
                    # Create format specifier for video+best audio
                    format_spec = f"{format_id}+bestaudio"
                    
                    video_formats.append({
                        'format_id': format_spec,
                        'quality': f"{height}p",
                        'ext': ext,
                        'fps': fps,
                        'filesize': filesize,
                        'vcodec': vcodec[:15],
                        'type': 'video+audio',
                        'display': f"{height}p HD ({ext}) - {self.format_bytes(filesize)} + Audio"
                    })
                    seen_video.add(quality_key)
            
            # Audio-only formats
            elif (acodec != 'none' and vcodec == 'none'):
                abr = fmt.get('abr', 0)
                quality_key = f"{abr}kbps_{ext}"
                if quality_key not in seen_audio and abr:
                    audio_formats.append({
                        'format_id': format_id,
                        'quality': f"{int(abr)}kbps",
                        'ext': ext,
                        'filesize': filesize,
                        'acodec': acodec[:15],
                        'type': 'audio',
                        'display': f"Audio {int(abr)}kbps ({ext}) - {self.format_bytes(filesize)}"
                    })
                    seen_audio.add(quality_key)
        
        # Sort formats by quality (highest first)
        video_formats.sort(key=lambda x: int(x['quality'][:-1]), reverse=True)
        combined_formats.sort(key=lambda x: int(x['quality'][:-1]), reverse=True)
        audio_formats.sort(key=lambda x: int(x['quality'][:-4]), reverse=True)
        
        # Add some preset format options for convenience
        preset_formats = []
        if any(fmt for fmt in video_formats if int(fmt['quality'][:-1]) >= 1080):
            preset_formats.append({
                'format_id': 'best[height<=1080]',
                'quality': 'Best ≤1080p',
                'ext': 'mp4',
                'type': 'preset',
                'display': 'Best quality ≤1080p (Recommended)'
            })
        
        preset_formats.append({
            'format_id': 'best[height<=720]',
            'quality': 'Best ≤720p',
            'ext': 'mp4', 
            'type': 'preset',
            'display': 'Best quality ≤720p (Fast)'
        })
        
        return {
            'preset': preset_formats,
            'video': video_formats[:15],  # Top 15 video formats
            'combined': combined_formats[:5],  # Top 5 combined formats
            'audio': audio_formats[:8]    # Top 8 audio formats
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
        
        # Setup download options with better format handling
        filename_template = '%(title)s.%(ext)s'
        if custom_name:
            filename_template = f'{custom_name}.%(ext)s'
        
        ydl_opts = {
            **self.base_opts,
            'format': format_id,
            'outtmpl': os.path.join(self.output_path, filename_template),
            'progress_hooks': [progress_hook],
            # Ensure we merge video+audio when needed
            'merge_output_format': 'mp4',
            # Add post-processors for better compatibility
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }] if FFmpegManager.get_ffmpeg_path() else []
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
        
        # Quality settings
        st.subheader("🎯 Quality Settings")
        max_quality = st.selectbox(
            "Maximum Quality",
            ["No Limit", "4K (2160p)", "1440p", "1080p", "720p", "480p"],
            index=2,  # Default to 1080p
            help="Set maximum video quality to download"
        )
        
        prefer_format = st.selectbox(
            "Prefer Format",
            ["MP4 (Recommended)", "WebM", "Any"],
            help="Preferred video container format"
        )
        
        # System info
        st.subheader("🖥️ System Info")
        ffmpeg_status = "✅ Available" if st.session_state.ffmpeg_setup else "❌ Not Found"
        st.write(f"FFmpeg: {ffmpeg_status}")
        st.write(f"Platform: {platform.system()}")
        
        if not st.session_state.ffmpeg_setup:
            st.warning("⚠️ FFmpeg not available. HD video merging may be limited.")
        
        return {
            'custom_name': custom_name,
            'download_type': download_type,
            'audio_format': audio_format if download_type == "Audio Only" else None,
            'audio_quality': audio_quality if download_type == "Audio Only" else None,
            'embed_subs': embed_subs,
            'embed_thumbnail': embed_thumbnail,
            'max_quality': max_quality,
            'prefer_format': prefer_format
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
    
    # Organize formats by type
    if settings['download_type'] == "Audio Only":
        available_formats = formats['audio']
        format_type = "Audio"
        st.info("🎵 Audio-only formats selected")
    elif settings['download_type'] == "Video Only":
        available_formats = formats['video']
        format_type = "Video (No Audio)"
        st.warning("📹 Video-only formats (no audio track)")
    else:
        # Combine all video formats for "Video + Audio"
        available_formats = (formats.get('preset', []) + 
                           formats.get('video', []) + 
                           formats.get('combined', []))
        format_type = "Video + Audio"
        st.success("🎬 Video with audio formats")
    
    if not available_formats:
        st.error("❌ No compatible formats found for the selected type")
        return
    
    # Format selection with categories
    format_options = []
    format_categories = []
