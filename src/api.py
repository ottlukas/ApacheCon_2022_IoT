#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API module for the ApacheCon 2022 IoT Demo.

This module provides REST API endpoints for interacting with Zenoh and IoTDB.
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import client modules
from .zenoh_client import ZenohClient
from .iotdb_client import IoTDBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
# pylint: disable=trailing-whitespace,broad-except

# Initialize clients
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """FastAPI lifespan handling for startup and shutdown."""
    try:
        # Initialize Zenoh client
        zenoh_peer = os.getenv("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
        zenoh_client.connect(peer=zenoh_peer)
        logger.info("Connected to Zenoh router at %s", zenoh_peer)

        # Initialize IoTDB client
        iotdb_host = os.getenv("IOTDB_HOST", "127.0.0.1")
        iotdb_port = os.getenv("IOTDB_PORT", "6667")
        iotdb_username = os.getenv("IOTDB_USERNAME", "root")
        iotdb_password = os.getenv("IOTDB_PASSWORD", "root")
        iotdb_client.connect(
            host=iotdb_host, port=iotdb_port, username=iotdb_username, password=iotdb_password
        )
        logger.info("Connected to IoTDB at %s:%s", iotdb_host, iotdb_port)

        # Initialize schema
        iotdb_client.initialize_schema()
        logger.info("IoTDB schema initialized")

        yield
    finally:
        try:
            zenoh_client.close()
            iotdb_client.close()
            logger.info("Clients closed successfully")
        except Exception as e:
            logger.error("Error during shutdown: %s", e)


# Create FastAPI app
app = FastAPI(
    title="ApacheCon 2022 IoT Demo API",
    description="API for interacting with Zenoh and Apache IoTDB",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "zenoh_connected": zenoh_client.is_connected(),
        "iotdb_connected": iotdb_client.is_connected(),
    }


@app.get("/zenoh/publish")
async def publish_to_zenoh(
    path: str = Query("/myfactory/machine1/temp", description="Zenoh path to publish to"),
    value: str = Query("25", description="Value to publish"),
):
    """Publish a value to a Zenoh path."""
    try:
        zenoh_client.publish(path, value)
        return {"status": "success", "path": path, "value": value}
    except Exception as e:
        logger.error("Error publishing to Zenoh: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/zenoh/get")
async def get_from_zenoh(
    path: str = Query("/myfactory/machine1/temp", description="Zenoh path to get value from")
):
    """Get the latest value from a Zenoh path."""
    try:
        value = zenoh_client.get(path)
        if value is None:
            raise HTTPException(status_code=404, detail="No value found at path")
        return {"path": path, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting from Zenoh: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/zenoh/subscribe")
async def subscribe_to_zenoh(
    path: str = Query("/myfactory/machine1/temp", description="Zenoh path to subscribe to")
):
    """Subscribe to a Zenoh path and return recent values."""
    try:
        values = zenoh_client.subscribe(path, timeout=5.0)
        return {"path": path, "values": values}
    except Exception as e:
        logger.error("Error subscribing to Zenoh: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/iotdb/insert")
async def insert_into_iotdb(
    timestamp: Optional[str] = None,
    temperature: float = Query(25.0, description="Temperature value to insert"),
):
    """Insert a temperature reading into IoTDB."""
    try:
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()

        iotdb_client.insert_temperature(timestamp, temperature)
        return {"status": "success", "timestamp": timestamp, "temperature": temperature}
    except Exception as e:
        logger.error("Error inserting into IoTDB: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/iotdb/query")
async def query_iotdb(limit: int = Query(10, description="Number of records to return")):
    """Query temperature data from IoTDB."""
    try:
        results = iotdb_client.query_temperature(limit=limit)
        return {"results": results}
    except Exception as e:
        logger.error("Error querying IoTDB: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/iotdb/latest")
async def get_latest_temperature():
    """Get the latest temperature reading from IoTDB."""
    try:
        result = iotdb_client.get_latest_temperature()
        if result is None:
            raise HTTPException(status_code=404, detail="No temperature data found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting latest temperature: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/sync")
async def sync_zenoh_to_iotdb():
    """Synchronize data from Zenoh to IoTDB."""
    try:
        # Get latest value from Zenoh
        zenoh_value = zenoh_client.get("/myfactory/machine1/temp")
        if zenoh_value is None:
            raise HTTPException(status_code=404, detail="No value found in Zenoh")

        # Insert into IoTDB
        timestamp = datetime.utcnow().isoformat()
        iotdb_client.insert_temperature(timestamp, float(zenoh_value))

        return {"status": "success", "zenoh_value": zenoh_value, "timestamp": timestamp}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error syncing data: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


def main():
    """Run the API server."""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))

    # pylint: disable=broad-except
    logger.info("Starting API server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
