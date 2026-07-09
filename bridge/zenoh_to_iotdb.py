# -*- coding: utf-8 -*-
"""Zenoh-to-IoTDB Bridge service.

Subscribes to the configured Zenoh key expression, validates incoming JSON
telemetry payloads using the SensorReading Pydantic model, and persists
readings into Apache IoTDB.

Designed to run as a Docker container:
  - Connects to Zenoh at ZENOH_ENDPOINT  (default: tcp/zenoh:7447)
  - Connects to IoTDB at IOTDB_HOST:IOTDB_PORT  (default: iotdb:6667)

Both connections use retry/backoff logic so the bridge tolerates slow
container startup ordering.
"""

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone

from app import config
from app.iotdb_client import IoTDBClient
from app.models import SensorReading
from app.zenoh_client import ZenohClient, decode_payload

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("zenoh_to_iotdb_bridge")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()
_running = True


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def _handle_shutdown(signum, frame) -> None:  # noqa: ARG001
    """Respond to SIGINT / SIGTERM by setting the shutdown flag."""
    global _running  # noqa: PLW0603
    logger.info("Shutdown signal %d received – stopping bridge …", signum)
    _running = False


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


# ---------------------------------------------------------------------------
# Zenoh sample callback
# ---------------------------------------------------------------------------


def _sample_callback(sample) -> None:
    """Process a single Zenoh sample.

    Decodes JSON, validates with Pydantic, and inserts into IoTDB.
    Malformed or invalid messages are logged and silently dropped.
    """
    payload_str = decode_payload(sample)
    if payload_str is None:
        logger.warning("Received Zenoh sample with empty/null payload – skipping")
        return

    logger.debug("Received payload: %s", payload_str)

    # ---- JSON decode -------------------------------------------------------
    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        logger.error("Malformed JSON from Zenoh – skipping: %s", exc)
        return

    # ---- Pydantic validation -----------------------------------------------
    try:
        reading = SensorReading(**data)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Payload validation failed – skipping: %s", exc)
        return

    # ---- Timestamp resolution ----------------------------------------------
    timestamp: str = reading.timestamp
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Bridging value → IoTDB | device=%s measurement=%s value=%s timestamp=%s",
        reading.device,
        reading.measurement,
        reading.value,
        timestamp,
    )

    # ---- IoTDB insert ------------------------------------------------------
    if not iotdb_client.is_connected():
        logger.error("IoTDB not connected – cannot insert, will retry on next message")
        return

    if not iotdb_client.insert_temperature(timestamp, reading.value):
        logger.error("Failed to insert telemetry into IoTDB (see above for details)")


# ---------------------------------------------------------------------------
# Startup connection helper
# ---------------------------------------------------------------------------


def _connect_services(max_retries: int = 20, delay: float = 3.0) -> bool:
    """Connect to Zenoh and IoTDB with linear retry/backoff.

    Args:
        max_retries: Maximum number of connection attempts per service.
        delay:       Seconds to wait between attempts.

    Returns:
        ``True`` when both services are connected and the IoTDB schema
        is initialised.
    """
    global _running  # noqa: PLW0603

    # ---- Zenoh ----------------------------------------------------------------
    retries = 0
    while _running and not zenoh_client.is_connected():
        logger.info(
            "Connecting to Zenoh at %s (attempt %d/%d) …",
            config.ZENOH_ENDPOINT,
            retries + 1,
            max_retries,
        )
        if zenoh_client.connect(peer=config.ZENOH_ENDPOINT):
            logger.info("Zenoh connected")
            break
        retries += 1
        if retries >= max_retries:
            logger.error("Could not connect to Zenoh after %d attempts", max_retries)
            return False
        time.sleep(delay)

    if not _running:
        return False

    # ---- IoTDB ----------------------------------------------------------------
    retries = 0
    while _running and not iotdb_client.is_connected():
        logger.info(
            "Connecting to IoTDB at %s:%d (attempt %d/%d) …",
            config.IOTDB_HOST,
            config.IOTDB_PORT,
            retries + 1,
            max_retries,
        )
        if iotdb_client.connect():
            logger.info("IoTDB connected")
            break
        retries += 1
        if retries >= max_retries:
            logger.error("Could not connect to IoTDB after %d attempts", max_retries)
            return False
        time.sleep(delay)

    if not _running:
        return False

    # ---- Schema init ----------------------------------------------------------
    logger.info("Initialising IoTDB schema …")
    if not iotdb_client.initialize_schema():
        logger.error("Failed to initialise IoTDB schema")
        return False

    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the bridge service."""
    logger.info("Starting Zenoh-to-IoTDB bridge service …")

    if not _connect_services():
        logger.error("Initial connection setup failed – exiting")
        sys.exit(1)

    logger.info("Declaring subscriber on key expression: %s", config.ZENOH_KEY_EXPRESSION)
    subscriber = zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, _sample_callback)
    if subscriber is None:
        logger.error("Failed to declare Zenoh subscriber – exiting")
        sys.exit(1)

    logger.info("Bridge is running.  Waiting for Zenoh messages …")

    try:
        while _running:
            # Periodic health-check; reconnect if a connection was lost
            if not zenoh_client.is_connected() or not iotdb_client.is_connected():
                logger.warning("A connection was lost – initiating reconnect …")
                zenoh_client.close()
                iotdb_client.close()

                if _connect_services():
                    logger.info("Reconnected.  Re-declaring subscriber on %s", config.ZENOH_KEY_EXPRESSION)
                    subscriber = zenoh_client.get_subscriber(
                        config.ZENOH_KEY_EXPRESSION, _sample_callback
                    )
                    if subscriber is None:
                        logger.error("Failed to re-subscribe after reconnect")
                else:
                    logger.warning("Reconnect attempt failed – will retry in %ds", 5)

            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    finally:
        logger.info("Cleaning up connections …")
        zenoh_client.close()
        iotdb_client.close()
        logger.info("Bridge stopped cleanly")


if __name__ == "__main__":
    main()
