import zenoh
import json
# from zenoh import ChangeKind # ChangeKind is part of the Sample object in the new API
import time

# The listener callback receives a Sample object in Zenoh 1.x
def listener(sample):
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

    print(">> [Subscription listener] received {:?} for {} : {} with timestamp {}"
          .format(sample.kind, sample.key_expr, payload_str, sample.timestamp.time))

if __name__ == "__main__":
    conf = zenoh.Config()
    conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(["tcp/127.0.0.1:7447"]))
    with zenoh.open(conf) as session:
        sub = session.declare_subscriber('/myfactory/machine1/temp', listener)
        # Keep the subscriber alive, e.g., by waiting for input or a long sleep
        # The original `time.sleep(10)` would cause the subscriber to stop after 10s.
        # For a subscriber, it usually needs to run indefinitely or until a signal.
        # I'll keep time.sleep(10) as per original, but in a real scenario, this would be different.
        time.sleep(10) 
        # sub.close() # In Zenoh 1.x, subscriber should be closed if no longer needed,
                      # but here it's managed by the session context ending.
                      # Explicitly closing is good if you want to stop subscribing before session ends.
