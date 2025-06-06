#!/bin/bash

echo "Ensuring zenohd is running..."
if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
    echo "zenohd is not running. Attempting to restart it..."
    if [ -f ./setup_zenoh.sh ]; then
        ./setup_zenoh.sh
        sleep 5 # Give it time to start
        if ! pgrep -f zenohd-linux-x86_64 > /dev/null; then
            echo "Failed to start zenohd. Aborting subscriber test."
            exit 1
        fi
        echo "zenohd started successfully."
    else
        echo "setup_zenoh.sh not found. Cannot start zenohd. Aborting."
        exit 1
    fi
else
    echo "zenohd is running."
fi

echo "Starting zenoh_producer.py in the background..."
# Use the modified zenoh_producer.py (sleep time 0.5s, corrected key & payload)
python zenoh_producer.py > producer_subscriber_test_producer_output.log 2>&1 &
PRODUCER_PID=$!
echo "Producer started with PID $PRODUCER_PID."
sleep 2 # Give producer a moment to start publishing

echo "Running zenoh_subscriber.py..."
# Capture subscriber output. It should run for a predefined time or be killed.
# Based on typical subscriber patterns, it might run until manually stopped.
# The prompt implies it runs for 10 seconds, which means zenoh_subscriber.py must have this logic.
# Let's assume it has a 10-second run time.
python zenoh_subscriber.py > subscriber_output.log 2>&1
SUBSCRIBER_EXIT_CODE=$?
echo "Subscriber finished with exit code $SUBSCRIBER_EXIT_CODE."

echo "Stopping producer (PID $PRODUCER_PID)..."
# Check if producer is still running before trying to kill
if kill -0 $PRODUCER_PID 2>/dev/null; then
    kill $PRODUCER_PID
    sleep 2 # Wait a moment for it to terminate cleanly
    if kill -0 $PRODUCER_PID 2>/dev/null; then
        echo "Producer (PID $PRODUCER_PID) did not terminate as expected. Forcing kill."
        kill -9 $PRODUCER_PID
    fi
else
    echo "Producer (PID $PRODUCER_PID) already terminated."
fi

echo "Subscriber output:"
cat subscriber_output.log

echo "Recent zenohd logs:"
tail -n 30 zenohd.log || echo "zenohd.log not found or empty."

# Heuristic for success: subscriber_output.log should contain "received" messages
# and the payload that the producer sent.
if grep -q ">> \[Subscription listener\] received" subscriber_output.log && grep -qE ": [0-9]+" subscriber_output.log; then
    echo "Subscriber test PASSED (received messages with numeric payload)."
else
    echo "Subscriber test FAILED (did not receive expected messages or correct payload)."
    echo "Producer output during this test:"
    cat producer_subscriber_test_producer_output.log
    exit 1
fi
