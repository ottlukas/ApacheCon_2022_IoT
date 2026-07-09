# -*- coding: utf-8 -*-
"""Zenoh client module for the IoT application.

Provides support for eclipse-zenoh >= 1.9.0.
"""

import logging
import time
from typing import Optional, List, Any, Dict

# Try to import zenoh with version compatibility
try:
    import zenoh
    ZENOH_AVAILABLE = True
except ImportError as e:
    logging.warning("Zenoh library not available: %s", e)
    ZENOH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ZenohClient:
    """Client wrapper for interacting with Zenoh router."""

    def __init__(self):
        """Initialize the Zenoh client."""
        self._session = None
        self._workspace = None
        self._connected = False
        self._subscribers: Dict[str, Any] = {}
        self._config = None

    def connect(self, peer: str = "tcp/127.0.0.1:7447", **kwargs) -> bool:
        """Connect to Zenoh router.

        Args:
            peer: Zenoh peer address (e.g. tcp/127.0.0.1:7447)
            **kwargs: Additional configuration options

        Returns:
            True if connection succeeded, False otherwise
        """
        if not ZENOH_AVAILABLE:
            logger.error("Zenoh library is not installed")
            return False

        try:
            self._config = zenoh.Config()
            self._config.insert_json5("mode", '"client"')
            self._config.insert_json5("connect/endpoints", f"[{peer!r}]")

            # Apply any additional config overrides
            for key, value in kwargs.items():
                if key != "peer":
                    self._config.insert_json5(key, str(value))

            self._session = zenoh.open(self._config)
            self._workspace = self._session.workspace("/")
            self._connected = True
            logger.info("Successfully connected to Zenoh router at %s", peer)
            return True
        except Exception as e:
            logger.error("Error connecting to Zenoh: %s", e)
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if client is connected to Zenoh router."""
        return bool(self._connected and self._session is not None)

    def close(self):
        """Close all subscribers and the Zenoh session."""
        if self._session is None:
            return

        try:
            # Safely close all active subscribers
            for path, subscriber in list(self._subscribers.items()):
                try:
                    subscriber.close()
                except Exception as sub_err:
                    logger.debug("Error closing subscriber for %s: %s", path, sub_err)
            self._subscribers.clear()

            # Close the session
            try:
                self._session.close()
            except Exception as sess_err:
                logger.debug("Error closing session: %s", sess_err)

            self._session = None
            self._workspace = None
            self._connected = False
            logger.info("Zenoh connection closed successfully")
        except Exception as e:
            logger.error("Error during Zenoh client close: %s", e)

    def publish(self, path: str, value: Any) -> bool:
        """Publish a value to a Zenoh path.

        Args:
            path: Zenoh path to publish to
            value: Value to publish

        Returns:
            True if publish succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return False

        try:
            value_str = str(value)
            self._workspace.put(path, value_str)
            logger.debug("Published to %s: %s", path, value_str)
            return True
        except Exception as e:
            logger.error("Error publishing to Zenoh path %s: %s", path, e)
            return False

    def get(self, path: str, timeout: float = 2.0) -> Optional[str]:
        """Get the latest value from a Zenoh path.

        Args:
            path: Zenoh path to get value from
            timeout: Timeout in seconds

        Returns:
            The string value if found, None otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return None

        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                results = self._workspace.get(path)
                if results and len(results) > 0:
                    latest = results[-1]
                    if latest.ok is not None:
                        sample = latest.ok
                        if sample.payload is not None:
                            value = bytes(sample.payload).decode("utf-8")
                            logger.debug("Got value from %s: %s", path, value)
                            return value
                time.sleep(0.1)

            logger.warning("Timeout getting value from %s", path)
            return None
        except Exception as e:
            logger.error("Error getting from Zenoh path %s: %s", path, e)
            return None

    def subscribe(self, path: str, callback=None, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Subscribe to a Zenoh path and collect values for a specified duration.

        Args:
            path: Zenoh path to subscribe to
            callback: Optional callback for received messages
            timeout: Duration in seconds to run subscription

        Returns:
            List of collected values
        """
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return []

        values = []

        try:
            def default_callback(sample):
                if sample.payload is not None:
                    try:
                        value = bytes(sample.payload).decode("utf-8")
                        ts = None
                        if hasattr(sample.timestamp, "time"):
                            ts = sample.timestamp.time.timestamp()
                        values.append({
                            "path": str(sample.key_expr),
                            "value": value,
                            "timestamp": ts
                        })
                        if callback:
                            callback(sample)
                    except Exception as e:
                        logger.error("Error processing sample: %s", e)

            subscriber = self._workspace.declare_subscriber(path, default_callback)
            self._subscribers[path] = subscriber

            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.1)

            if path in self._subscribers:
                self._subscribers[path].close()
                del self._subscribers[path]

            logger.debug("Subscribed to %s, collected %d messages", path, len(values))
            return values
        except Exception as e:
            logger.error("Error subscribing to Zenoh path %s: %s", path, e)
            return []

    def get_subscriber(self, path: str, callback) -> Optional[Any]:
        """Create a persistent subscriber for a Zenoh path.

        Args:
            path: Zenoh path to subscribe to
            callback: Callback function for received samples

        Returns:
            Subscriber object or None if failed
        """
        if not self.is_connected():
            logger.error("Not connected to Zenoh router")
            return None

        try:
            subscriber = self._workspace.declare_subscriber(path, callback)
            self._subscribers[path] = subscriber
            logger.debug("Created persistent subscriber for %s", path)
            return subscriber
        except Exception as e:
            logger.error("Error creating subscriber for %s: %s", path, e)
            return None

    def unsubscribe(self, path: str) -> bool:
        """Unsubscribe from a Zenoh path.

        Args:
            path: Zenoh path to unsubscribe from

        Returns:
            True if successful, False otherwise
        """
        if path in self._subscribers:
            try:
                self._subscribers[path].close()
                del self._subscribers[path]
                logger.debug("Unsubscribed from %s", path)
                return True
            except Exception as e:
                logger.error("Error unsubscribing from %s: %s", path, e)
                return False
        return False
