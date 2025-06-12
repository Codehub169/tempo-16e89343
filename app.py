import streamlit as st
import yt_dlp
import os

# Define output directory
TEMP_AUDIO_DIR = "temp_audio"

def create_temp_dir():
    """Ensures the temporary directory for audio files exists."""
    if not os.path.exists(TEMP_AUDIO_DIR):
        os.makedirs(TEMP_AUDIO_DIR)

def progress_hook(d, progress_bar, status_placeholder):
    """Hook for yt-dlp to update Streamlit UI on progress."""
    # Attempt to get the video title from the info_dict if available
    hook_video_title = d.get('info_dict', {}).get('title', 'Current video')

    if d['status'] == 'downloading':
        total_bytes_str = d.get('_total_bytes_str', 'N/A')
        speed_str = d.get('_speed_str', 'N/A')
        percent_str = d.get('_percent_str', '0%')
        # Extract numeric percentage for progress bar
        try:
            percentage = float(percent_str.replace('%', ''))
        except ValueError:
            percentage = 0
        
        # Scale download progress (0-100%) to a part of the overall progress (e.g., 10-80%)
        # Initial 10% for fetching info, final 20% for conversion buffering.
        current_progress = 10 + int(percentage * 0.7) 
        progress_bar.progress(current_progress)
        status_placeholder.info(f"Downloading '{hook_video_title}': {percent_str} of {total_bytes_str} at {speed_str}")
    elif d['status'] == 'finished':
        # This status can be for download finishing (before conversion) or postprocessing finishing.
        # If it's the end of a download before conversion, info_dict should be present.
        progress_bar.progress(85) # Download finished, moving to conversion/next step
        status_placeholder.info(f"Download of '{hook_video_title}' complete. Preparing for conversion...")
    elif d['status'] == 'error':
        status_placeholder.warning(f"Error reported by yt-dlp during processing of '{hook_video_title}'.")

def process_videos(urls):
    """Processes a list of URLs: downloads, converts, and prepares for download."""
    st.session_state.download_links = []  # Reset for new batch
    st.session_state.processing_done = False
    
    if not urls:
        st.warning("Please enter at least one YouTube URL.")
        return

    url_list = [url.strip() for url in urls.splitlines() if url.strip()]
    if not url_list:
        st.warning("No valid URLs found. Please check your input.")
        return

    results_container = st.container()

    for i, url in enumerate(url_list):
        video_container = results_container.container()
        video_container.markdown(f"---")
        status_placeholder = video_container.empty()
        progress_bar = video_container.progress(0)
        
        status_placeholder.info(f"Preparing to process URL: {url}")
        video_title = f"Video {i+1}" # Default title before fetching info

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',  # Standard quality
            }],
            'outtmpl': os.path.join(TEMP_AUDIO_DIR, '%(title)s.%(ext)s'),
            'noplaylist': True, # Process only single video if playlist URL is given
            'quiet': True,      # Suppress yt-dlp console output
            'no_warnings': True,
            'progress_hooks': [lambda d_hook: progress_hook(d_hook, progress_bar, status_placeholder)],
            'ffmpeg_location': '/usr/bin/ffmpeg' # Explicit path, good for containers
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                status_placeholder.info(f"Fetching video information for {url}...")
                progress_bar.progress(5)
                
                try:
                    initial_info = ydl.extract_info(url, download=False)
                    video_title = initial_info.get('title', f'Video {i+1}') # Use actual title or a placeholder
                except Exception as info_e:
                    status_placeholder.error(f"Failed to fetch initial info for {url}: {str(info_e)[:200]}")
                    progress_bar.progress(100) # Mark as done with error
                    continue # Skip this URL

                status_placeholder.info(f"Processing: '{video_title}'")
                progress_bar.progress(10)
                
                processed_info = ydl.extract_info(url, download=True)
                
                final_mp3_path = processed_info.get('filepath')
                if not final_mp3_path and processed_info.get('ext') == 'mp3': # Fallback for some cases
                    final_mp3_path = ydl.prepare_filename(processed_info).replace(processed_info['ext'], 'mp3')

                if final_mp3_path and os.path.exists(final_mp3_path) and final_mp3_path.endswith(".mp3"):
                    actual_filename_for_download = os.path.basename(final_mp3_path)
                    progress_bar.progress(95)
                    status_placeholder.success(f"Successfully converted: '{video_title}' (as {actual_filename_for_download})")

                    with open(final_mp3_path, "rb") as fp:
                        file_bytes = fp.read()
                    
                    st.session_state.download_links.append({
                        "title": video_title,
                        "filename": actual_filename_for_download,
                        "data": file_bytes,
                        "url": url,
                        "container": video_container # Store container to place download button later
                    })
                    os.remove(final_mp3_path) # Clean up the file
                    progress_bar.progress(100)
                else:
                    error_detail_path = final_mp3_path if final_mp3_path else "Not available"
                    error_detail_exists = os.path.exists(final_mp3_path) if final_mp3_path else False
                    error_detail_ext = final_mp3_path.endswith('.mp3') if final_mp3_path else False
                    error_detail = f"(Reported path: {error_detail_path}, Exists: {error_detail_exists}, Ends with .mp3: {error_detail_ext})"
                    status_placeholder.error(f"Conversion failed or MP3 file not found for '{video_title}'. {error_detail}")
                    progress_bar.progress(100) # Mark as done with error

        except yt_dlp.utils.DownloadError as e:
            status_placeholder.error(f"Download/Conversion error for '{video_title}': {str(e)[:300]}") # Limit error message length
            progress_bar.progress(100)
        except Exception as e:
            status_placeholder.error(f"An unexpected error occurred with '{video_title}': {str(e)[:300]}")
            progress_bar.progress(100)
    
    st.session_state.processing_done = True
    if not st.session_state.download_links:
        results_container.error("No videos could be processed successfully.")
    else:
        results_container.success("All selected videos processed! See download links above each status message.")
        # Display download buttons in their respective containers
        for item in st.session_state.download_links:
            item["container"].download_button(
                label=f"omagnetic_download Download {item['filename']}",
                data=item['data'],
                file_name=item['filename'],
                mime="audio/mpeg"
            )
            item["container"].caption(f"Original URL: {item['url']}")

# --- Streamlit App UI --- 
st.set_page_config(layout="wide", page_title="YouTube to MP3 Converter", theme="light")

# Custom CSS (incorporating Design System)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Poppins:wght@600&display=swap');
    body, .stApp {
        font-family: 'Inter', sans-serif;
        /* color: #333333; */ /* Default theme will handle text color */
        /* background-color: #FFFFFF; */ /* Default theme will handle background */
    }
    h1, h2, h3 {
        font-family: 'Poppins', sans-serif;
        /* color: #333333; */ /* Default theme */
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
    /* Light theme might handle these well, but custom styles can ensure consistency */
    .stAlert[data-baseweb="alert"] {
        border-radius: 5px;
        font-family: 'Inter', sans-serif;
    }
    .stAlert[data-baseweb="alert"] p {
         font-family: 'Inter', sans-serif; /* Ensure p inside alert also uses Inter */
    }
    /* Success: Plan: #28A745 (Green) */
    .stAlert[data-baseweb="alert"][data-testid="stSuccess"] {
        background-color: #D4EDDA;
        color: #155724;
        border: 1px solid #C3E6CB;
    }
    /* Error: Plan: #DC3545 (Red) */
    .stAlert[data-baseweb="alert"][data-testid="stError"] {
        background-color: #F8D7DA;
        color: #721C24;
        border: 1px solid #F5C6CB;
    }
    /* Info: (Derived) */
    .stAlert[data-baseweb="alert"][data-testid="stInfo"] {
        background-color: #D1ECF1;
        color: #0C5460;
        border: 1px solid #BEE5EB;
    }
    /* Warning: Plan: #FFC107 (Yellow) */
    .stAlert[data-baseweb="alert"][data-testid="stWarning"] {
        background-color: #FFF3CD;
        color: #856404;
        border: 1px solid #FFEEBA;
    }
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #007BFF; /* Accent Bright Blue for progress bar */
    }
</style>
""", unsafe_allow_html=True)

st.title("	eleporterightarrow_button		 Tune YouTube to MP3 Converter")
st.markdown("Convert YouTube videos to MP3 audio files. Paste video links below (one per line) and click convert.")

create_temp_dir() # Ensure temp directory exists on app start/rerun

urls_input = st.text_area("YouTube Video URL(s):", height=150, placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ\nhttps://www.youtube.com/watch?v=anotherVideoID")

# Initialize session state variables if they don't exist
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False
if 'download_links' not in st.session_state:
    st.session_state.download_links = []

if st.button("			 Link Convert to MP3", key="convert_button"):
    # Clear previous results shown on page (placeholders will be reused)
    # The process_videos function will now populate new results within its own containers.
    st.session_state.download_links = [] # Reset links
    st.session_state.processing_done = False # Reset flag
    process_videos(urls_input)

# Note: Download buttons are now added dynamically within process_videos
# to their respective containers. This avoids issues with Streamlit's rerun behavior
# and stale button states if they were all displayed at the end based on session_state alone.

st.markdown("""
---
<p style='text-align: center; color: #888888; font-size: 0.9em;'>
    Built with Streamlit & yt-dlp. For personal, non-commercial use only. 
    Respect copyright laws.
</p>
""", unsafe_allow_html=True)
