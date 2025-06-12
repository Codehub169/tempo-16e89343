#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Update package list and install ffmpeg (required by yt-dlp for audio conversion)
echo "Updating package list and installing ffmpeg..."
if ! (apt-get update -y && apt-get install -y ffmpeg); then
    echo "ERROR: Failed to update package list or install ffmpeg."
    echo "ffmpeg is a critical dependency for audio conversion."
    echo "Please check your internet connection, permissions, and package manager logs."
    exit 1
fi
echo "ffmpeg installed successfully."

# Install Python dependencies from requirements.txt
echo "Installing Python dependencies from requirements.txt..."
if ! pip install --no-cache-dir -r requirements.txt; then
    echo "Failed to install Python dependencies from requirements.txt."
    exit 1
fi
echo "Python dependencies installed successfully."

# Create the temporary directory for audio files if it doesn't exist.
# The application also does this, but it's good practice for a startup script.
APP_TEMP_DIR="temp_audio"
echo "Ensuring temporary directory '$APP_TEMP_DIR' exists..."
mkdir -p "$APP_TEMP_DIR"

# Run the Streamlit application
echo "Starting Streamlit application on port 9000..."
streamlit run app.py --server.port 9000 --server.headless true --server.enableCORS false --server.enableXsrfProtection false
