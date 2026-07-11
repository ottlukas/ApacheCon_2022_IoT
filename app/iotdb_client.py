# -*- coding: utf-8 -*-
"""IoTDB client module for the IoT application.

Provides a wrapper for Apache IoTDB operations, supporting the IoTDB 2.x API.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import config

# Try to import IoTDB Session with version compatibility
try:
    from iotdb.Session import Session

    IOTDB_AVAILABLE = True
except ImportError:
    try:
        from iotdb import Session

        IOTDB_AVAILABLE = True
    except ImportError as exc:
        logging.warning("IoTDB library not available: %s", exc)
        IOTDB_AVAILABLE = False
        Session = None  # type: ignore[assignment]


# Specific IoTDB exceptions. We define narrow placeholder subclasses first so
# the code remains valid (and Pylint sees specific, non-broad catches) even on
# IoTDB versions that expose the exceptions at a different import path; the
# `from ... import` then overrides them with the real classes when available.
class IoTDBConnectionException(Exception):  # noqa: F811  (re-bound below)
    """Placeholder used until the real IoTDB class is imported."""


class StatementExecutionException(Exception):  # noqa: F811  (re-bound below)
    """Placeholder used until the real IoTDB class is imported."""


try:
    from iotdb.utils.exception import (  # type: ignore[no-redef]
        IoTDBConnectionException,
        StatementExecutionException,
    )
except ImportError:  # pragma: no cover - depends on iotdb version
    pass

logger = logging.getLogger(__name__)


@dataclass
class _ConnectionInfo:
    """Grouped connection parameters (host/port/credentials) for IoTDB."""

    host: str
    port: int
    user: str
    password: str


class IoTDBClient:
    """Client wrapper for Apache IoTDB."""

    def __init__(self) -> None:
        """Initialize the IoTDB client from application configuration."""
        self._session: Optional[Session] = None
        self._connected = False
        self._conn = _ConnectionInfo(
            host=config.IOTDB_HOST,
            port=config.IOTDB_PORT,
            user=config.IOTDB_USER,
            password=config.IOTDB_PASSWORD,
        )
        self._database = config.IOTDB_DATABASE
        self._device = config.IOTDB_DEVICE
        self._measurement = config.IOTDB_MEASUREMENT

    def connect(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """Connect to the IoTDB server.

        Args:
            host: IoTDB server host (overrides configuration if provided).
            port: IoTDB server port (overrides configuration if provided).
            username: Username for authentication (overrides configuration).
            password: Password for authentication (overrides configuration).

        Returns:
            True if the connection succeeded, False otherwise.
        """
        if not IOTDB_AVAILABLE:
            logger.error("IoTDB library is not installed")
            return False

        if host:
            self._conn.host = host
        if port is not None:
            self._conn.port = port
        if username:
            self._conn.user = username
        if password:
            self._conn.password = password

        try:
            self._session = Session(
                self._conn.host,
                int(self._conn.port),
                self._conn.user,
                self._conn.password,
            )
            self._session.open(False)  # False = do not fetch metadata
            self._connected = True
            logger.info("Connected to IoTDB at %s:%s", self._conn.host, self._conn.port)
            return True
        except (IoTDBConnectionException, OSError) as exc:
            logger.error("Error connecting to IoTDB: %s", exc)
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Return whether the client is currently connected to IoTDB."""
        return bool(self._connected and self._session is not None)

    def close(self) -> None:
        """Close the IoTDB connection (idempotent)."""
        if self._session is None:
            return

        try:
            self._session.close()
        except (IoTDBConnectionException, OSError) as exc:
            logger.debug("Error closing IoTDB session: %s", exc)
        finally:
            self._session = None
            self._connected = False
            logger.info("IoTDB connection closed")

    def initialize_schema(self) -> bool:
        """Initialize the database schema (storage group and time series).

        Returns:
            True if schema initialization succeeded, False otherwise.
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            # Create storage group / database if it does not exist
            try:
                create_db_sql = f"CREATE DATABASE {self._database}"
                self._session.execute_non_query_statement(create_db_sql)
                logger.debug("Database %s created", self._database)
            except StatementExecutionException as exc:
                # Tolerate an already-existing storage group
                if "already" in str(exc).lower():
                    logger.debug("Database %s already exists", self._database)
                else:
                    raise

            # Create time series if it does not exist
            full_ts_path = f"{self._device}.{self._measurement}"
            try:
                create_ts_sql = (
                    f"CREATE TIMESERIES {full_ts_path} " f"WITH DATATYPE=DOUBLE, ENCODING=PLAIN"
                )
                self._session.execute_non_query_statement(create_ts_sql)
                logger.debug("Timeseries %s created", full_ts_path)
            except StatementExecutionException as exc:
                if "already" in str(exc).lower():
                    logger.debug("Timeseries %s already exists", full_ts_path)
                else:
                    raise

            return True
        except StatementExecutionException as exc:
            logger.error("Error initializing schema: %s", exc)
            return False

    def insert_temperature(self, timestamp: Any, temperature: float) -> bool:
        """Insert a temperature reading into IoTDB.

        Args:
            timestamp: ISO format string, Unix timestamp string, or numeric
                timestamp (epoch milliseconds).
            temperature: Temperature value to insert.

        Returns:
            True if the insert succeeded, False otherwise.
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            # Convert the timestamp to epoch milliseconds for robustness
            try:
                if isinstance(timestamp, (int, float)):
                    if timestamp < 9999999999:  # epoch in seconds
                        ms_val = int(timestamp * 1000)
                    else:
                        ms_val = int(timestamp)
                elif str(timestamp).isdigit():
                    ms_val = int(timestamp)
                    if ms_val < 9999999999:
                        ms_val *= 1000
                else:
                    ts_clean = str(timestamp).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_clean)
                    ms_val = int(dt.timestamp() * 1000)
                timestamp_val = str(ms_val)
            except ValueError as exc:
                logger.warning(
                    "Failed to parse timestamp '%s', using current time: %s",
                    timestamp,
                    exc,
                )
                timestamp_val = str(int(time.time() * 1000))

            # SQL insert statement
            full_path = f"{self._device}"
            sql = (
                f"INSERT INTO {full_path}"
                f"(timestamp, {self._measurement}) "
                f"VALUES({timestamp_val}, {float(temperature)})"
            )
            self._session.execute_non_query_statement(sql)
            logger.debug("Inserted temperature: %s at %s", temperature, timestamp)
            return True
        except (StatementExecutionException, IoTDBConnectionException, OSError) as exc:
            logger.error("Error inserting temperature: %s", exc)
            return False

    def query_temperature(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Query temperature data from IoTDB (most recent first).

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of temperature records with ``timestamp`` and ``temperature``
            keys, or an empty list on error / when not connected.
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return []

        try:
            full_path = f"{self._device}.{self._measurement}"
            sql = (
                f"SELECT {self._measurement} FROM {self._device} "
                f"ORDER BY TIME DESC LIMIT {limit}"
            )
            result = self._session.execute_query_statement(sql)

            df = result.todf()
            records: List[Dict[str, Any]] = []

            if df is not None and len(df) > 0:
                target_col = self._resolve_column(df.columns, full_path)
                if target_col and target_col in df.columns:
                    for _, row in df.iterrows():
                        records.append(
                            {
                                "timestamp": str(row.get("Time", "")),
                                "temperature": float(row.get(target_col, 0.0)),
                            }
                        )

            logger.debug("Queried %d temperature records", len(records))
            return records
        except (StatementExecutionException, IoTDBConnectionException, OSError) as exc:
            logger.error("Error querying temperature: %s", exc)
            return []

    @staticmethod
    def _resolve_column(columns: Any, full_path: str) -> Optional[str]:
        """Find the dataframe column backing ``full_path`` (or its suffix)."""
        for col in columns:
            if col.lower() == full_path.lower():
                return col
        for col in columns:
            if col.endswith(full_path.split(".")[-1]):
                return col
        return None

    def get_latest_temperature(self) -> Optional[Dict[str, Any]]:
        """Return the latest temperature reading, or None if none found.

        Returns:
            Dictionary with ``timestamp`` and ``temperature``, or None.
        """
        records = self.query_temperature(limit=1)
        if records:
            return records[0]
        return None

    def execute_query(self, sql: str) -> Optional[Any]:
        """Execute a custom SQL query.

        Args:
            sql: SQL query to execute.

        Returns:
            The query result, or None on error / when not connected.
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return None

        try:
            return self._session.execute_query_statement(sql)
        except (StatementExecutionException, IoTDBConnectionException, OSError) as exc:
            logger.error("Error executing query %s: %s", sql, exc)
            return None

    def execute_non_query(self, sql: str) -> bool:
        """Execute a non-query SQL statement.

        Args:
            sql: SQL statement to execute.

        Returns:
            True if the statement succeeded, False otherwise.
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            self._session.execute_non_query_statement(sql)
            return True
        except (StatementExecutionException, IoTDBConnectionException, OSError) as exc:
            logger.error("Error executing non-query %s: %s", sql, exc)
            return False
