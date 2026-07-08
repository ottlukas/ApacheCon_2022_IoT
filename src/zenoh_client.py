#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zenoh client module for the ApacheCon 2022 IoT Demo.

This module provides a wrapper for Zenoh operations with error handling
and version compatibility for eclipse-zenoh >= 1.9.0.
"""

import logging
from typing import Optional, List, Any, Dict
import time
from client_utils import (
    is_connected as util_is_connected,
    close_connection as util_close_connection,
    check_connected_or_return as util_check_connected_or_return,
)

# Try to import zenoh with version compatibility
try:
    import zenoh
    ZENOH_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Zenoh not available: {e}")
    ZENOH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ZenohClient:
    """
    Client for interacting with Zenoh router.
    
    Supports eclipse-zenoh >= 1.9.0 API.
    """
    
    def __init__(self):
        """Initialize the Zenoh client."""
        self._session = None
        self._workspace = None
        self._connected = False
        self._subscribers: Dict[str, Any] = {}
        self._config = zenoh.Config() if ZENOH_AVAILABLE else None
    
    def connect(self, peer: str = "tcp/127.0.0.1:7447", **kwargs) -> bool:
        """
        Connect to Zenoh router.
        
        Args:
            peer: Zenoh peer address
            **kwargs: Additional configuration options
            
        Returns:
            True if connection succeeded, False otherwise
        """
        if not ZENOH_AVAILABLE:
            logger.error("Zenoh library is not installed")
            return False
        
        try:
            # Create configuration
            self._config = zenoh.Config()
            # Set mode to client
            self._config.insert_json5("mode", '"client"')
            # Set connect endpoints
            self._config.insert_json5("connect/endpoints", f'[{peer!r}]')
            
            # Apply any additional kwargs to config
            for key, value in kwargs.items():
                if key != 'peer':  # peer is already handled
                    self._config.insert_json5(key, str(value))
            
            # Open session
            self._session = zenoh.open(self._config)
            self._workspace = self._session.workspace('/')
            self._connected = True
            logger.info(f"Successfully connected to Zenoh router at {peer}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Zenoh: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if client is connected to Zenoh router."""
        return util_is_connected(self)
    
    def close(self):
        """Close the Zenoh connection."""
        util_close_connection(self)
    
    def publish(self, path: str, value: Any) -> bool:
        """
        Publish a value to a Zenoh path.
        
        Args:
            path: Zenoh path to publish to
            value: Value to publish (will be converted to string)
            
        Returns:
            True if publish succeeded, False otherwise
        """
        ret = util_check_connected_or_return(self, "Zenoh router", False)
        if ret is not None:
            return ret
        
        try:
            # Convert value to string if needed
            value_str = str(value)
            self._workspace.put(path, value_str)
            logger.debug(f"Published to {path}: {value_str}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing to Zenoh path {path}: {e}")
            return False
    
    def get(self, path: str, timeout: float = 2.0) -> Optional[Any]:
        """
        Get the latest value from a Zenoh path.
        
        Args:
            path: Zenoh path to get value from
            timeout: Timeout in seconds
            
        Returns:
            The value if found, None otherwise
        """
        ret = util_check_connected_or_return(self, "Zenoh router", None)
        if ret is not None:
            return ret
        
        try:
            # Get with timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                results = self._workspace.get(path)
                if results and len(results) > 0:
                    # Get the most recent result
                    latest = results[-1]
                    if latest.ok is not None:
                        sample = latest.ok
                        if sample.payload is not None:
                            value = bytes(sample.payload).decode('utf-8')
                            logger.debug(f"Got value from {path}: {value}")
                            return value
                time.sleep(0.1)
            
            logger.warning(f"Timeout getting value from {path}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting from Zenoh path {path}: {e}")
            return None
    
    def subscribe(self, path: str, callback=None, timeout: float = 5.0) -> List[Any]:
        """
        Subscribe to a Zenoh path and collect values.
        
        Args:
            path: Zenoh path to subscribe to
            callback: Optional callback function for received messages
            timeout: Timeout in seconds to collect values
            
        Returns:
            List of received values
        """
        ret = util_check_connected_or_return(self, "Zenoh router", [])
        if ret is not None:
            return ret
        
        values = []
        
        try:
            def default_callback(sample):
                """Default callback to collect values."""
                if sample.payload is not None:
                    try:
                        value = bytes(sample.payload).decode('utf-8')
                        values.append({
                            'path': str(sample.key_expr),
                            'value': value,
                            'timestamp': sample.timestamp.time.timestamp() if hasattr(sample.timestamp, 'time') else None
                        })
                        if callback:
                            callback(sample)
                    except Exception as e:
                        logger.error(f"Error processing sample: {e}")
            
            # Subscribe with default callback
            subscriber = self._workspace.declare_subscriber(path, default_callback)
            self._subscribers[path] = subscriber
            
            # Wait for messages
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.1)
            
            # Unsubscribe
            if path in self._subscribers:
                self._subscribers[path].close()
                del self._subscribers[path]
            
            logger.debug(f"Subscribed to {path}, received {len(values)} messages")
            return values
            
        except Exception as e:
            logger.error(f"Error subscribing to Zenoh path {path}: {e}")
            return []
    
    def get_subscriber(self, path: str, callback) -> Optional[Any]:
        """
        Create a persistent subscriber for a Zenoh path.
        
        Args:
            path: Zenoh path to subscribe to
            callback: Callback function for received messages
            
        Returns:
            Subscriber object or None if failed
        """
        ret = util_check_connected_or_return(self, "Zenoh router", None)
        if ret is not None:
            return ret
        
        try:
            subscriber = self._workspace.declare_subscriber(path, callback)
            self._subscribers[path] = subscriber
            logger.debug(f"Created persistent subscriber for {path}")
            return subscriber
        except Exception as e:
            logger.error(f"Error creating subscriber for {path}: {e}")
            return None
    
    def unsubscribe(self, path: str) -> bool:
        """
        Unsubscribe from a Zenoh path.
        
        Args:
            path: Zenoh path to unsubscribe from
            
        Returns:
            True if unsubscribed successfully, False otherwise
        """
        if path in self._subscribers:
            try:
                self._subscribers[path].close()
                del self._subscribers[path]
                logger.debug(f"Unsubscribed from {path}")
                return True
            except Exception as e:
                logger.error(f"Error unsubscribing from {path}: {e}")
                return False
        return False
