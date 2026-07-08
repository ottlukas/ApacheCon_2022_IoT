#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for the Zenoh client module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.zenoh_client import ZenohClient


@pytest.fixture
def mock_zenoh():
    """Mock Zenoh module."""
    with patch('src.zenoh_client.zenoh') as mock:
        with patch('src.zenoh_client.Zenoh') as mock_zenoh_class:
            with patch('src.zenoh_client.Workspace') as mock_workspace_class:
                # Setup mock instances
                mock_zenoh_instance = MagicMock()
                mock_workspace_instance = MagicMock()
                mock_zenoh_class.return_value = mock_zenoh_instance
                mock_zenoh_instance.workspace.return_value = mock_workspace_instance
                
                # Setup mock get method
                mock_result = MagicMock()
                mock_value = MagicMock()
                mock_value.get_content.return_value = "25.0"
                mock_timestamp = MagicMock()
                mock_timestamp.time = 1234567890
                mock_result.value = mock_value
                mock_result.timestamp = mock_timestamp
                mock_workspace_instance.get.return_value = [mock_result]
                
                yield {
                    'module': mock,
                    'Zenoh': mock_zenoh_class,
                    'Workspace': mock_workspace_class,
                    'instance': mock_zenoh_instance,
                    'workspace': mock_workspace_instance
                }


class TestZenohClientInitialization:
    """Tests for ZenohClient initialization."""
    
    def test_init(self):
        """Test client initialization."""
        client = ZenohClient()
        assert client._zenoh is None
        assert client._workspace is None
        assert client._connected is False
        assert client._subscribers == {}


class TestZenohClientConnection:
    """Tests for Zenoh client connection."""
    
    def test_connect_success(self, mock_zenoh):
        """Test successful connection to Zenoh router."""
        client = ZenohClient()
        result = client.connect(peer="tcp/127.0.0.1:7447")
        
        assert result is True
        assert client.is_connected() is True
        mock_zenoh['Zenoh'].assert_called_once()
    
    def test_connect_failure(self):
        """Test connection failure when Zenoh is not available."""
        with patch('src.zenoh_client.ZENOH_AVAILABLE', False):
            client = ZenohClient()
            result = client.connect()
            
            assert result is False
            assert client.is_connected() is False
    
    def test_connect_with_config(self, mock_zenoh):
        """Test connection with custom configuration."""
        client = ZenohClient()
        result = client.connect(
            peer="tcp/192.168.1.1:7447",
            custom_option="value"
        )
        
        assert result is True
        # Check that custom options were passed
        call_args = mock_zenoh['Zenoh'].call_args
        assert call_args[1]['peer'] == "tcp/192.168.1.1:7447"
        assert call_args[1]['custom_option'] == "value"


class TestZenohClientPublish:
    """Tests for Zenoh client publish functionality."""
    
    def test_publish_success(self, mock_zenoh):
        """Test successful publish to Zenoh."""
        client = ZenohClient()
        client.connect()
        
        result = client.publish("/test/temp", 25.0)
        
        assert result is True
        mock_zenoh['workspace'].put.assert_called_once_with("/test/temp", "25.0")
    
    def test_publish_not_connected(self):
        """Test publish when not connected."""
        client = ZenohClient()
        result = client.publish("/test/temp", 25.0)
        
        assert result is False
    
    def test_publish_with_string_value(self, mock_zenoh):
        """Test publish with string value."""
        client = ZenohClient()
        client.connect()
        
        result = client.publish("/test/temp", "hello")
        
        assert result is True
        mock_zenoh['workspace'].put.assert_called_once_with("/test/temp", "hello")


class TestZenohClientGet:
    """Tests for Zenoh client get functionality."""
    
    def test_get_success(self, mock_zenoh):
        """Test successful get from Zenoh."""
        client = ZenohClient()
        client.connect()
        
        result = client.get("/test/temp")
        
        assert result == "25.0"
        mock_zenoh['workspace'].get.assert_called_once_with("/test/temp")
    
    def test_get_not_connected(self):
        """Test get when not connected."""
        client = ZenohClient()
        result = client.get("/test/temp")
        
        assert result is None
    
    def test_get_timeout(self, mock_zenoh):
        """Test get with timeout."""
        client = ZenohClient()
        client.connect()
        
        # Mock empty results
        mock_zenoh['workspace'].get.return_value = []
        
        result = client.get("/test/temp", timeout=0.1)
        
        assert result is None


class TestZenohClientSubscribe:
    """Tests for Zenoh client subscribe functionality."""
    
    def test_subscribe_success(self, mock_zenoh):
        """Test successful subscribe to Zenoh path."""
        client = ZenohClient()
        client.connect()
        
        # Setup mock subscriber
        mock_subscriber = MagicMock()
        mock_zenoh['workspace'].subscribe.return_value = mock_subscriber
        
        result = client.subscribe("/test/temp", timeout=0.1)
        
        assert isinstance(result, list)
        mock_zenoh['workspace'].subscribe.assert_called_once()
    
    def test_subscribe_not_connected(self):
        """Test subscribe when not connected."""
        client = ZenohClient()
        result = client.subscribe("/test/temp")
        
        assert result == []


class TestZenohClientClose:
    """Tests for Zenoh client close functionality."""
    
    def test_close(self, mock_zenoh):
        """Test closing Zenoh connection."""
        client = ZenohClient()
        client.connect()
        
        client.close()
        
        assert client.is_connected() is False
        assert client._zenoh is None
        assert client._workspace is None
    
    def test_close_with_subscribers(self, mock_zenoh):
        """Test closing with active subscribers."""
        client = ZenohClient()
        client.connect()
        
        # Add a mock subscriber
        mock_subscriber = MagicMock()
        client._subscribers["/test/temp"] = mock_subscriber
        
        client.close()
        
        assert client.is_connected() is False
        mock_subscriber.close.assert_called_once()
        assert "/test/temp" not in client._subscribers


class TestZenohClientSubscriberManagement:
    """Tests for subscriber management."""
    
    def test_get_subscriber(self, mock_zenoh):
        """Test creating a persistent subscriber."""
        client = ZenohClient()
        client.connect()
        
        mock_subscriber = MagicMock()
        mock_zenoh['workspace'].subscribe.return_value = mock_subscriber
        
        callback = lambda x: None
        result = client.get_subscriber("/test/temp", callback)
        
        assert result is not None
        assert "/test/temp" in client._subscribers
    
    def test_unsubscribe(self, mock_zenoh):
        """Test unsubscribing from a path."""
        client = ZenohClient()
        client.connect()
        
        mock_subscriber = MagicMock()
        client._subscribers["/test/temp"] = mock_subscriber
        
        result = client.unsubscribe("/test/temp")
        
        assert result is True
        assert "/test/temp" not in client._subscribers
        mock_subscriber.close.assert_called_once()
    
    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing from a non-existent path."""
        client = ZenohClient()
        result = client.unsubscribe("/nonexistent")
        
        assert result is False
