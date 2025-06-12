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
    # Optionally, exit if ffmpeg is critical and installation fails, 
    # but for some environments, it might be pre-installed or handled differently.
    # exit 1 
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
APP_TEMP_DIR="temp_audio"
echo "Ensuring temporary directory '$APP_TEMP_DIR' exists..."
mkdir -p "$APP_TEMP_DIR"

# Run the Streamlit application
echo "Starting Streamlit application on port 9000..."
streamlit run app.py --server.port 9000 --server.headless true --server.enableCORS false --server.enableXsrfProtection false
