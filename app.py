import streamlit as st
import yt_dlp
import os
import shutil
import tempfile
import re

# Define base output directory
BASE_TEMP_AUDIO_DIR = "temp_audio_batches"

# Regex for YouTube URL validation
# Matches standard video URLs, shortened youtu.be URLs, and allows for extra parameters (timestamps, playlists).
YOUTUBE_URL_PATTERN = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})([\[\]\(\)\w\s=&%#@!?\+\-_.:;\'"]*)?$'
)

def ensure_base_temp_dir():
    """Ensures the base temporary directory for all processing batches exists."""
    if not os.path.exists(BASE_TEMP_AUDIO_DIR):
        try:
            os.makedirs(BASE_TEMP_AUDIO_DIR)
        except OSError as e:
            st.error(f"Fatal Error: Could not create base temporary directory {BASE_TEMP_AUDIO_DIR}: {e}. Please check permissions.")
            st.stop()

def progress_hook(d, hook_data):
    """Hook for yt-dlp to update Streamlit UI on progress."""
    progress_bar = hook_data['progress_bar']
    status_placeholder = hook_data['status_placeholder']
    video_title = hook_data['video_title']

    if d['status'] == 'downloading':
        total_bytes_str = d.get('_total_bytes_str', 'N/A')
        speed_str = d.get('_speed_str', 'N/A')
        percent_str = d.get('_percent_str', '0%')
        try:
            percentage = float(percent_str.replace('%', ''))
        except ValueError:
            percentage = 0
        
        current_progress = 10 + int(percentage * 0.7) 
        progress_bar.progress(current_progress)
        status_placeholder.info(f"Downloading '{video_title}': {percent_str} of {total_bytes_str} at {speed_str}")
    elif d['status'] == 'finished':
        progress_bar.progress(85)
        status_placeholder.info(f"Download of '{video_title}' complete. Converting to MP3...")
    elif d['status'] == 'error':
        # This message might be generic; more specific errors are caught in the main processing loop.
        status_placeholder.warning(f"A problem occurred during yt-dlp processing of '{video_title}'. Waiting for final status...")

def process_videos(urls):
    """Processes a list of URLs: downloads, converts, and prepares for download."""
    st.session_state.download_links = []
    st.session_state.processing_done = False
    
    if not urls:
        st.warning("Please enter at least one YouTube URL.")
        return

    raw_url_list = [url.strip() for url in urls.splitlines() if url.strip()]
    if not raw_url_list:
        st.warning("No URLs provided. Please check your input.")
        return

    results_container = st.container()
    
    valid_urls_to_process = []
    for u in raw_url_list:
        if YOUTUBE_URL_PATTERN.match(u):
            valid_urls_to_process.append(u)
        else:
            results_container.warning(f"Skipped: '{u}' does not appear to be a valid YouTube video URL.")
            
    if not valid_urls_to_process:
        results_container.error("No valid YouTube URLs found among the provided inputs.")
        return

    ensure_base_temp_dir() # Ensure base directory is available
    
    current_batch_temp_dir = None
    try:
        current_batch_temp_dir = tempfile.mkdtemp(dir=BASE_TEMP_AUDIO_DIR)

        for i, url in enumerate(valid_urls_to_process):
            video_container = results_container.container()
            video_container.markdown("---")
            status_placeholder = video_container.empty()
            progress_bar = video_container.progress(0)
            
            status_placeholder.info(f"Preparing to process URL: {url}")

            hook_data = {
                'progress_bar': progress_bar,
                'status_placeholder': status_placeholder,
                'video_title': "Unknown Video"
            }

            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(current_batch_temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [lambda d: progress_hook(d, hook_data)],
                # 'ffmpeg_location' is removed; relying on ffmpeg in PATH (installed by startup.sh)
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    status_placeholder.info(f"Fetching video information for {url}...")
                    progress_bar.progress(5)
                    
                    # Use a fallback title in case fetching info fails or title is missing
                    # This title is updated in hook_data for the progress hook
                    fetched_video_title = f"Video from {url.split('v=')[-1][:11] if 'v=' in url else 'youtu.be/' + url.split('/')[-1][:11]}"

                    try:
                        initial_info = ydl.extract_info(url, download=False)
                        fetched_video_title = initial_info.get('title', fetched_video_title)
                    except Exception as info_e:
                        status_placeholder.warning(f"Could not pre-fetch video info for {url}: {str(info_e)[:100]}. Proceeding with download attempt.")
                        # Not fatal, ydl.extract_info(download=True) will get it or fail.
                    
                    hook_data['video_title'] = fetched_video_title # Update title for progress hook

                    status_placeholder.info(f"Processing: '{hook_data['video_title']}'")
                    progress_bar.progress(10)
                    
                    processed_info = ydl.extract_info(url, download=True)
                    # Update title again from processed_info if it's more accurate (e.g., after redirects)
                    hook_data['video_title'] = processed_info.get('title', hook_data['video_title'])
                    final_mp3_path = processed_info.get('filepath')

                    if final_mp3_path and os.path.exists(final_mp3_path) and final_mp3_path.lower().endswith(".mp3"):
                        actual_filename_for_download = os.path.basename(final_mp3_path)
                        progress_bar.progress(95)
                        status_placeholder.success(f"Successfully converted: '{hook_data['video_title']}' (as {actual_filename_for_download})")

                        with open(final_mp3_path, "rb") as fp:
                            file_bytes = fp.read()
                        
                        st.session_state.download_links.append({
                            "title": hook_data['video_title'],
                            "filename": actual_filename_for_download,
                            "data": file_bytes,
                            "url": url,
                            "container": video_container
                        })
                        os.remove(final_mp3_path)
                        progress_bar.progress(100)
                    else:
                        error_detail = f"(Reported path: {final_mp3_path}, Exists: {os.path.exists(final_mp3_path) if final_mp3_path else 'N/A'}, Ends with .mp3: {final_mp3_path.lower().endswith('.mp3') if final_mp3_path else 'N/A'})"
                        status_placeholder.error(f"Conversion failed or MP3 file not found for '{hook_data['video_title']}'. {error_detail}")
                        progress_bar.progress(100)

            except yt_dlp.utils.DownloadError as e:
                err_title = hook_data['video_title'] if hook_data['video_title'] != "Unknown Video" else url
                status_placeholder.error(f"Download/Conversion error for '{err_title}': {str(e)[:300]}")
                progress_bar.progress(100)
            except Exception as e:
                err_title = hook_data['video_title'] if hook_data['video_title'] != "Unknown Video" else url
                status_placeholder.error(f"An unexpected error occurred with '{err_title}': {str(e)[:300]}")
                progress_bar.progress(100)
        
        st.session_state.processing_done = True
        if not st.session_state.download_links:
            results_container.error("No videos could be processed successfully from the valid URLs.")
        else:
            results_container.success("Processing complete! Download links are available above their respective status messages.")
            for item in st.session_state.download_links:
                item["container"].download_button(
                    label=f"\ud83d\udce5 Download {item['filename']}", # Inbox tray icon
                    data=item['data'],
                    file_name=item['filename'],
                    mime="audio/mpeg"
                )
                item["container"].caption(f"Original URL: {item['url']}")
                
    except Exception as batch_e:
        st.error(f"A critical error occurred during batch processing: {batch_e}")
    finally:
        if current_batch_temp_dir and os.path.exists(current_batch_temp_dir):
            try:
                shutil.rmtree(current_batch_temp_dir)
            except Exception as e:
                st.warning(f"Could not clean up temporary batch directory {current_batch_temp_dir}: {e}. Manual cleanup may be required.")

# --- Streamlit App UI --- 
st.set_page_config(layout="wide", page_title="YouTube to MP3 Converter")

# Custom CSS (incorporating Design System)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Poppins:wght@600&display=swap');
    body, .stApp {
        font-family: 'Inter', sans-serif;
        color: #333333; /* Dark Gray text */
        background-color: #FFFFFF; /* White background */
    }
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif;
        color: #333333; /* Dark Gray headings */
    }
    .stButton>button {
        background-color: #007BFF; /* Accent Bright Blue */
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.6em 1.2em;
        font-family: 'Inter', sans-serif;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #0056b3; /* Darker blue on hover */
    }
    .stTextArea textarea {
        background-color: #F0F0F0; /* Secondary Light Gray */
        border: 1px solid #CCCCCC; /* Neutral border */
        border-radius: 5px;
        min-height: 150px;
        font-family: 'Inter', sans-serif;
    }
    /* Alert styling for success, error, info, warning */
    .stAlert[data-baseweb="alert"] {
        border-radius: 5px;
        font-family: 'Inter', sans-serif;
    }
    .stAlert[data-baseweb="alert"] p {
         font-family: 'Inter', sans-serif; /* Ensure p inside alert also uses Inter */
    }
    /* Success: Plan: #28A745 (Green) */
    .stAlert[data-baseweb="alert"][data-testid="stSuccess"] {
        background-color: #D4EDDA; /* Light green bg */
        color: #155724; /* Dark green text */
        border: 1px solid #C3E6CB;
    }
    /* Error: Plan: #DC3545 (Red) */
    .stAlert[data-baseweb="alert"][data-testid="stError"] {
        background-color: #F8D7DA; /* Light red bg */
        color: #721C24; /* Dark red text */
        border: 1px solid #F5C6CB;
    }
    /* Info: (Derived) */
    .stAlert[data-baseweb="alert"][data-testid="stInfo"] {
        background-color: #D1ECF1; /* Light blue bg */
        color: #0C5460; /* Dark blue text */
        border: 1px solid #BEE5EB;
    }
    /* Warning: Plan: #FFC107 (Yellow) */
    .stAlert[data-baseweb="alert"][data-testid="stWarning"] {
        background-color: #FFF3CD; /* Light yellow bg */
        color: #856404; /* Dark yellow text */
        border: 1px solid #FFEEBA;
    }
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #007BFF; /* Accent Bright Blue for progress bar */
    }
</style>
""", unsafe_allow_html=True)

st.title("\u25b6\ufe0f\ud83c\udfb5 YouTube to MP3 Converter") # Play icon, musical notes icon
st.markdown("Enter one or more YouTube video URLs below (one per line) to convert them to MP3.")