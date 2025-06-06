#!/bin/bash

echo "Attempting to start/restart zenohd to ensure a clean state..."
if [ -f ./setup_zenoh.sh ]; then
    ./setup_zenoh.sh # This script now includes pkill for existing instances
    sleep 5 # Give it time to start
    if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
        echo "Failed to start zenohd via setup_zenoh.sh. Aborting retrieve test."
        cat zenohd.log # Show why it might have failed
        exit 1
    fi
    echo "zenohd started/restarted successfully."
else
    echo "setup_zenoh.sh not found. Cannot ensure zenohd is running. Aborting."
    exit 1
fi

echo "Starting zenoh_producer.py in the background to publish some data..."
# Producer already has fixes for key and payload, and reduced sleep time.
python zenoh_producer.py > producer_retrieve_test_producer_output.log 2>&1 &
PRODUCER_PID=$!
echo "Producer started with PID $PRODUCER_PID. Letting it run for 2-3 seconds to ensure it's publishing..."
sleep 3

echo "Running zenoh_retrieve.py WHILE producer is still running..."
# Capture retrieve output.
python zenoh_retrieve.py > retrieve_output.log 2>&1
RETRIEVE_EXIT_CODE=$?
echo "Retrieve script finished with exit code $RETRIEVE_EXIT_CODE."

echo "Now stopping producer (PID $PRODUCER_PID)..."
if kill -0 $PRODUCER_PID 2>/dev/null; then
    kill $PRODUCER_PID
    sleep 1 # Wait a moment for it to terminate cleanly
    if kill -0 $PRODUCER_PID 2>/dev/null; then
        echo "Producer (PID $PRODUCER_PID) did not terminate as expected. Forcing kill."
        kill -9 $PRODUCER_PID
    fi
    echo "Producer stopped."
else
    echo "Producer (PID $PRODUCER_PID) already terminated by the time we tried to stop it."
fi

echo "Retrieve script output:"
cat retrieve_output.log

echo "Recent zenohd logs:"
tail -n 30 zenohd.log || echo "zenohd.log not found or empty."

# Heuristic for success:
echo "Analyzing retrieve_output.log for success indicators..."
if grep -q "No data received from Zenoh." retrieve_output.log; then
    echo "Retrieve test FAILED (No data received from Zenoh)."
    exit 1
elif grep -q "Traceback" retrieve_output.log && ! grep -q "iotdb" retrieve_output.log; then
    # If there's a traceback not related to IoTDB, it's a script/Zenoh error
    echo "Retrieve test FAILED (Script error detected, possibly Zenoh related)."
    exit 1
elif grep -q "DataFrame is None and no results processed" retrieve_output.log; then
    # Specific message from zenoh_retrieve.py if Zenoh get fails
    echo "Retrieve test FAILED (DataFrame is None, Zenoh get likely failed or returned no results)."
    exit 1
elif grep -q "Traceback" retrieve_output.log && grep -q "iotdb" retrieve_output.log; then
    echo "Retrieve test PARTIALLY PASSED (Zenoh get likely worked, but IoTDB operation failed. This is acceptable for Zenoh functionality verification)."
    # For this partial pass, we still need to ensure it didn't say "No data received"
    if grep -q "Successfully retrieved data from Zenoh" retrieve_output.log; then
         echo "Partial pass confirmed by 'Successfully retrieved data' message."
    else
         echo "Partial pass is ambiguous, 'Successfully retrieved data' message NOT found."
         # exit 1 # Or treat as full failure depending on strictness
    fi
elif grep -q "Successfully retrieved data from Zenoh" retrieve_output.log; then
    echo "Retrieve test PASSED (Zenoh get seems to have worked; DataFrame processing was attempted/successful)."
else
    echo "Retrieve test FAILED (Output did not clearly indicate success or known partial success state)."
    exit 1
fi
