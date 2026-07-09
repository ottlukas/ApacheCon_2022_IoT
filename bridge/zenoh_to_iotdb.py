# -*- coding: utf-8 -*-
"""Zenoh-to-IoTDB Bridge service.

Actively subscribes to Zenoh telemetry data and persists it in Apache IoTDB.
"""

import sys
import json
import logging
import time
import signal
from datetime import datetime, timezone

from app import config
from app.zenoh_client import ZenohClient
from app.iotdb_client import IoTDBClient
from app.models import SensorReading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("zenoh_to_iotdb_bridge")

# Global instances
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()
running = True


def handle_shutdown(signum, frame):
    """Gracefully handle shutdown signals."""
    global running
    logger.info("Shutdown signal received. Stopping bridge...")
    running = False


# Register signals
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def sample_callback(sample):
    """Callback for Zenoh subscription messages."""
    if sample.payload is None:
        logger.warning("Received Zenoh sample with null payload")
        return

    try:
        payload_bytes = bytes(sample.payload)
        payload_str = payload_bytes.decode("utf-8")
        logger.debug("Received payload: %s", payload_str)

        # Parse JSON
        data = json.loads(payload_str)

        # Validate with Pydantic model
        reading = SensorReading(**data)

        # Extract values
        timestamp = reading.timestamp
        value = reading.value

        # Fallback to current UTC time if timestamp is missing or empty
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Bridging value to IoTDB - Device: %s, Measurement: %s, Value: %s, Timestamp: %s",
            reading.device,
            reading.measurement,
            value,
            timestamp
        )

        # Insert to IoTDB
        success = iotdb_client.insert_temperature(timestamp, value)
        if not success:
            logger.error("Failed to insert telemetry into IoTDB")

    except json.JSONDecodeError as jde:
        logger.error("Failed to decode JSON from Zenoh payload: %s", jde)
    except Exception as e:
        logger.error("Error processing incoming Zenoh message: %s", e)


def connect_services(max_retries: int = 20, delay: float = 3.0) -> bool:
    """Connect to Zenoh and IoTDB with retry/backoff logic.

    Args:
        max_retries: Maximum connection attempts
        delay: Sleep duration between attempts

    Returns:
        True if all connections succeeded and schema initialized, False otherwise
    """
    global running

    # Try connecting to Zenoh
    retries = 0
    while running and not zenoh_client.is_connected():
        logger.info(
            "Attempting connection to Zenoh at %s (attempt %d/%d)...",
            config.ZENOH_ENDPOINT,
            retries + 1,
            max_retries
        )
        if zenoh_client.connect(peer=config.ZENOH_ENDPOINT):
            break
        retries += 1
        if retries >= max_retries:
            logger.error("Could not connect to Zenoh after maximum retries.")
            return False
        time.sleep(delay)

    # Try connecting to IoTDB
    retries = 0
    while running and not iotdb_client.is_connected():
        logger.info(
            "Attempting connection to IoTDB at %s:%d (attempt %d/%d)...",
            config.IOTDB_HOST,
            config.IOTDB_PORT,
            retries + 1,
            max_retries
        )
        if iotdb_client.connect():
            break
        retries += 1
        if retries >= max_retries:
            logger.error("Could not connect to IoTDB after maximum retries.")
            return False
        time.sleep(delay)

    # Initialize Schema on IoTDB
    if running and iotdb_client.is_connected():
        logger.info("Initializing IoTDB schema...")
        if not iotdb_client.initialize_schema():
            logger.error("Failed to initialize IoTDB schema")
            return False

    return True


def main():
    """Main execution loop for the bridge."""
    logger.info("Starting Zenoh-to-IoTDB bridge service...")
    
    # Perform initial connection
    if not connect_services():
        logger.error("Initialization failed. Exiting.")
        sys.exit(1)

    # Initial subscription
    logger.info("Declaring subscriber on key expression: %s", config.ZENOH_KEY_EXPRESSION)
    sub = zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, sample_callback)
    if not sub:
        logger.error("Failed to subscribe to key expression. Exiting.")
        sys.exit(1)

    logger.info("Bridge is actively running and subscribing.")

    # Keep service alive and monitor connectivity
    try:
        while running:
            # Check connection status
            if not zenoh_client.is_connected() or not iotdb_client.is_connected():
                logger.warning("Connection lost. Initiating reconnect loop...")
                
                # Cleanup existing client handles
                zenoh_client.close()
                iotdb_client.close()
                
                if connect_services():
                    # Re-subscribe
                    logger.info("Reconnected. Declaring subscriber on key expression: %s", config.ZENOH_KEY_EXPRESSION)
                    sub = zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, sample_callback)
                    if not sub:
                        logger.error("Failed to re-subscribe after connection recovery.")
                else:
                    logger.warning("Failed to reconnect during this cycle. Will retry in 5s.")
                    
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Interrupted by keyboard.")
    finally:
        logger.info("Cleaning up connections...")
        zenoh_client.close()
        iotdb_client.close()
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    main()
