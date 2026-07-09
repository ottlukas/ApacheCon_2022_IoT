# -*- coding: utf-8 -*-
"""Integration tests for the Zenoh-to-IoTDB bridge flow."""

import pytest
import time
import json
from app.zenoh_client import ZenohClient
from app.iotdb_client import IoTDBClient
from app import config


@pytest.fixture(scope="module")
def bridge_flow_services():
    """Setup clients and skip tests if Zenoh or IoTDB are not accessible."""
    zenoh_cl = ZenohClient()
    iotdb_cl = IoTDBClient()

    z_ok = zenoh_cl.connect(peer=config.ZENOH_HOST_ENDPOINT)
    i_ok = iotdb_cl.connect(host="localhost", port=6667)

    if not (z_ok and i_ok):
        if z_ok:
            zenoh_cl.close()
        if i_ok:
            iotdb_cl.close()
        pytest.skip("Bridge flow requires Zenoh and IoTDB to be running. Integration tests skipped.")

    yield zenoh_cl, iotdb_cl

    zenoh_cl.close()
    iotdb_cl.close()


def test_bridge_flow(bridge_flow_services):
    """Publish a message to Zenoh and verify it gets persisted to IoTDB by the bridge."""
    zenoh_cl, iotdb_cl = bridge_flow_services

    # Ensure target schema exists
    iotdb_cl.initialize_schema()

    # Clear previous entries if any (so we can assert cleanly)
    # The client can delete or we can just write a unique value
    unique_temp = 15.0 + (time.time() % 10.0)  # Random unique number between 15.0 and 25.0
    timestamp_iso = "2026-07-09T12:34:56.789Z"

    # Construct standard telemetry payload
    payload = {
        "sensor_id": "machine1-temperature",
        "device": "machine1",
        "measurement": "temperature",
        "value": unique_temp,
        "unit": "celsius",
        "timestamp": timestamp_iso
    }

    logger_msg = json.dumps(payload)

    # Publish to Zenoh
    publish_success = zenoh_cl.publish(config.ZENOH_KEY_EXPRESSION, logger_msg)
    assert publish_success is True

    # Polling IoTDB for the unique value (maximum 5 seconds)
    found = False
    start_time = time.time()
    while time.time() - start_time < 5.0:
        records = iotdb_cl.query_temperature(limit=10)
        for r in records:
            if abs(float(r["temperature"]) - unique_temp) < 0.01:
                found = True
                break
        if found:
            break
        time.sleep(0.5)

    assert found is True, f"Telemetry value {unique_temp} was not bridged to IoTDB within 5 seconds."
Block_clean = True
