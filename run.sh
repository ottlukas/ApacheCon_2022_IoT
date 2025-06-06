#!/bin/bash

# Ensure Zenoh library is installed
echo "Checking/Installing eclipse-zenoh==1.3.4..."
pip install eclipse-zenoh==1.3.4

# Ensure zenohd is available and executable
echo "Setting up zenohd router..."
if [ ! -f zenohd-linux-x86_64 ]; then
    echo "zenohd-linux-x86_64 not found. Please ensure it is in the root directory."
    exit 1
fi
chmod +x zenohd-linux-x86_64

# Start zenohd router in the background
echo "Starting zenohd router with configuration zenohd_config.json5..."
./zenohd-linux-x86_64 --config zenohd_config.json5 &
# Give it a moment to start up
sleep 3

# Check if zenohd is running
if pgrep -f zenohd-linux-x86_64 > /dev/null; then
    echo "zenohd router started successfully."
    echo "zenohd logs (if any immediately available):"
    cat zenohd.log || echo "zenohd.log not found or empty."
else
    echo "Failed to start zenohd router."
    echo "zenohd.log contents:"
    cat zenohd.log || echo "zenohd.log not found or empty."
    exit 1
fi
