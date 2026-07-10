#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zenoh telemetry subscriber for educational demonstration.

Subscribes to a Zenoh key expression and prints received telemetry payloads to the terminal.
"""

import os
import sys
import json
import argparse
import logging
import time

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import zenoh
from app import config
from app.zenoh_client import decode_payload

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("zenoh_subscriber")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Zenoh Telemetry Subscriber")
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("ZENOH_HOST_ENDPOINT", config.ZENOH_HOST_ENDPOINT),
        help="Zenoh router TCP endpoint"
    )
    parser.add_argument(
        "--key",
        type=str,
        default=os.getenv("ZENOH_KEY_EXPRESSION", config.ZENOH_KEY_EXPRESSION),
        help="Zenoh key expression to subscribe to"
    )
    return parser.parse_args()

def sample_listener(sample):
    """Callback function to process incoming Zenoh samples."""
    payload_str = decode_payload(sample)
    if payload_str is None:
        payload_str = "[Null/Empty Payload]"
    
    print(f">> [Subscription listener] received sample on '{sample.key_expr}':")
    print(f"   Payload: {payload_str}")
    if sample.timestamp is not None:
        print(f"   Timestamp: {sample.timestamp}")
    print("-" * 50)

def main():
    args = parse_args()
    logger.info("Starting Zenoh subscriber...")
    
    # Configure Zenoh Session
    conf_dict = {
        "mode": "client",
        "connect": {"endpoints": [args.endpoint]}
    }
    z_config = zenoh.Config.from_json5(json.dumps(conf_dict))
    
    logger.info("Connecting to Zenoh router at: %s", args.endpoint)
    try:
        with zenoh.open(z_config) as session:
            logger.info("Declaring subscriber on key expression: '%s'", args.key)
            subscriber = session.declare_subscriber(args.key, sample_listener)
            
            print(f"\nListening to Zenoh key expression '{args.key}'...")
            print("Press CTRL+C to stop.\n")
            
            # Keep the main thread alive while listening
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("Stopping subscriber...")
    except Exception as exc:
        logger.error("An error occurred in subscriber: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()
