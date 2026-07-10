# -*- coding: utf-8 -*-
"""Integration tests for the Zenoh-to-IoTDB bridge end-to-end flow.

Requires the Docker Compose stack (zenoh + iotdb + zenoh-to-iotdb bridge) to
be running via ``make up``.  Tests are automatically skipped when either
service is unreachable.

Test strategy:
  1. Connect a local test publisher to Zenoh.
  2. Connect a local test reader to IoTDB.
  3. Publish one standard telemetry message to the production key expression.
  4. Poll IoTDB for up to 10 seconds until the bridge writes the value.
  5. Assert the bridged value matches what was published.
"""

import json
import time
from datetime import datetime, timezone

import pytest

from app import config
from app.iotdb_client import IoTDBClient
from app.zenoh_client import ZenohClient

# Poll timeout: how long to wait for the bridge to persist the message
BRIDGE_WAIT_SECONDS = 10.0


@pytest.fixture(scope="module")
def bridge_flow_services():
    """Connect both clients and skip if either service is unavailable."""
    zenoh_cl = ZenohClient()
    iotdb_cl = IoTDBClient()

    z_ok = zenoh_cl.connect(peer=config.ZENOH_HOST_ENDPOINT)
    i_ok = iotdb_cl.connect(host="localhost", port=6667)

    if not (z_ok and i_ok):
        if z_ok:
            zenoh_cl.close()
        if i_ok:
            iotdb_cl.close()
        pytest.skip(
            "Bridge flow test requires both Zenoh and IoTDB to be running. "
            "Integration tests skipped."
        )

    yield zenoh_cl, iotdb_cl

    zenoh_cl.close()
    iotdb_cl.close()


def test_bridge_flow(bridge_flow_services):
    """Publish a message to Zenoh and assert it is persisted to IoTDB by the bridge."""
    zenoh_cl, iotdb_cl = bridge_flow_services

    # Ensure the target schema exists so queries don't fail
    iotdb_cl.initialize_schema()

    # Use a value with fractional uniqueness to avoid false positives from
    # pre-existing data in the database
    unique_temp = round(15.0 + (time.time() % 10.0), 3)
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    payload = {
        "sensor_id": "machine1-temperature",
        "device": "machine1",
        "measurement": "temperature",
        "value": unique_temp,
        "unit": "celsius",
        "timestamp": timestamp_iso,
    }

    # Publish to the production key expression (what the bridge is subscribed to)
    publish_ok = zenoh_cl.publish(config.ZENOH_KEY_EXPRESSION, json.dumps(payload))
    assert publish_ok is True, "Failed to publish test telemetry to Zenoh"

    # Poll IoTDB until the bridge persists the value or the timeout expires
    found = False
    deadline = time.monotonic() + BRIDGE_WAIT_SECONDS
    while time.monotonic() < deadline:
        records = iotdb_cl.query_temperature(limit=20)
        for rec in records:
            if abs(float(rec.get("temperature", 0.0)) - unique_temp) < 0.001:
                found = True
                break
        if found:
            break
        time.sleep(0.5)

    assert found is True, (
        f"Telemetry value {unique_temp} was not bridged to IoTDB within "
        f"{BRIDGE_WAIT_SECONDS}s. Check bridge container logs: "
        "'docker compose logs -f zenoh-to-iotdb'"
    )

