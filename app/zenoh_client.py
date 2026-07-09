# -*- coding: utf-8 -*-
"""Zenoh client module for the IoT application.

Supports eclipse-zenoh >= 1.9.0.

Key API differences from zenoh 0.x:
  - There is NO workspace concept; all operations (put, declare_subscriber, get)
    are performed directly on the Session object.
  - Config is built via zenoh.Config.from_json5() using a JSON5 dict string.
  - sample.payload is a ZBytes object; convert to bytes with bytes(sample.payload).
  - Subscribers are managed via session.declare_subscriber(key_expr, callback)
    and stopped by calling subscriber.undeclare().
"""

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

try:
    import zenoh

    ZENOH_AVAILABLE = True
except ImportError as exc:
    logging.warning("Zenoh library not available: %s", exc)
    ZENOH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ZenohClient:
    """Client wrapper for interacting with a Zenoh router (eclipse-zenoh >= 1.9.0)."""

    def __init__(self) -> None:
        self._session: Optional[Any] = None
        self._connected: bool = False
        # Maps key-expression string -> active Subscriber object
        self._subscribers: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, peer: str = "tcp/127.0.0.1:7447") -> bool:
        """Open a Zenoh client session connecting to *peer*.

        Args:
            peer: Zenoh router endpoint, e.g. ``tcp/localhost:7447``.

        Returns:
            ``True`` if the session was opened successfully.
        """
        if not ZENOH_AVAILABLE:
            logger.error("Zenoh library is not installed")
            return False

        try:
            conf_dict = {
                "mode": "client",
                "connect": {"endpoints": [peer]},
            }
            config = zenoh.Config.from_json5(json.dumps(conf_dict))
            self._session = zenoh.open(config)
            self._connected = True
            logger.info("Connected to Zenoh router at %s", peer)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error connecting to Zenoh at %s: %s", peer, exc)
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Return ``True`` when a live session is open."""
        if self._session is None or not self._connected:
            return False
        try:
            return not self._session.is_closed()
        except Exception:  # pylint: disable=broad-except
            return False

    def close(self) -> None:
        """Undeclare all subscribers and close the Zenoh session."""
        # Undeclare subscribers first
        for path, subscriber in list(self._subscribers.items()):
            try:
                subscriber.undeclare()
                logger.debug("Undeclared subscriber for %s", path)
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Error undeclaring subscriber for %s: %s", path, exc)
        self._subscribers.clear()

        if self._session is not None:
            try:
                self._session.close()
                logger.info("Zenoh session closed")
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Error closing Zenoh session: %s", exc)

        self._session = None
        self._connected = False

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, path: str, value: Any) -> bool:
        """Put *value* on *path* in the Zenoh router.

        Args:
            path:  Zenoh key expression to publish to.
            value: Value to publish; will be converted to ``bytes`` via str().

        Returns:
            ``True`` on success.
        """
        if not self.is_connected():
            logger.error("Cannot publish – not connected to Zenoh router")
            return False
        try:
            payload = str(value).encode("utf-8")
            self._session.put(path, payload)
            logger.debug("Published to %s: %s", path, value)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error publishing to %s: %s", path, exc)
            return False

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def get_subscriber(self, path: str, callback: Callable) -> Optional[Any]:
        """Declare a **persistent** subscriber on *path*.

        The *callback* is invoked for every received Sample.
        The caller is responsible for keeping the returned Subscriber
        alive (or calling :meth:`unsubscribe` / :meth:`close`).

        Args:
            path:     Zenoh key expression to subscribe to.
            callback: Callable that receives a ``zenoh.Sample``.

        Returns:
            The ``zenoh.Subscriber`` object, or ``None`` on failure.
        """
        if not self.is_connected():
            logger.error("Cannot subscribe – not connected to Zenoh router")
            return None
        try:
            subscriber = self._session.declare_subscriber(path, callback)
            self._subscribers[path] = subscriber
            logger.info("Declared subscriber on %s", path)
            return subscriber
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error declaring subscriber for %s: %s", path, exc)
            return None

    def subscribe(
        self, path: str, callback: Optional[Callable] = None, timeout: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Subscribe to *path*, collect messages for *timeout* seconds, then return.

        Primarily used by integration tests that need to collect a batch of
        messages synchronously.

        Args:
            path:     Zenoh key expression.
            callback: Optional extra callback invoked per-sample.
            timeout:  How many seconds to listen before returning.

        Returns:
            List of ``{"path": str, "value": str, "timestamp": float|None}`` dicts.
        """
        if not self.is_connected():
            logger.error("Cannot subscribe – not connected to Zenoh router")
            return []

        collected: List[Dict[str, Any]] = []

        def _handler(sample: Any) -> None:
            if sample.payload is None:
                return
            try:
                value_str = bytes(sample.payload).decode("utf-8")
                ts: Optional[float] = None
                if sample.timestamp is not None:
                    try:
                        # NTP64 object – convert to Unix time
                        ts = sample.timestamp.get_time().timestamp()
                    except Exception:  # pylint: disable=broad-except
                        pass
                collected.append(
                    {"path": str(sample.key_expr), "value": value_str, "timestamp": ts}
                )
                if callback is not None:
                    callback(sample)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error processing sample: %s", exc)

        subscriber = None
        try:
            subscriber = self._session.declare_subscriber(path, _handler)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                time.sleep(0.05)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error during timed subscription on %s: %s", path, exc)
        finally:
            if subscriber is not None:
                try:
                    subscriber.undeclare()
                except Exception:  # pylint: disable=broad-except
                    pass

        logger.debug("Collected %d messages from %s", len(collected), path)
        return collected

    def unsubscribe(self, path: str) -> bool:
        """Stop and remove the subscriber registered under *path*.

        Args:
            path: Zenoh key expression previously passed to
                  :meth:`get_subscriber`.

        Returns:
            ``True`` if a subscriber was found and removed.
        """
        subscriber = self._subscribers.pop(path, None)
        if subscriber is None:
            return False
        try:
            subscriber.undeclare()
            logger.debug("Unsubscribed from %s", path)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error unsubscribing from %s: %s", path, exc)
            return False


def decode_payload(sample: Any) -> Optional[str]:
    """Decode a Zenoh sample's payload to a UTF-8 string.

    Convenience helper used by bridge and dashboard callbacks.

    Args:
        sample: A ``zenoh.Sample`` received in a subscriber callback.

    Returns:
        Decoded string, or ``None`` if the payload is absent or undecodable.
    """
    if sample.payload is None:
        return None
    try:
        return bytes(sample.payload).decode("utf-8")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to decode Zenoh payload: %s", exc)
        return None
