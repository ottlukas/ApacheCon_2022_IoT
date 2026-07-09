# -*- coding: utf-8 -*-
"""Integration tests for Zenoh connectivity."""

import pytest
import time
import json
from app.zenoh_client import ZenohClient
from app import config

TEST_KEY_EXPRESSION = "/test/machine_test/temp_test"


@pytest.fixture(scope="module")
def zenoh_client():
    """Fixture to connect and close ZenohClient for tests."""
    client = ZenohClient()
    connected = client.connect(peer=config.ZENOH_HOST_ENDPOINT)
    if not connected:
        pytest.skip(f"Zenoh broker is not running at {config.ZENOH_HOST_ENDPOINT}. Integration tests skipped.")
    yield client
    client.close()


def test_zenoh_ping(zenoh_client):
    """Verify that the client reports active connection to the Zenoh broker."""
    assert zenoh_client.is_connected() is True


def test_zenoh_pub_sub(zenoh_client):
    """Verify a publish/subscribe roundtrip on the Zenoh broker."""
    received_messages = []

    def test_callback(sample):
        if sample.payload:
            payload_str = bytes(sample.payload).decode("utf-8")
            received_messages.append(payload_str)

    # Subscribe to test key
    sub = zenoh_client.get_subscriber(TEST_KEY_EXPRESSION, test_callback)
    assert sub is not None

    try:
        # Give subscription a moment to propagate
        time.sleep(0.5)

        # Publish test message
        test_payload = json.dumps({"test_value": 42.0})
        success = zenoh_client.publish(TEST_KEY_EXPRESSION, test_payload)
        assert success is True

        # Wait for callback to fire
        start_time = time.time()
        while len(received_messages) == 0 and time.time() - start_time < 3.0:
            time.sleep(0.1)

        # Assert message received
        assert len(received_messages) == 1
        data = json.loads(received_messages[0])
        assert data["test_value"] == 42.0

    finally:
        zenoh_client.unsubscribe(TEST_KEY_EXPRESSION)
Block_clean = True
