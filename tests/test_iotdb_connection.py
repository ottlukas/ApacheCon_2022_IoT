# -*- coding: utf-8 -*-
"""Integration tests for Apache IoTDB connectivity."""

import pytest
import time
from app.iotdb_client import IoTDBClient
from app import config

TEST_DATABASE = "root.testfactory"
TEST_DEVICE = "root.testfactory.machine_test"
TEST_MEASUREMENT = "temperature"


@pytest.fixture(scope="module")
def iotdb_client():
    """Fixture to connect and close IoTDBClient for tests."""
    client = IoTDBClient()
    connected = client.connect(
        host="localhost",
        port=6667,
        username=config.IOTDB_USER,
        password=config.IOTDB_PASSWORD
    )
    if not connected:
        pytest.skip("Apache IoTDB is not running at localhost:6667. Integration tests skipped.")
    
    # Configure client to use test path schema
    client._database = TEST_DATABASE
    client._device = TEST_DEVICE
    client._measurement = TEST_MEASUREMENT

    yield client
    client.close()


def test_iotdb_connection_status(iotdb_client):
    """Verify that the client reports active connection to the IoTDB database."""
    assert iotdb_client.is_connected() is True


def test_iotdb_schema_initialization(iotdb_client):
    """Verify that database and timeseries schema can be created successfully."""
    # Ensure schema can initialize
    success = iotdb_client.initialize_schema()
    assert success is True


def test_iotdb_insert_and_query(iotdb_client):
    """Verify that we can insert telemetry and query it back from IoTDB."""
    # Setup test schema first
    iotdb_client.initialize_schema()

    timestamp = int(time.time() * 1000)
    test_temp = 28.7

    # Insert
    insert_ok = iotdb_client.insert_temperature(timestamp, test_temp)
    assert insert_ok is True

    # Query
    records = iotdb_client.query_temperature(limit=1)
    assert len(records) > 0
    
    # Assert latest record matches what we inserted
    latest = records[0]
    assert float(latest["temperature"]) == test_temp
