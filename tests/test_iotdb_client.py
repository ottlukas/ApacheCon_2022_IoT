#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for the IoTDB client module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.iotdb_client import IoTDBClient


@pytest.fixture
def mock_iotdb_session():
    """Mock IoTDB Session."""
    with patch('src.iotdb_client.Session') as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # Mock query result
        mock_result = MagicMock()
        mock_df = pd.DataFrame({
            'Time': ['2023-01-01T00:00:00', '2023-01-01T00:01:00'],
            'root.myfactory.machine1.temperature': [25, 26]
        })
        mock_result.todf.return_value = mock_df
        mock_session.execute_query_statement.return_value = mock_result
        
        yield {
            'class': mock_session_class,
            'instance': mock_session,
            'result': mock_result,
            'df': mock_df
        }


class TestIoTDBClientInitialization:
    """Tests for IoTDBClient initialization."""
    
    def test_init(self):
        """Test client initialization."""
        client = IoTDBClient()
        assert client._session is None
        assert client._connected is False
        assert client._config['host'] == '127.0.0.1'
        assert client._config['port'] == '6667'


class TestIoTDBClientConnection:
    """Tests for IoTDB client connection."""
    
    def test_connect_success(self, mock_iotdb_session):
        """Test successful connection to IoTDB."""
        client = IoTDBClient()
        result = client.connect(
            host="127.0.0.1",
            port="6667",
            username="root",
            password="root"
        )
        
        assert result is True
        assert client.is_connected() is True
        mock_iotdb_session['class'].assert_called_once()
        mock_iotdb_session['instance'].open.assert_called_once_with(False)
    
    def test_connect_failure(self):
        """Test connection failure when IoTDB is not available."""
        with patch('src.iotdb_client.IOTDB_AVAILABLE', False):
            client = IoTDBClient()
            result = client.connect()
            
            assert result is False
            assert client.is_connected() is False
    
    def test_connect_with_custom_config(self, mock_iotdb_session):
        """Test connection with custom configuration."""
        client = IoTDBClient()
        result = client.connect(
            host="192.168.1.1",
            port="6668",
            username="admin",
            password="password"
        )
        
        assert result is True
        assert client._config['host'] == "192.168.1.1"
        assert client._config['port'] == "6668"


class TestIoTDBClientClose:
    """Tests for IoTDB client close functionality."""
    
    def test_close(self, mock_iotdb_session):
        """Test closing IoTDB connection."""
        client = IoTDBClient()
        client.connect()
        
        client.close()
        
        assert client.is_connected() is False
        assert client._session is None
        mock_iotdb_session['instance'].close.assert_called_once()


class TestIoTDBClientSchema:
    """Tests for IoTDB schema operations."""
    
    def test_initialize_schema_success(self, mock_iotdb_session):
        """Test successful schema initialization."""
        client = IoTDBClient()
        client.connect()
        
        result = client.initialize_schema()
        
        assert result is True
        # Check that storage group and time series were created
        calls = mock_iotdb_session['instance'].execute_non_query_statement.call_args_list
        assert len(calls) == 2
        assert "SET STORAGE GROUP" in str(calls[0])
        assert "CREATE TIMESERIES" in str(calls[1])
    
    def test_initialize_schema_custom(self, mock_iotdb_session):
        """Test schema initialization with custom names."""
        client = IoTDBClient()
        client.connect()
        
        result = client.initialize_schema(
            storage_group="root.custom",
            timeseries="sensor.temperature"
        )
        
        assert result is True
        calls = mock_iotdb_session['instance'].execute_non_query_statement.call_args_list
        assert "root.custom" in str(calls[0])
        assert "root.custom.sensor.temperature" in str(calls[1])
    
    def test_initialize_schema_already_exists(self, mock_iotdb_session):
        """Test schema initialization when schema already exists."""
        client = IoTDBClient()
        client.connect()
        
        # Mock error for already existing schema
        mock_iotdb_session['instance'].execute_non_query_statement.side_effect = Exception(
            "Timeseries already exist"
        )
        
        result = client.initialize_schema()
        
        assert result is True


class TestIoTDBClientInsert:
    """Tests for IoTDB insert operations."""
    
    def test_insert_temperature_success(self, mock_iotdb_session):
        """Test successful temperature insertion."""
        client = IoTDBClient()
        client.connect()
        
        result = client.insert_temperature("2023-01-01T00:00:00", 25.0)
        
        assert result is True
        mock_iotdb_session['instance'].execute_non_query_statement.assert_called_once()
    
    def test_insert_temperature_not_connected(self):
        """Test insert when not connected."""
        client = IoTDBClient()
        result = client.insert_temperature("2023-01-01T00:00:00", 25.0)
        
        assert result is False
    
    def test_insert_temperature_with_unix_timestamp(self, mock_iotdb_session):
        """Test insert with Unix timestamp."""
        client = IoTDBClient()
        client.connect()
        
        result = client.insert_temperature("1234567890", 25.0)
        
        assert result is True
        call_args = mock_iotdb_session['instance'].execute_non_query_statement.call_args
        assert "1234567890" in str(call_args)


class TestIoTDBClientQuery:
    """Tests for IoTDB query operations."""
    
    def test_query_temperature_success(self, mock_iotdb_session):
        """Test successful temperature query."""
        client = IoTDBClient()
        client.connect()
        
        results = client.query_temperature(limit=10)
        
        assert len(results) == 2
        assert results[0]['timestamp'] == '2023-01-01T00:00:00'
        assert results[0]['temperature'] == 25.0
        assert results[1]['timestamp'] == '2023-01-01T00:01:00'
        assert results[1]['temperature'] == 26.0
    
    def test_query_temperature_not_connected(self):
        """Test query when not connected."""
        client = IoTDBClient()
        results = client.query_temperature(limit=10)
        
        assert results == []
    
    def test_query_temperature_empty_result(self, mock_iotdb_session):
        """Test query with empty result."""
        client = IoTDBClient()
        client.connect()
        
        # Mock empty dataframe
        mock_empty_df = pd.DataFrame()
        mock_iotdb_session['result'].todf.return_value = mock_empty_df
        
        results = client.query_temperature(limit=10)
        
        assert results == []


class TestIoTDBClientLatest:
    """Tests for getting latest temperature."""
    
    def test_get_latest_temperature_success(self, mock_iotdb_session):
        """Test successful get latest temperature."""
        client = IoTDBClient()
        client.connect()
        
        result = client.get_latest_temperature()
        
        assert result is not None
        assert result['timestamp'] == '2023-01-01T00:00:00'
        assert result['temperature'] == 25.0
    
    def test_get_latest_temperature_not_found(self, mock_iotdb_session):
        """Test get latest when no data exists."""
        client = IoTDBClient()
        client.connect()
        
        # Mock empty result
        mock_iotdb_session['result'].todf.return_value = pd.DataFrame()
        
        result = client.get_latest_temperature()
        
        assert result is None


class TestIoTDBClientCustomQueries:
    """Tests for custom query execution."""
    
    def test_execute_query_success(self, mock_iotdb_session):
        """Test successful custom query execution."""
        client = IoTDBClient()
        client.connect()
        
        result = client.execute_query("SELECT * FROM root.myfactory.machine1")
        
        assert result is not None
        mock_iotdb_session['instance'].execute_query_statement.assert_called_once()
    
    def test_execute_query_not_connected(self):
        """Test custom query when not connected."""
        client = IoTDBClient()
        result = client.execute_query("SELECT * FROM root.myfactory.machine1")
        
        assert result is None
    
    def test_execute_non_query_success(self, mock_iotdb_session):
        """Test successful non-query execution."""
        client = IoTDBClient()
        client.connect()
        
        result = client.execute_non_query("DELETE FROM root.myfactory.machine1")
        
        assert result is True
        mock_iotdb_session['instance'].execute_non_query_statement.assert_called_once()
    
    def test_execute_non_query_not_connected(self):
        """Test non-query when not connected."""
        client = IoTDBClient()
        result = client.execute_non_query("DELETE FROM root.myfactory.machine1")
        
        assert result is False
