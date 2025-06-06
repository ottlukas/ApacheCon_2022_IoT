#!/bin/bash

echo "Modifying zenohd_config.json5 to remove plugins section..."
cp zenohd_config.json5 zenohd_config.json5.bak
echo '{ "listen": { "endpoints": ["tcp/0.0.0.0:7447"] } }' > zenohd_config.json5
echo "New zenohd_config.json5 content:"
cat zenohd_config.json5

echo "Ensuring zenohd is (re)started with the new minimal config..."
# pkill if running, then start with setup_zenoh.sh which uses the current config
if pgrep -f zenohd-linux-x86_64 > /dev/null; then
    echo "Stopping existing zenohd..."
    pkill -f zenohd-linux-x86_64
    sleep 2
fi
# setup_zenoh.sh should now use the modified config file
# It will also reinstall dependencies, which is redundant but harmless here.
./setup_zenoh.sh
sleep 5 # Give zenohd time to start
if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
    echo "Failed to start zenohd with minimal config. Aborting."
    # Restore original config
    mv zenohd_config.json5.bak zenohd_config.json5
    exit 1
fi
echo "zenohd is running with minimal config."
echo "Initial zenohd.log with minimal config:"
head -n 50 zenohd.log # Show more initial logs

echo "Starting zenoh_producer.py in the background..."
# Producer already has fixes for key and payload, and reduced sleep time.
python zenoh_producer.py > producer_retrieve_test_producer_output.log 2>&1 &
PRODUCER_PID=$!
echo "Producer started with PID $PRODUCER_PID. Letting it run for 10 seconds..."
sleep 10

echo "Stopping producer (PID $PRODUCER_PID)..."
if kill -0 $PRODUCER_PID 2>/dev/null; then
    kill $PRODUCER_PID
    sleep 2
    if kill -0 $PRODUCER_PID 2>/dev/null; then kill -9 $PRODUCER_PID; fi
else
    echo "Producer (PID $PRODUCER_PID) already terminated."
fi
echo "Producer stopped."

echo "Running zenoh_retrieve.py (with its previous fixes)..."
# Assuming zenoh_retrieve.py has fixes from the previous extensive subtask (key, payload, optional IoTDB)
python zenoh_retrieve.py > retrieve_output.log 2>&1 &
RETRIEVE_PID=$!

# Timeout for retrieve script
TIMEOUT_SECONDS=20
SECONDS_WAITED=0
while kill -0 $RETRIEVE_PID 2>/dev/null && [ $SECONDS_WAITED -lt $TIMEOUT_SECONDS ]; do
    sleep 1
    SECONDS_WAITED=$((SECONDS_WAITED+1))
done

RETRIEVE_HUNG=false
if kill -0 $RETRIEVE_PID 2>/dev/null; then
    echo "zenoh_retrieve.py is still running after $TIMEOUT_SECONDS seconds. Killing it."
    kill -9 $RETRIEVE_PID
    RETRIEVE_HUNG=true
fi

echo "Retrieve script output:"
cat retrieve_output.log

# Restore original config before showing final logs, so setup for next subtask is clean
echo "Restoring original zenohd_config.json5..."
mv zenohd_config.json5.bak zenohd_config.json5

echo "zenohd.log after retrieve attempt (last 50 lines):"
tail -n 50 zenohd.log


if [ "$RETRIEVE_HUNG" = true ]; then
    echo "Retrieve test FAILED (Script hung and was killed)."
    exit 1
fi

if grep -q "Successfully retrieved data from Zenoh" retrieve_output.log; then
    echo "Retrieve test PASSED (Zenoh get successfully retrieved data with minimal zenohd config)."
elif grep -q "No data received from Zenoh" retrieve_output.log || grep -q "DataFrame is None and no results processed" retrieve_output.log ; then
    echo "Retrieve test FAILED (No data received from Zenoh, even with minimal config)."
    # Check zenohd logs for specific messages about 'get' or storage if this happens
    if grep -iE "storage|store|get operation" zenohd.log; then
        echo "Relevant messages found in zenohd.log regarding storage/get."
    else
        echo "No specific messages about storage/get found in zenohd.log that could explain the failure."
    fi
    exit 1
elif grep -qE "AttributeError|TypeError|KeyError|SyntaxError|ModuleNotFoundError" retrieve_output.log; then
    # Added SyntaxError and ModuleNotFoundError to the script error check
    echo "Retrieve test FAILED (Script error in zenoh_retrieve.py)."
    exit 1
else
    echo "Retrieve test FAILED (Output did not clearly indicate success or failure)."
    exit 1
fi
