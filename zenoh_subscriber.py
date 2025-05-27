"""
# TODO: Add module docstring
"""
import json
import time
import os

import zenoh

# from zenoh import ChangeKind # ChangeKind is part of the Sample object in the new API

# The listener callback receives a Sample object in Zenoh 1.x
def sample_listener(sample):
    """Callback function to process incoming Zenoh samples."""
    # sample.kind can be zenoh.SampleKind.PUT or zenoh.SampleKind.DELETE
    # sample.key_expr is the key expression
    # sample.payload is the value (bytes)
    # sample.timestamp is a zenoh.Timestamp object (with time and id)

    # Assuming the payload is a string or can be decoded to a string.
    # The producer sends an integer. Let's assume it's received as a string representation.
    payload_str = ''
    if sample.payload is not None:
        try:
            payload_str = sample.payload.decode() # Try decoding as UTF-8
        except UnicodeDecodeError:
            payload_str = str(sample.payload) # Fallback to raw string representation of bytes

    print(f">> [Subscription listener] received {sample.kind!r} for {sample.key_expr} : "
          f"{payload_str} with timestamp {sample.timestamp.time}")

if __name__ == "__main__":
    config = zenoh.Config()
    # Set mode to client
    config.insert_json5("mode", json.dumps("client"))
    # Corrected configuration key for connect endpoints
    # pylint: disable=line-too-long
    zenoh_router_endpoint = os.environ.get("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
    config.insert_json5("connect/endpoints", json.dumps([zenoh_router_endpoint]))
    # pylint: enable=line-too-long
    with zenoh.open(config) as open_session:
        subscriber = open_session.declare_subscriber('/myfactory/machine1/temp', sample_listener)
        # Keep the subscriber alive, e.g., by waiting for input or a long sleep
        # The original `time.sleep(10)` would cause the subscriber to stop after 10s.
        # For a subscriber, it usually needs to run indefinitely or until a signal.
        # I'll keep time.sleep(10) as per original, but in a real scenario, this would be different.
        time.sleep(10)
        # subscriber.close() # In Zenoh 1.x, subscriber should be closed if no longer needed,
                      # but here it's managed by the session context ending.
                      # pylint: disable=line-too-long
                      # Explicitly closing is good if you want to stop subscribing before session ends.