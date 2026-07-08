#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared client utilities for IoTDB and Zenoh clients.

Provides small helper functions to reduce duplicated connection
management logic across client implementations.
"""

from typing import Any
import logging

logger = logging.getLogger(__name__)


def is_connected(obj: Any) -> bool:
    """Return True if the client object reports an active session.

    Checks for an attribute ``_connected`` and a non-None ``_session``.
    """
    return bool(getattr(obj, "_connected", False) and getattr(obj, "_session", None) is not None)


def close_connection(obj: Any) -> None:
    """Safely close a client's connection and clear related state.

    - Closes any subscriber objects found in ``_subscribers`` (if a dict).
    - Calls ``close()`` on ``_session`` if present.
    - Clears ``_session``, ``_workspace`` (if present) and sets ``_connected`` to False.
    Errors during closing are caught and logged.
    """
    session = getattr(obj, "_session", None)
    if session is None:
        return

    try:
        # Close subscribers if the client exposes them
        subs = getattr(obj, "_subscribers", None)
        if isinstance(subs, dict):
            for sub in list(subs.values()):
                try:
                    sub.close()
                except Exception:
                    # best-effort close
                    pass
            subs.clear()

        # Close the session/workspace if they expose close
        try:
            session.close()
        except Exception:
            pass

        setattr(obj, "_session", None)
        if hasattr(obj, "_workspace"):
            setattr(obj, "_workspace", None)
        setattr(obj, "_connected", False)

        logger.info("Connection closed by client_utils.close_connection")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Error closing connection in client_utils: {exc}")
