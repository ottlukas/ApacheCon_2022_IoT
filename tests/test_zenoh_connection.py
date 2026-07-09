# -*- coding: utf-8 -*-
"""Integration tests for Zenoh broker connectivity.

Requires the Docker Compose stack to be running (``make up``).
Tests are automatically skipped when the Zenoh broker is unreachable.
"""

import json
import time

import pytest

from app import config
from app.zenoh_client import ZenohClient

# Use a separate test key expression to avoid polluting production data
TEST_KEY_EXPRESSION = "test/machine_test/temp_test"


@pytest.fixture(scope="module")
def zenoh_client():
    """Module-scoped fixture: connect once, yield, then close."""
    client = ZenohClient()
    connected = client.connect(peer=config.ZENOH_HOST_ENDPOINT)
    if not connected:
        pytest.skip(
            f"Zenoh broker is not running at {config.ZENOH_HOST_ENDPOINT}. "
            "Integration tests skipped."
        )
    yield client
    client.close()


def test_zenoh_ping(zenoh_client):
    """The client must report an active connection to the Zenoh broker."""
    assert zenoh_client.is_connected() is True


def test_zenoh_pub_sub(zenoh_client):
    """Publish a JSON message and verify it is received via subscription."""
    received: list = []

    def _callback(sample) -> None:
        if sample.payload is not None:
            received.append(bytes(sample.payload).decode("utf-8"))

    # Subscribe first, then publish
    sub = zenoh_client.get_subscriber(TEST_KEY_EXPRESSION, _callback)
    assert sub is not None, "Failed to declare subscriber"

    try:
        # Brief pause to let the subscription propagate through the broker
        time.sleep(0.5)

        test_payload = json.dumps({"test_value": 42.0})
        ok = zenoh_client.publish(TEST_KEY_EXPRESSION, test_payload)
        assert ok is True, "Publish returned False"

        # Poll for up to 3 seconds
        deadline = time.monotonic() + 3.0
        while len(received) == 0 and time.monotonic() < deadline:
            time.sleep(0.1)

        assert len(received) >= 1, "No message received within 3 seconds"
        data = json.loads(received[0])
        assert data["test_value"] == 42.0
    finally:
        zenoh_client.unsubscribe(TEST_KEY_EXPRESSION)
