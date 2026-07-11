# -*- coding: utf-8 -*-
"""Sensor telemetry simulator.

Runs locally and publishes simulated telemetry values to Zenoh.
"""

import os
import sys
import json
import random
import time
import argparse
import logging
import signal
from datetime import datetime, timezone

# Add project root to sys.path to allow importing app package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import config
from app.zenoh_client import ZenohClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sensor_simulator")

# Global variables
running = True
client = ZenohClient()


def handle_shutdown(signum, frame):
    """Handle termination signals gracefully."""
    global running
    logger.info("Shutdown signal received. Exiting simulator...")
    running = False


# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def generate_reading(device: str, measurement: str, min_val: float, max_val: float, fixed_val: float = None) -> dict:
    """Generate a single random telemetry reading.

    Args:
        device: Device ID string
        measurement: Measurement type string
        min_val: Minimum range value
        max_val: Maximum range value
        fixed_val: When provided, every reading emits this exact value instead
            of a random one (used by deterministic integration tests).

    Returns:
        Dictionary payload conforming to SensorReading schema.
    """
    value = round(fixed_val, 2) if fixed_val is not None else round(random.uniform(min_val, max_val), 2)
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "sensor_id": f"{device}-{measurement}",
        "device": device,
        "measurement": measurement,
        "value": value,
        "unit": "celsius",
        "timestamp": timestamp
    }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Simulate sensor readings and publish them to Zenoh."
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=config.ZENOH_HOST_ENDPOINT,
        help=f"Zenoh router TCP endpoint (default: {config.ZENOH_HOST_ENDPOINT})"
    )
    parser.add_argument(
        "--key",
        type=str,
        default=config.ZENOH_KEY_EXPRESSION,
        help=f"Zenoh key expression to publish to (default: {config.ZENOH_KEY_EXPRESSION})"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=config.SIMULATOR_INTERVAL_SECONDS,
        help=f"Publish interval in seconds (default: {config.SIMULATOR_INTERVAL_SECONDS})"
    )
    parser.add_argument(
        "--min",
        type=float,
        default=config.SIMULATOR_MIN_VALUE,
        help=f"Minimum temperature value (default: {config.SIMULATOR_MIN_VALUE})"
    )
    parser.add_argument(
        "--max",
        type=float,
        default=config.SIMULATOR_MAX_VALUE,
        help=f"Maximum temperature value (default: {config.SIMULATOR_MAX_VALUE})"
    )
    parser.add_argument(
        "--device",
        type=str,
        default=config.IOTDB_DEVICE.split(".")[-1],
        help="Device name (default derived from IOTDB_DEVICE)"
    )
    parser.add_argument(
        "--measurement",
        type=str,
        default=config.IOTDB_MEASUREMENT,
        help=f"Measurement name (default: {config.IOTDB_MEASUREMENT})"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publish a single reading and exit immediately (useful for testing)"
    )
    parser.add_argument(
        "--value",
        type=float,
        default=None,
        help="Emit a fixed value on every reading (instead of a random one). "
             "Useful for deterministic integration tests."
    )
    return parser.parse_args()


def main():
    """Main entrypoint for simulator execution."""
    args = parse_args()

    logger.info("Initializing simulator...")
    logger.info("Connecting to Zenoh broker at: %s", args.endpoint)

    if not client.connect(peer=args.endpoint):
        logger.error("Failed to connect to Zenoh broker. Exiting.")
        sys.exit(1)

    logger.info("Connected to Zenoh successfully.")

    if args.once:
        # Generate and publish single reading
        reading = generate_reading(args.device, args.measurement, args.min, args.max, args.value)
        payload = json.dumps(reading)
        logger.info("Publishing single reading: %s", payload)
        success = client.publish(args.key, payload)
        if success:
            logger.info("Telemetry successfully published.")
        else:
            logger.error("Failed to publish telemetry.")
        client.close()
        sys.exit(0 if success else 1)

    logger.info(
        "Starting simulation loop (Key: %s, Interval: %ss, Range: [%s, %s]). Press CTRL+C to stop.",
        args.key,
        args.interval,
        args.min,
        args.max
    )

    try:
        while running:
            reading = generate_reading(args.device, args.measurement, args.min, args.max, args.value)
            payload = json.dumps(reading)
            
            # Print friendly console log as requested by user ("except for CLI-friendly simulator status messages")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Simulated {reading['device']}.{reading['measurement']} = {reading['value']} {reading['unit']}", flush=True)
            
            client.publish(args.key, payload)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Closing Zenoh client session...")
        client.close()
        logger.info("Simulator stopped.")


if __name__ == "__main__":
    main()
