#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IoTDB client module for the ApacheCon 2022 IoT Demo.

This module provides a wrapper for Apache IoTDB operations with support
for IoTDB 2.x API.
"""

import logging
from typing import Optional, List, Any, Dict
import time
from client_utils import is_connected as util_is_connected, close_connection as util_close_connection

# Try to import IoTDB Session with version compatibility
try:
    from iotdb.Session import Session
    IOTDB_AVAILABLE = True
except ImportError:
    try:
        # Try alternative import for IoTDB 2.x
        from iotdb import Session
        IOTDB_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"IoTDB library not available: {e}")
        IOTDB_AVAILABLE = False
        Session = None

logger = logging.getLogger(__name__)


class IoTDBClient:
    """
    Client for interacting with Apache IoTDB.
    
    Supports IoTDB 2.x API.
    """
    
    # Default configuration
    DEFAULT_STORAGE_GROUP = "root.myfactory"
    DEFAULT_TIMESERIES = "machine1.temperature"
    
    def __init__(self):
        """Initialize the IoTDB client."""
        self._session: Optional[Session] = None
        self._connected = False
        self._config = {
            'host': '127.0.0.1',
            'port': '6667',
            'username': 'root',
            'password': 'root'
        }
    
    def connect(
        self,
        host: str = "127.0.0.1",
        port: str = "6667",
        username: str = "root",
        password: str = "root"
    ) -> bool:
        """
        Connect to IoTDB server.
        
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
        
        try:
            self._config = {
                'host': host,
                'port': port,
                'username': username,
                'password': password
            }
            
            self._session = Session(host, port, username, password)
            self._session.open(False)  # False = do not fetch metadata
            self._connected = True
            logger.info(f"Successfully connected to IoTDB at {host}:{port}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to IoTDB: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if client is connected to IoTDB."""
        return util_is_connected(self)
    
    def close(self):
        """Close the IoTDB connection."""
        util_close_connection(self)
    
    def initialize_schema(self, storage_group: str = None, timeseries: str = None) -> bool:
        """
        Initialize the database schema (storage group and time series).
        
        Args:
            storage_group: Storage group path (default: root.myfactory)
            timeseries: Time series path (default: machine1.temperature)
            
        Returns:
            True if schema initialization succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False
        
        try:
            sg = storage_group or self.DEFAULT_STORAGE_GROUP
            ts = timeseries or self.DEFAULT_TIMESERIES
            full_ts_path = f"{sg}.{ts}"
            
            # Create storage group if not exists
            create_sg_sql = f"SET STORAGE GROUP TO {sg}"
            self._session.execute_non_query_statement(create_sg_sql)
            logger.debug(f"Storage group {sg} created or already exists")
            
            # Create time series if not exists
            create_ts_sql = (
                f"CREATE TIMESERIES {full_ts_path} "
                f"WITH DATATYPE=INT32, ENCODING=PLAIN"
            )
            self._session.execute_non_query_statement(create_ts_sql)
            logger.debug(f"Time series {full_ts_path} created or already exists")
            
            return True
            
        except Exception as e:
            # Ignore errors if schema already exists
            error_msg = str(e).lower()
            if "already exists" in error_msg or "timeseries already exist" in error_msg:
                logger.debug(f"Schema already exists: {e}")
                return True
            logger.error(f"Error initializing schema: {e}")
            return False
    
    def insert_temperature(self, timestamp: str, temperature: float) -> bool:
        """
        Insert a temperature reading into IoTDB.
        
        Args:
            timestamp: ISO format timestamp or Unix timestamp
            temperature: Temperature value
            
        Returns:
            True if insert succeeded, False otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return False
        
        try:
            # Convert timestamp to proper format if needed
            if timestamp.isdigit():
                # Unix timestamp in milliseconds
                timestamp_str = timestamp
            else:
                # ISO format or other string format
                timestamp_str = f"'{timestamp}'"
            
            sql = (
                f"INSERT INTO {self.DEFAULT_STORAGE_GROUP}.{self.DEFAULT_TIMESERIES} "
                f"(timestamp,temperature) values({timestamp_str}, {int(temperature)})"
            )
            
            self._session.execute_non_query_statement(sql)
            logger.debug(f"Inserted temperature: {temperature} at {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting temperature: {e}")
            return False
    
    def query_temperature(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query temperature data from IoTDB.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of temperature records with timestamp and value
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return []
        
        try:
            sql = (
                f"SELECT * FROM {self.DEFAULT_STORAGE_GROUP}.{self.DEFAULT_TIMESERIES} "
                f"ORDER BY TIME DESC limit {limit}"
            )
            
            result = self._session.execute_query_statement(sql)
            
            # Convert to list of dictionaries
            df = result.todf()
            records = []
            
            if df is not None and len(df) > 0:
                # Extract temperature column
                temp_col = f"{self.DEFAULT_STORAGE_GROUP}.{self.DEFAULT_TIMESERIES}"
                if temp_col in df.columns:
                    for idx, row in df.iterrows():
                        records.append({
                            'timestamp': str(row.get('Time', '')),
                            'temperature': float(row.get(temp_col, 0))
                        })
            
            logger.debug(f"Queried {len(records)} temperature records")
            return records
            
        except Exception as e:
            logger.error(f"Error querying temperature: {e}")
            return []
    
    def get_latest_temperature(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest temperature reading from IoTDB.
        
        Returns:
            Dictionary with timestamp and temperature, or None if not found
        """
        records = self.query_temperature(limit=1)
        if records and len(records) > 0:
            return records[0]
        return None
    
    def execute_query(self, sql: str) -> Optional[Any]:
        """
        Execute a custom SQL query.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Query result or None if error
        """
        if not self.is_connected():
            logger.error("Not connected to IoTDB")
            return None
        
        try:
            result = self._session.execute_query_statement(sql)
            return result
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return None
    
    def execute_non_query(self, sql: str) -> bool:
        """
        Execute a non-query SQL statement.
        
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
            logger.error(f"Error executing non-query: {e}")
            return False
