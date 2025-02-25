import streamlit as st
import yt_dlp
import os
import tempfile
import base64
import re
import time
import pandas as pd
import plotly.express as px
import subprocess
from urllib.parse import urlparse, parse_qs

# Set page config
st.set_page_config(
    page_title="YouTube Downloader Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #FF0000;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        color: #155724;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-message {
        padding: 1rem;
        background-color: #f8d7da;
        color: #721c24;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #e7f3fe;
        border-left: 6px solid #2196F3;
        padding: 0.5rem 1rem;
        margin: 1rem 0;
    }
    .download-btn {
        background-color: #4CAF50;
        color: white;
        padding: 0.5rem 1rem;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 1rem;
        border-radius: 0.3rem;
        margin: 0.5rem 0;
    }
    .feature-box {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# Check if ffmpeg is installed
def check_ffmpeg():
    try:
        # Try to run ffmpeg
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

# Function to install yt-dlp and ffmpeg if necessary
def setup_dependencies():
    with st.spinner("Setting up dependencies..."):
        # For Streamlit Cloud, we can assume yt-dlp is installed via requirements.txt
        # Check for ffmpeg
        if not check_ffmpeg():
            st.warning("FFmpeg not found. Attempting to install...")
            try:
                # This is for Linux environments (like Streamlit Cloud)
                subprocess.run(["apt-get", "update"], check=True)
                subprocess.run(["apt-get", "install", "-y", "ffmpeg"], check=True)
                st.success("FFmpeg installed successfully!")
            except subprocess.SubprocessError:
                st.error("Failed to install FFmpeg. Some features may not work properly.")

# Function to get video info
def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info
        except yt_dlp.utils.DownloadError as e:
            st.error(f"Error: {str(e)}")
            return None

# Function to download video/audio
def download_media(url, download_type, format_id=None, quality=None, audio_only=False, 
                   audio_format="mp3", video_format="mp4", extract_audio=False, trim=False, 
                   start_time=None, end_time=None, filename=None, thumbnail=False):
    
    # Create a temporary directory for downloads
    temp_dir = tempfile.mkdtemp()
    
    # Set filename template
    if not filename:
        filename = "%(title)s.%(ext)s"
    else:
        # Ensure filename has the right extension placeholder
        if "%(ext)s" not in filename:
            filename += ".%(ext)s"
    
    output_template = os.path.join(temp_dir, filename)
    
    # Configure yt-dlp options based on download type
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': False,
        'no_warnings': True,
        'progress_hooks': [lambda d: update_progress(d)],
    }
    
    # Add format options based on download type
    if download_type == "video":
        if format_id:
            ydl_opts['format'] = format_id
        else:
            if quality == "best":
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            elif quality == "medium":
                ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]'
            elif quality == "low":
                ydl_opts['format'] = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
            
        if video_format != "mp4":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': video_format,
            }]
    
    elif download_type == "audio":
        if audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': '192',
            }]
    
    elif download_type == "audio_extract":
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': '192',
        }]
    
    # Add thumbnail download option
    if thumbnail:
        ydl_opts['writethumbnail'] = True
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegThumbnailsConvertor',
            'format': 'jpg',
        })
    
    # Download the media
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            
            # Handle extension change for audio formats
            if download_type in ["audio", "audio_extract"]:
                base, _ = os.path.splitext(downloaded_file)
                downloaded_file = f"{base}.{audio_format}"
            
            # Trim the media if requested
            if trim and start_time and end_time:
                try:
                    original_file = downloaded_file
                    file_base, file_ext = os.path.splitext(original_file)
                    trimmed_file = f"{file_base}_trimmed{file_ext}"
                    
                    # Convert time format if needed (e.g., "1:30" to "00:01:30")
                    start_time_str = format_time(start_time)
                    end_time_str = format_time(end_time)
                    
                    # ffmpeg command to trim
                    trimming_status = st.empty()
                    trimming_status.info(f"Trimming media from {start_time_str} to {end_time_str}...")
                    
                    ffmpeg_cmd = [
                        "ffmpeg", "-i", original_file, 
                        "-ss", start_time_str, "-to", end_time_str, 
                        "-c:v", "copy", "-c:a", "copy", trimmed_file
                    ]
                    
                    subprocess.run(ffmpeg_cmd, check=True)
                    trimming_status.success("Trimming completed successfully!")
                    
                    # Use the trimmed file instead
                    downloaded_file = trimmed_file
                    
                except subprocess.SubprocessError as e:
                    st.error(f"Error during trimming: {str(e)}")
            
            return downloaded_file, info
    except yt_dlp.utils.DownloadError as e:
        st.error(f"Download Error: {str(e)}")
        return None, None

# Function to format time for ffmpeg
def format_time(time_str):
    # Check if time is already in HH:MM:SS format
    if re.match(r'^\d+:\d+:\d+$', time_str):
        return time_str
    
    # Check if time is in MM:SS format
    if re.match(r'^\d+:\d+$', time_str):
        return f"00:{time_str}"
    
    # Check if time is just seconds
    if re.match(r'^\d+$', time_str):
        seconds = int(time_str)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    
    # Default case
    return time_str

# Function to create a download link
def get_download_link(file_path, link_text, file_type):
    with open(file_path, "rb") as file:
        data = file.read()
    b64 = base64.b64encode(data).decode()
    file_name = os.path.basename(file_path)
    mime_type = "audio/mpeg" if file_type == "audio" else "video/mp4"
    href = f'<a href="data:{mime_type};base64,{b64}" download="{file_name}" class="download-btn">{link_text}</a>'
    return href

# Function to update progress
def update_progress(d):
    if d['status'] == 'downloading':
        try:
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes > 0:
                progress = downloaded_bytes / total_bytes
                progress_bar.progress(progress)
                download_status.text(f"Downloading: {d.get('_percent_str', '0%')} at {d.get('_speed_str', 'N/A')}")
            else:
                download_status.text(f"Downloading: {downloaded_bytes/1024/1024:.1f} MB at {d.get('_speed_str', 'N/A')}")
        except Exception as e:
            download_status.text(f"Downloading... {d.get('_percent_str', '')}")
    
    elif d['status'] == 'finished':
        progress_bar.progress(1.0)
        download_status.success("Download completed!")

# Function to extract video ID from URL
def extract_video_id(url):
    parsed_url = urlparse(url)
    
    if parsed_url.netloc == 'youtu.be':
        return parsed_url.path[1:]
    elif parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        elif parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2]
    
    # Return None if unable to extract ID
    return None

# Function to check if URL is a valid YouTube URL
def is_valid_youtube_url(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    youtube_regex_match = re.match(youtube_regex, url)
    return bool(youtube_regex_match)

# Function to display video statistics
def display_video_stats(info):
    if not info:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Video Information")
        info_table = {
            "Title": info.get('title', 'N/A'),
            "Channel": info.get('uploader', 'N/A'),
            "Duration": f"{int(info.get('duration', 0) // 60)}:{int(info.get('duration', 0) % 60):02d}",
            "Upload Date": info.get('upload_date', 'N/A'),
            "Views": f"{info.get('view_count', 0):,}",
            "Likes": f"{info.get('like_count', 0):,}",
        }
        
        df = pd.DataFrame(list(info_table.items()), columns=['Metric', 'Value'])
        st.table(df)
    
    with col2:
        st.subheader("Engagement Statistics")
        if 'view_count' in info and 'like_count' in info:
            data = {
                'Metric': ['Views', 'Likes'],
                'Count': [info.get('view_count', 0), info.get('like_count', 0)]
            }
            fig = px.bar(data, x='Metric', y='Count', color='Metric', 
                         color_discrete_map={'Views': 'blue', 'Likes': 'red'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

# Function to extract and display playlist info
def handle_playlist(url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                st.subheader(f"Playlist: {info.get('title', 'Unknown')}")
                st.write(f"Total videos: {len(info['entries'])}")
                
                # Create a DataFrame for the playlist
                playlist_data = []
                for index, entry in enumerate(info['entries']):
                    playlist_data.append({
                        'Index': index + 1,
                        'Title': entry.get('title', 'Unknown'),
                        'URL': f"https://www.youtube.com/watch?v={entry.get('id')}",
                    })
                
                playlist_df = pd.DataFrame(playlist_data)
                st.dataframe(playlist_df)
                
                # Option to download the entire playlist
                if st.button("Download Entire Playlist"):
                    download_playlist(url)
                
                return True
            
            return False
        
        except yt_dlp.utils.DownloadError as e:
            st.error(f"Error: {str(e)}")
            return False

# Function to download a playlist
def download_playlist(url):
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, "%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s")
    
    ydl_opts = {
        'outtmpl': output_template,
        'quiet': False,
        'no_warnings': True,
        'format': 'best',
    }
    
    with st.spinner("Downloading playlist..."):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
                st.success("Playlist downloaded successfully!")
                st.info("Note: Playlist download is for demonstration purposes. In a production app, you would need to create a zip file of the downloads and provide a download link.")
            except yt_dlp.utils.DownloadError as e:
                st.error(f"Error downloading playlist: {str(e)}")

# Main app
def main():
    st.markdown("<h1 class='main-header'>YouTube Downloader Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-header'>Download videos, audio, and playlists with advanced options</p>", unsafe_allow_html=True)
    
    # Setup dependencies
    setup_dependencies()
    
    # Sidebar with app info
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png", width=200)
        st.title("Features")
        st.markdown("""
        - 🎬 Download videos in various formats and qualities
        - 🎵 Extract audio from videos
        - ✂️ Trim videos to specific timestamps
        - 📋 Support for playlists
        - 📊 Video statistics and information
        - 🖼️ Download video thumbnails
        """)
        
        st.title("How to Use")
        st.markdown("""
        1. Paste a YouTube video or playlist URL
        2. Select download options
        3. Click download and wait for processing
        4. Click the download link when ready
        """)
        
        st.caption("Made with ❤️ using Streamlit, yt-dlp, and ffmpeg")
    
    # Main content
    url = st.text_input("Enter YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")
    
    if url:
        if not is_valid_youtube_url(url):
            st.error("Please enter a valid YouTube URL")
        else:
            # Check if it's a playlist
            if "playlist" in url or "list=" in url:
                is_playlist = handle_playlist(url)
                if is_playlist:
                    st.write("---")
                    st.write("You can also download individual videos from the playlist by pasting their URL above.")
                    return
            
            # Get video info
            with st.spinner("Fetching video information..."):
                info = get_video_info(url)
                
                if info:
                    # Extract video ID for thumbnail
                    video_id = extract_video_id(url)
                    if video_id:
                        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                        st.image(thumbnail_url, use_column_width=True)
                    
                    # Display basic video info
                    st.title(info.get('title', 'Unknown Title'))
                    st.write(f"By: {info.get('uploader', 'Unknown uploader')}")
                    
                    # Show tabs for different download options
                    tab1, tab2, tab3, tab4 = st.tabs(["📹 Video", "🎵 Audio", "✂️ Advanced", "📊 Stats"])
                    
                    # Video tab
                    with tab1:
                        st.header("Download Video")
                        
                        # Get available formats
                        formats = []
                        if 'formats' in info:
                            for f in info['formats']:
                                if f.get('resolution') != 'audio only' and f.get('ext') in ['mp4', 'webm', 'mkv']:
                                    format_info = f"{f.get('format_id')} - {f.get('ext')} - {f.get('resolution')} - {f.get('fps', 'N/A')}fps"
                                    formats.append((f.get('format_id'), format_info))
                        
                        # Video quality options
                        quality_col, format_col = st.columns(2)
                        
                        with quality_col:
                            quality = st.radio("Select video quality:", ["best", "medium", "low"])
                        
                        with format_col:
                            video_format = st.selectbox("Select output format:", ["mp4", "mkv", "webm", "avi"])
                        
                        # Option to select specific format
                        use_specific_format = st.checkbox("Use specific format (advanced)")
                        if use_specific_format and formats:
                            format_id = st.selectbox(
                                "Select specific format:",
                                options=[f[0] for f in formats],
                                format_func=lambda x: next((f[1] for f in formats if f[0] == x), x)
                            )
                        else:
                            format_id = None
                        
                        # Download button
                        if st.button("Download Video"):
                            global progress_bar, download_status
                            progress_bar = st.progress(0)
                            download_status = st.empty()
                            
                            downloaded_file, download_info = download_media(
                                url, 
                                "video", 
                                format_id=format_id, 
                                quality=quality, 
                                video_format=video_format
                            )
                            
                            if downloaded_file:
                                st.markdown(get_download_link(downloaded_file, "Download Video", "video"), unsafe_allow_html=True)
                    
                    # Audio tab
                    with tab2:
                        st.header("Download Audio")
                        
                        audio_format = st.selectbox("Select audio format:", ["mp3", "m4a", "wav", "flac", "ogg"])
                        
                        # Download button
                        if st.button("Download Audio"):
                            global progress_bar, download_status
                        