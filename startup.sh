#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Update package list and install ffmpeg (required by yt-dlp for audio conversion)
echo "Updating package list and installing ffmpeg..."
if apt-get update -y && apt-get install -y ffmpeg; then
    echo "ffmpeg installed successfully."
else
    echo "Failed to install ffmpeg. Please ensure you have permissions and an internet connection."
    echo "ffmpeg is required for audio conversion."
    exit 1 
fi

# Install Python dependencies from requirements.txt
echo "Installing Python dependencies from requirements.txt..."
if pip install --no-cache-dir -r requirements.txt; then
    echo "Python dependencies installed successfully."
else
    echo "Failed to install Python dependencies."
    exit 1
fi

# Create the temporary directory for audio files if it doesn't exist.
# The application also does this, but it's good practice for a startup script.
# This should match BASE_TEMP_AUDIO_DIR in app.py
APP_BASE_TEMP_DIR="temp_audio_batches"
echo "Ensuring base temporary directory '$APP_BASE_TEMP_DIR' exists..."
mkdir -p "$APP_BASE_TEMP_DIR"

# Run the Streamlit application
echo "Starting Streamlit application on port 9000..."
streamlit run app.py --server.port 9000 --server.headless true --server.enableCORS false --server.enableXsrfProtection false
