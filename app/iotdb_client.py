# -*- coding: utf-8 -*-
"""IoTDB client module for the IoT application.

Provides wrapper for Apache IoTDB operations, supporting IoTDB 2.x API.
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Any, Dict
from app import config

# Try to import IoTDB Session with version compatibility
try:
    from iotdb.Session import Session
    IOTDB_AVAILABLE = True
except ImportError:
    try:
        from iotdb import Session
        IOTDB_AVAILABLE = True
    except ImportError as e:
        logging.warning("IoTDB library not available: %s", e)
        IOTDB_AVAILABLE = False
        Session = None

logger = logging.getLogger(__name__)


class IoTDBClient:
    """Client wrapper for Apache IoTDB."""

    def __init__(self):
        """Initialize the IoTDB client."""
        self._session: Optional[Session] = None
        self._connected = False
        self._host = config.IOTDB_HOST
        self._port = config.IOTDB_PORT
        self._user = config.IOTDB_USER
        self._password = config.IOTDB_PASSWORD
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
        """Connect to IoTDB server.

        Args:
            host: IoTDB server host
            port: IoTDB server port
            username: Username for authentication
            password: Password for authentication

        Returns:
            True if connection succeeded, False otherwise
        """
        if not IOTDB_AVAILABLE:
            logger.error("IoTDB library is not installed")
            return False

        if host:
            self._host = host
        if port is not None:
            self._port = port
        if username:
            self._user = username
        if password:
            self._password = password

        try:
            self._session = Session(self._host, str(self._port), self._user, self._password)
            self._session.open(False)  # False = do not fetch metadata
            self._connected = True
            logger.info("Successfully connected to IoTDB at %s:%s", self._host, self._port)
            return True
        except Exception as e:
            logger.error("Error connecting to IoTDB: %s", e)
            self._connected = False
            return False

    def is_connected(self) -> bool:
        """Check if client is connected to IoTDB."""
        return bool(self._connected and self._session is not None)

    def close(self):
        """Close the IoTDB connection."""
        if self._session is None:
            return

        try:
            self._session.close()
        except Exception as e:
            logger.debug("Error closing IoTDB session: %s", e)
        finally:
            self._session = None
            self._connected = False
            logger.info("IoTDB connection closed")

    def initialize_schema(self) -> bool:
        """Initialize the database schema (storage group and time series).

        Returns:
            True if schema initialization succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            # Create storage group / database if not exists
            try:
                create_db_sql = f"CREATE DATABASE {self._database}"
                self._session.execute_non_query_statement(create_db_sql)
                logger.debug("Database %s created", self._database)
            except Exception as e:
                # Handle cases where storage group already exists
                if "already" in str(e).lower():
                    logger.debug("Database %s already exists", self._database)
                else:
                    raise e

            # Create time series if not exists
            full_ts_path = f"{self._device}.{self._measurement}"
            try:
                create_ts_sql = f"CREATE TIMESERIES {full_ts_path} WITH DATATYPE=DOUBLE, ENCODING=PLAIN"
                self._session.execute_non_query_statement(create_ts_sql)
                logger.debug("Timeseries %s created", full_ts_path)
            except Exception as e:
                if "already" in str(e).lower():
                    logger.debug("Timeseries %s already exists", full_ts_path)
                else:
                    raise e

            return True
        except Exception as e:
            logger.error("Error initializing schema: %s", e)
            return False

    def insert_temperature(self, timestamp: Any, temperature: float) -> bool:
        """Insert a temperature reading into IoTDB.

        Args:
            timestamp: ISO format string, Unix timestamp string, or numeric timestamp (ms)
            temperature: Temperature value

        Returns:
            True if insert succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            # Convert timestamp to epoch milliseconds for robustness in IoTDB
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
            except Exception as ts_exc:
                logger.warning("Failed to parse timestamp '%s', falling back to current time: %s", timestamp, ts_exc)
                timestamp_val = str(int(time.time() * 1000))

            # SQL insert statement
            full_path = f"{self._device}"
            sql = f"INSERT INTO {full_path}(timestamp, {self._measurement}) VALUES({timestamp_val}, {float(temperature)})"
            self._session.execute_non_query_statement(sql)
            logger.debug("Inserted temperature: %s at %s", temperature, timestamp)
            return True
        except Exception as e:
            logger.error("Error inserting temperature: %s", e)
            return False

    def query_temperature(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Query temperature data from IoTDB.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of temperature records with timestamp and value
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return []

        try:
            full_path = f"{self._device}.{self._measurement}"
            sql = f"SELECT {self._measurement} FROM {self._device} ORDER BY TIME DESC LIMIT {limit}"
            result = self._session.execute_query_statement(sql)

            df = result.todf()
            records = []

            if df is not None and len(df) > 0:
                # Find matching column
                target_col = None
                for col in df.columns:
                    if col.lower() == full_path.lower():
                        target_col = col
                        break

                if target_col is None:
                    # Fallback to checking suffix
                    for col in df.columns:
                        if col.endswith(self._measurement):
                            target_col = col
                            break

                if target_col and target_col in df.columns:
                    for _, row in df.iterrows():
                        records.append({
                            "timestamp": str(row.get("Time", "")),
                            "temperature": float(row.get(target_col, 0.0)),
                        })

            logger.debug("Queried %d temperature records", len(records))
            return records
        except Exception as e:
            logger.error("Error querying temperature: %s", e)
            return []

    def get_latest_temperature(self) -> Optional[Dict[str, Any]]:
        """Get the latest temperature reading from IoTDB.

        Returns:
            Dictionary with timestamp and temperature, or None if not found
        """
        records = self.query_temperature(limit=1)
        if records:
            return records[0]
        return None

    def execute_query(self, sql: str) -> Optional[Any]:
        """Execute a custom SQL query.

        Args:
            sql: SQL query to execute

        Returns:
            Query result or None if error
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return None

        try:
            return self._session.execute_query_statement(sql)
        except Exception as e:
            logger.error("Error executing query %s: %s", sql, e)
            return None

    def execute_non_query(self, sql: str) -> bool:
        """Execute a non-query SQL statement.

        Args:
            sql: SQL statement to execute

        Returns:
            True if succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False

        try:
            self._session.execute_non_query_statement(sql)
            return True
        except Exception as e:
            logger.error("Error executing non-query %s: %s", sql, e)
            return False
