# -*- coding: utf-8 -*-
"""FastAPI application entrypoint integrating Panel dashboard."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import panel as pn

from app import config
from app.zenoh_client import ZenohClient
from app.iotdb_client import IoTDBClient
from app.dashboard import create_dashboard

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")

# Initialize global clients
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager for FastAPI startup and shutdown."""
    logger.info("Starting FastAPI application...")
    
    # Connect to Zenoh
    logger.info("Connecting to Zenoh endpoint: %s", config.ZENOH_ENDPOINT)
    zenoh_client.connect(peer=config.ZENOH_ENDPOINT)
    
    # Connect to IoTDB
    logger.info("Connecting to IoTDB at %s:%d", config.IOTDB_HOST, config.IOTDB_PORT)
    if iotdb_client.connect():
        # Initialize schema if connected
        logger.info("Initializing IoTDB database and timeseries schema...")
        iotdb_client.initialize_schema()
        
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down FastAPI application, closing connections...")
    zenoh_client.close()
    iotdb_client.close()


# Create FastAPI application
app = FastAPI(
    title="ApacheCon 2022 IoT Demo Portal",
    description="Portal featuring health checks and Panel dashboard integration",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root_redirect():
    """Redirect root path to the Panel dashboard."""
    return RedirectResponse(url="/panel")


@app.get("/health")
async def health():
    """Health check endpoint.

    Returns:
        JSON object containing status, timestamp and component connectivity.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zenoh_connected": zenoh_client.is_connected(),
        "iotdb_connected": iotdb_client.is_connected(),
    }


@app.get("/api/status")
async def api_status():
    """Status endpoint providing system and configuration metadata.

    Returns:
        JSON response with detailed connection statistics.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "zenoh": {
                "connected": zenoh_client.is_connected(),
                "endpoint": config.ZENOH_ENDPOINT,
                "key_expression": config.ZENOH_KEY_EXPRESSION
            },
            "iotdb": {
                "connected": iotdb_client.is_connected(),
                "host": config.IOTDB_HOST,
                "port": config.IOTDB_PORT,
                "database": config.IOTDB_DATABASE,
                "device": config.IOTDB_DEVICE
            }
        }
    }


# Integrate Panel application into FastAPI under /panel
def get_dashboard_app():
    """Factory function for Panel template creation."""
    return create_dashboard(zenoh_client, iotdb_client)


pn.io.fastapi.add_application("/panel", get_dashboard_app)
