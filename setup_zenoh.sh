#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Checking/Installing eclipse-zenoh==1.3.4..."
pip install eclipse-zenoh==1.3.4

echo "Checking/Installing IoTDB Python client (attempting 'iotdb')..."
pip install iotdb || echo "Failed to install 'iotdb' package. Continuing without it."
echo "Checking/Installing pandas..."
pip install pandas

echo "Setting up zenohd router..."
ZENOHD_TARGET_FILENAME="zenohd-linux-x86_64" # Local name for the binary
ZENOHD_DOWNLOAD_URL="https_LATEST_ZENOHD_URL_PLACEHOLDER" # Placeholder

# Define the Zenohd version and archive name based on observed latest
ZENOHD_VERSION="1.4.0" # Assuming this is the latest stable, adjust if needed
ZENOHD_ARCHIVE_TYPE="x86_64-unknown-linux-gnu-standalone"
ZENOHD_ARCHIVE_FILENAME="zenoh-${ZENOHD_VERSION}-${ZENOHD_ARCHIVE_TYPE}.zip"
ACTUAL_DOWNLOAD_URL="https://download.eclipse.org/zenoh/zenoh/latest/${ZENOHD_ARCHIVE_FILENAME}"

echo "Downloading Zenoh router archive from $ACTUAL_DOWNLOAD_URL ..."
curl -L --fail "$ACTUAL_DOWNLOAD_URL" -o "$ZENOHD_ARCHIVE_FILENAME"

if [ ! -s "$ZENOHD_ARCHIVE_FILENAME" ]; then
    echo "Failed to download or downloaded an empty file: $ZENOHD_ARCHIVE_FILENAME using $ACTUAL_DOWNLOAD_URL."
    exit 1
fi
echo "Downloaded $ZENOHD_ARCHIVE_FILENAME successfully."

echo "Installing unzip..."
sudo apt-get update && sudo apt-get install -y unzip

echo "Unzipping $ZENOHD_ARCHIVE_FILENAME..."
# Unzip, expecting 'zenohd' binary. Overwrite if exists.
# The actual binary inside might just be 'zenohd'.
unzip -o "$ZENOHD_ARCHIVE_FILENAME" zenohd -d . || (echo "Failed to unzip zenohd. Trying to extract 'bin/zenohd'..." && unzip -o "$ZENOHD_ARCHIVE_FILENAME" bin/zenohd -d . && mv bin/zenohd .)

# Check if zenohd was extracted and move it to the target filename if necessary
if [ -f "zenohd" ]; then
    echo "Found 'zenohd' binary."
    # If ZENOHD_TARGET_FILENAME is different from 'zenohd', move it
    if [ "zenohd" != "$ZENOHD_TARGET_FILENAME" ]; then
        mv zenohd "$ZENOHD_TARGET_FILENAME"
        echo "Moved 'zenohd' to '$ZENOHD_TARGET_FILENAME'."
    fi
elif [ ! -f "$ZENOHD_TARGET_FILENAME" ]; then
    echo "ERROR: 'zenohd' binary not found after unzipping."
    ls -l # List files to see what was extracted
    exit 1
fi


chmod +x "$ZENOHD_TARGET_FILENAME"
echo "Made $ZENOHD_TARGET_FILENAME executable."
rm "$ZENOHD_ARCHIVE_FILENAME" # Clean up the zip file

# Verify the downloaded binary
echo "Verifying zenohd binary type:"
file "$ZENOHD_TARGET_FILENAME"
echo "Attempting to get zenohd version:"
./"$ZENOHD_TARGET_FILENAME" --version || echo "Getting version failed, but this might be okay for some zenohd versions."


echo "Starting $ZENOHD_TARGET_FILENAME with configuration zenohd_config.json5..."
# Attempt to kill any existing zenohd processes to free up the port
echo "Attempting to stop any existing zenohd processes..."
pkill -f zenohd-linux-x86_64 && echo "Killed existing zenohd process(es)." || echo "No existing zenohd process found or pkill failed."
sleep 1 # Give a moment for the process to terminate

# Clear previous log
> zenohd.log
./"$ZENOHD_TARGET_FILENAME" --config zenohd_config.json5 > zenohd.log 2>&1 &
ROUTER_PID=$!
echo "$ZENOHD_TARGET_FILENAME process started with PID $ROUTER_PID."

sleep 5 # Give it a moment to start up

if kill -0 $ROUTER_PID 2>/dev/null; then
    echo "$ZENOHD_TARGET_FILENAME (PID $ROUTER_PID) is running."
    echo "Recent $ZENOHD_TARGET_FILENAME logs (first 20 lines):"
    head -n 20 zenohd.log
else
    echo "Failed to start or keep $ZENOHD_TARGET_FILENAME running."
    echo "$ZENOHD_TARGET_FILENAME log contents:"
    cat zenohd.log
    exit 1
fi
