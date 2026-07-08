#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for the Zenoh client module.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.zenoh_client import ZenohClient


@pytest.fixture
def mock_zenoh():
    """Mock Zenoh module for eclipse-zenoh >= 1.9.0."""
    with patch('src.zenoh_client.zenoh') as mock:
        # Mock Config
        mock_config = MagicMock()
        mock.Config.return_value = mock_config
        
        # Mock Session
        mock_session = MagicMock()
        mock.open.return_value = mock_session
        
        # Mock Workspace
        mock_workspace = MagicMock()
        mock_session.workspace.return_value = mock_workspace
        
        # Setup mock get method - new API returns Reply objects
        mock_reply = MagicMock()
        mock_reply.is_ok.return_value = True
        mock_sample = MagicMock()
        mock_sample.payload = b"25.0"
        mock_timestamp = MagicMock()
        mock_timestamp.time.timestamp.return_value = 1234567890
        mock_sample.timestamp = mock_timestamp
        mock_reply.ok = mock_sample
        mock_workspace.get.return_value = [mock_reply]
        
        # Setup mock put method
        mock_workspace.put.return_value = None
        
        # Setup mock subscriber
        mock_subscriber = MagicMock()
        mock_workspace.declare_subscriber.return_value = mock_subscriber
        
        yield {
            'module': mock,
            'Config': mock.Config,
            'open': mock.open,
            'session': mock_session,
            'workspace': mock_workspace,
            'subscriber': mock_subscriber,
            'reply': mock_reply,
            'sample': mock_sample
        }


class TestZenohClientInitialization:
    """Tests for ZenohClient initialization."""
    
    def test_init(self):
        """Test client initialization."""
        client = ZenohClient()
        assert client._session is None
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
        mock_zenoh['open'].assert_called_once()
    
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
        # Check that config was created
        mock_zenoh['Config'].assert_called()


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
        
        result = client.subscribe("/test/temp", timeout=0.1)
        
        assert isinstance(result, list)
        mock_zenoh['workspace'].declare_subscriber.assert_called_once()
    
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
        assert client._session is None
        assert client._workspace is None
        mock_zenoh['session'].close.assert_called_once()
    
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
        
        def callback(x):
            return None
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
