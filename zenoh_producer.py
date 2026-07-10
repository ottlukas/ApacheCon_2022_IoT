#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zenoh telemetry producer (sensor simulator) for educational demonstration.

Simulates sensor telemetry readings and publishes them to a Zenoh key.
Compatible with the Zenoh-to-IoTDB bridge and the Panel dashboard.
"""

import os
import sys
import json
import random
import time
import argparse
import logging
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import zenoh
from app import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("zenoh_producer")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Zenoh Telemetry Producer (Sensor Simulator)")
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
        help="Zenoh key expression to publish to"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Publishing interval in seconds"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "raw"],
        default="json",
        help="Payload format (json or raw float)"
    )
    return parser.parse_args()

def generate_sensor_data() -> dict:
    """Generate mock temperature sensor reading."""
    val = round(random.uniform(18.0, 32.0), 2)
    return {
        "sensor_id": "machine1-temperature",
        "device": "machine1",
        "measurement": "temperature",
        "value": val,
        "unit": "celsius",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def main():
    args = parse_args()
    logger.info("Starting Zenoh telemetry producer...")
    
    # Configure Zenoh Session
    conf_dict = {
        "mode": "client",
        "connect": {"endpoints": [args.endpoint]}
    }
    z_config = zenoh.Config.from_json5(json.dumps(conf_dict))
    
    logger.info("Connecting to Zenoh router at: %s", args.endpoint)
    try:
        session = zenoh.open(z_config)
        logger.info("Session opened successfully. Key Expression: '%s'", args.key)
        
        print(f"\nPublishing simulated temperature values to '{args.key}' every {args.interval}s...")
        print("Press CTRL+C to exit.\n")
        
        while True:
            data = generate_sensor_data()
            if args.format == "json":
                payload = json.dumps(data)
            else:
                payload = str(data["value"])
                
            session.put(args.key, payload)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Published: {payload}", flush=True)
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping producer...")
    except Exception as exc:
        logger.error("An error occurred in producer: %s", exc)
        sys.exit(1)
    finally:
        logger.info("Zenoh session closed.")

if __name__ == "__main__":
    main()
