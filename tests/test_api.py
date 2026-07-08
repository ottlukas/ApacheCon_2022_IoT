#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for the API module.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_zenoh_client():
    """Mock Zenoh client for testing."""
    with patch('src.api.zenoh_client') as mock:
        mock.is_connected.return_value = True
        mock.get.return_value = "25.0"
        mock.publish.return_value = True
        mock.subscribe.return_value = []
        yield mock


@pytest.fixture
def mock_iotdb_client():
    """Mock IoTDB client for testing."""
    with patch('src.api.iotdb_client') as mock:
        mock.is_connected.return_value = True
        mock.insert_temperature.return_value = True
        mock.query_temperature.return_value = [
            {'timestamp': '2023-01-01T00:00:00', 'temperature': 25.0}
        ]
        mock.get_latest_temperature.return_value = {
            'timestamp': '2023-01-01T00:00:00',
            'temperature': 25.0
        }
        yield mock


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    def test_health_endpoint(self, client):
        """Test that health endpoint returns correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "zenoh_connected" in data
        assert "iotdb_connected" in data


class TestZenohEndpoints:
    """Tests for Zenoh-related endpoints."""
    
    def test_publish_to_zenoh(self, client, mock_zenoh_client):
        """Test publishing to Zenoh."""
        response = client.get("/zenoh/publish?path=/test/temp&value=30")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["path"] == "/test/temp"
        assert data["value"] == "30"
        mock_zenoh_client.publish.assert_called_once()
    
    def test_get_from_zenoh(self, client, mock_zenoh_client):
        """Test getting value from Zenoh."""
        response = client.get("/zenoh/get?path=/test/temp")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/test/temp"
        assert data["value"] == "25.0"
        mock_zenoh_client.get.assert_called_once_with("/test/temp")
    
    def test_get_from_zenoh_not_found(self, client):
        """Test getting value from Zenoh when not found."""
        with patch('src.api.zenoh_client') as mock:
            mock.is_connected.return_value = True
            mock.get.return_value = None
            
            response = client.get("/zenoh/get?path=/test/temp")
            assert response.status_code == 404
    
    def test_subscribe_to_zenoh(self, client, mock_zenoh_client):
        """Test subscribing to Zenoh."""
        response = client.get("/zenoh/subscribe?path=/test/temp")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/test/temp"
        assert data["values"] == []
        mock_zenoh_client.subscribe.assert_called_once()


class TestIoTDBEndpoints:
    """Tests for IoTDB-related endpoints."""
    
    def test_insert_into_iotdb(self, client, mock_iotdb_client):
        """Test inserting into IoTDB."""
        response = client.post("/iotdb/insert?temperature=30")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["temperature"] == 30.0
        mock_iotdb_client.insert_temperature.assert_called_once()
    
    def test_query_iotdb(self, client, mock_iotdb_client):
        """Test querying IoTDB."""
        response = client.get("/iotdb/query?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        mock_iotdb_client.query_temperature.assert_called_once_with(limit=5)
    
    def test_get_latest_temperature(self, client, mock_iotdb_client):
        """Test getting latest temperature from IoTDB."""
        response = client.get("/iotdb/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["timestamp"] == "2023-01-01T00:00:00"
        assert data["temperature"] == 25.0
        mock_iotdb_client.get_latest_temperature.assert_called_once()
    
    def test_get_latest_temperature_not_found(self, client):
        """Test getting latest temperature when not found."""
        with patch('src.api.iotdb_client') as mock:
            mock.is_connected.return_value = True
            mock.get_latest_temperature.return_value = None
            
            response = client.get("/iotdb/latest")
            assert response.status_code == 404


class TestSyncEndpoint:
    """Tests for the sync endpoint."""
    
    def test_sync_zenoh_to_iotdb(self, client, mock_zenoh_client, mock_iotdb_client):
        """Test syncing data from Zenoh to IoTDB."""
        response = client.get("/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["zenoh_value"] == "25.0"
        mock_zenoh_client.get.assert_called_once_with("/myfactory/machine1/temp")
        mock_iotdb_client.insert_temperature.assert_called_once()
    
    def test_sync_zenoh_to_iotdb_not_found(self, client):
        """Test syncing when Zenoh value not found."""
        with patch('src.api.zenoh_client') as mock:
            mock.is_connected.return_value = True
            mock.get.return_value = None
            
            response = client.get("/sync")
            assert response.status_code == 404


class TestErrorHandling:
    """Tests for error handling in the API."""
    
    def test_zenoh_connection_error(self, client):
        """Test error when Zenoh is not connected."""
        with patch('src.api.zenoh_client') as mock:
            mock.is_connected.return_value = False
            mock.get.side_effect = Exception("Not connected")
            
            response = client.get("/zenoh/get")
            assert response.status_code == 500
    
    def test_iotdb_connection_error(self, client):
        """Test error when IoTDB is not connected."""
        with patch('src.api.iotdb_client') as mock:
            mock.is_connected.return_value = False
            mock.insert_temperature.side_effect = Exception("Not connected")
            
            response = client.post("/iotdb/insert?temperature=30")
            assert response.status_code == 500
