#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zenoh client module for the ApacheCon 2022 IoT Demo.

This module provides a wrapper for Zenoh operations with error handling
and version compatibility for Zenoh >= 0.11.0.
"""

import logging
from typing import Optional, List, Any, Dict
import time

# Try to import zenoh with version compatibility
try:
    import zenoh
    from zenoh import Zenoh, Workspace
    from zenoh.message import Message
    ZENOH_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Zenoh not available: {e}")
    ZENOH_AVAILABLE = False
    Zenoh = None
    Workspace = None

logger = logging.getLogger(__name__)


class ZenohClient:
    """
    Client for interacting with Zenoh router.
    
    Supports Zenoh >= 0.11.0 API.
    """
    
    def __init__(self):
        """Initialize the Zenoh client."""
        self._zenoh: Optional[Zenoh] = None
        self._workspace: Optional[Workspace] = None
        self._connected = False
        self._subscribers: Dict[str, Any] = {}
    
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
            # Create Zenoh instance with configuration
            config = {'peer': peer}
            config.update(kwargs)
            
            self._zenoh = Zenoh(config)
            self._workspace = self._zenoh.workspace('/')
            self._connected = True
            logger.info(f"Successfully connected to Zenoh router at {peer}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Zenoh: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if client is connected to Zenoh router."""
        return self._connected and self._zenoh is not None
    
    def close(self):
        """Close the Zenoh connection."""
        if self._zenoh is not None:
            try:
                # Close all subscribers
                for sub in self._subscribers.values():
                    try:
                        sub.close()
                    except Exception:
                        pass
                self._subscribers.clear()
                
                # Close workspace and zenoh instance
                self._workspace = None
                self._zenoh = None
                self._connected = False
                logger.info("Zenoh connection closed")
            except Exception as e:
                logger.error(f"Error closing Zenoh connection: {e}")
    
    def publish(self, path: str, value: Any) -> bool:
        """
        Publish a value to a Zenoh path.
        
        Args:
            path: Zenoh path to publish to
            value: Value to publish (will be converted to string)
            
        Returns:
            True if publish succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return False
        
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
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return None
        
        try:
            # Get with timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                results = self._workspace.get(path)
                if results and len(results) > 0:
                    # Get the most recent result
                    latest = results[-1]
                    if latest.value is not None:
                        value = latest.value.get_content()
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
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return []
        
        values = []
        
        try:
            def default_callback(change):
                """Default callback to collect values."""
                if change.value is not None:
                    value = change.value.get_content()
                    values.append({
                        'path': change.path,
                        'value': value,
                        'timestamp': change.timestamp.time if hasattr(change.timestamp, 'time') else None
                    })
                    if callback:
                        callback(change)
            
            # Subscribe with default callback
            subscriber = self._workspace.subscribe(path, default_callback)
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
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return None
        
        try:
            subscriber = self._workspace.subscribe(path, callback)
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
