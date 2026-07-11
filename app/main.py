# -*- coding: utf-8 -*-
"""FastAPI application entrypoint integrating Panel dashboard.

Panel FastAPI integration (Panel >= 1.3, bokeh-fastapi required):
  pn.io.fastapi.add_application is a decorator.  Usage:

    @pn.io.fastapi.add_application("/panel", app=fastapi_app, title="…")
    def factory():
        return <Panel viewable>

  This mounts a full Bokeh/Panel server at /panel inside the FastAPI process.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app import config
from app.dashboard import create_dashboard
from app.iotdb_client import IoTDBClient
from app.zenoh_client import ZenohClient
from app import simulator_controller

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Global service clients (one per process)
# ---------------------------------------------------------------------------
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Startup: open connections.  Shutdown: close them cleanly."""
    logger.info("Starting FastAPI application …")

    # Connect to Zenoh
    logger.info("Connecting to Zenoh endpoint: %s", config.ZENOH_ENDPOINT)
    if zenoh_client.connect(peer=config.ZENOH_ENDPOINT):
        logger.info("Zenoh connected successfully")
    else:
        logger.warning("Zenoh connection failed – dashboard will show disconnected status")

    # Connect to IoTDB and initialise schema
    logger.info("Connecting to IoTDB at %s:%d", config.IOTDB_HOST, config.IOTDB_PORT)
    if iotdb_client.connect():
        logger.info("IoTDB connected, initialising schema …")
        iotdb_client.initialize_schema()
    else:
        logger.warning("IoTDB connection failed – dashboard will show disconnected status")

    yield

    # Cleanup
    logger.info("Shutting down FastAPI application, closing connections …")
    zenoh_client.close()
    iotdb_client.close()
    logger.info("Connections closed")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ApacheCon 2022 IoT Demo Portal",
    description="Portal featuring health checks and Panel dashboard integration",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root_redirect():
    """Redirect root path to the Panel dashboard."""
    return RedirectResponse(url="/panel")


@app.get("/health")
async def health():
    """Health check endpoint.

    Returns:
        JSON object with status, timestamp and component connectivity.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zenoh_connected": zenoh_client.is_connected(),
        "iotdb_connected": iotdb_client.is_connected(),
    }


@app.get("/api/status")
async def api_status():
    """Detailed status endpoint with service configuration metadata.

    Returns:
        JSON response with connection statistics for each service.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "zenoh": {
                "connected": zenoh_client.is_connected(),
                "endpoint": config.ZENOH_ENDPOINT,
                "key_expression": config.ZENOH_KEY_EXPRESSION,
            },
            "iotdb": {
                "connected": iotdb_client.is_connected(),
                "host": config.IOTDB_HOST,
                "port": config.IOTDB_PORT,
                "database": config.IOTDB_DATABASE,
                "device": config.IOTDB_DEVICE,
            },
        },
        "simulator": simulator_controller.simulator_status(),
    }


# ---------------------------------------------------------------------------
# Sensor simulator control endpoints
#
# The dashboard container is the natural home for the simulator: in Docker it
# shares the network with the Zenoh broker, so it can publish directly. These
# endpoints wrap ``app.simulator_controller`` which spawns the simulator as a
# subprocess and captures its stdout into a rolling log.
# ---------------------------------------------------------------------------

@app.post("/api/simulator/start")
async def api_simulator_start():
    """Start the sensor simulator subprocess (idempotent)."""
    return simulator_controller.start_simulator()


@app.post("/api/simulator/stop")
async def api_simulator_stop():
    """Stop the sensor simulator subprocess (idempotent)."""
    return simulator_controller.stop_simulator()


@app.get("/api/simulator/status")
async def api_simulator_status():
    """Return whether the simulator is running and a detail message."""
    return simulator_controller.simulator_status()


@app.get("/api/simulator/log")
async def api_simulator_log(tail: int = 200):
    """Return the rolling log lines captured from the simulator subprocess."""
    return simulator_controller.get_log(tail=tail)


# ---------------------------------------------------------------------------
# Panel dashboard – mounted at /panel via bokeh-fastapi decorator
#
# pn.io.fastapi.add_application is a decorator that:
#   1. Registers the factory with BokehFastAPI.
#   2. Mounts the Panel/Bokeh ASGI handler at the given path on `app`.
#
# The import is deferred to here so the module-level side-effects in
# panel.io.fastapi (bokeh_fastapi dependency check) only run inside the
# actual dashboard container – not in test collection or the bridge process.
# ---------------------------------------------------------------------------

try:
    import panel as pn  # noqa: E402

    # Side-effect import: triggers the bokeh-fastapi availability check early.
    import panel.io.fastapi  # noqa: F401,E402  # pylint: disable=unused-import

    @pn.io.fastapi.add_application("/panel", app=app, title="IoT Stream Analysis Dashboard")
    def _dashboard_factory():
        """Panel factory – called once per browser session."""
        return create_dashboard(zenoh_client, iotdb_client)

    logger.info("Panel dashboard mounted at /panel")
except ImportError as exc:
    logger.error(
        "Could not mount Panel dashboard (bokeh-fastapi missing?): %s. "
        "Install it with: pip install bokeh-fastapi",
        exc,
    )
