#!/bin/bash
# set -e # Removed to allow checking producer status more flexibly

# Ensure zenohd is running
if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
    echo "zenohd is not running. Attempting to start it..."
    if [ -f ./setup_zenoh.sh ]; then
        ./setup_zenoh.sh
        sleep 5 # Give it a moment to fully start
        if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
            echo "Failed to start zenohd. Aborting producer test."
            exit 1
        fi
        echo "zenohd started successfully."
    else
        echo "setup_zenoh.sh not found. Cannot start zenohd. Aborting."
        exit 1
    fi
else
    echo "zenohd is already running."
fi

echo "Running zenoh_producer.py..."
# Run the producer in the background, save its PID, let it run for a bit, then kill it.
# Capture its output to a file.
python zenoh_producer.py > producer_output.log 2>&1 &
PRODUCER_PID=$!

echo "Producer started with PID $PRODUCER_PID. Waiting for 20 seconds..."
sleep 20

echo "Stopping producer..."
kill $PRODUCER_PID
# Wait a moment for it to terminate cleanly
sleep 2

# Check if the producer process is still running (it shouldn't be)
if kill -0 $PRODUCER_PID 2>/dev/null; then
    echo "Producer (PID $PRODUCER_PID) did not terminate as expected. Forcing kill."
    kill -9 $PRODUCER_PID
fi

echo "Producer output:"
cat producer_output.log

echo "Checking relevant zenohd logs..."
# Grep for session messages or errors that might relate to the producer.
# The producer connects from some IP/port to the router's 7447.
# Look for "new session" or "error" or the producer's IP if known (likely 127.0.0.1).
if grep -E -i "New session|Accepted|ERROR|WARN|127.0.0.1" zenohd.log; then
    echo "--- End of relevant zenohd logs ---"
else
    echo "No specific session messages/errors found in zenohd.log for producer, which might be normal if logging is minimal on success."
fi

# Heuristic for success: producer_output.log should contain numbers (the temperatures)
# This regex matches lines that ONLY contain a number (integer or float)
if grep -qE '^-?[0-9]+(\.[0-9]+)?$' producer_output.log; then
    echo "Producer test PASSED (produced numeric output)."
else
    echo "Producer test FAILED (did not produce expected numeric output)."
    exit 1
fi
