# -*- coding: utf-8 -*-
"""Standalone Panel dashboard script for ApacheCon 2022 IoT Demo.

Provides a real-time web-based visualization of Zenoh streams and Apache IoTDB time-series data.
Can be started with:
    panel serve panel_script.py --autoreload --show
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import panel as pn

from app import config
from app.zenoh_client import ZenohClient, decode_payload
from app.iotdb_client import IoTDBClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("panel_script")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Zenoh configuration
ZENOH_KEY_EXPR = os.getenv("ZENOH_KEY_EXPRESSION", config.ZENOH_KEY_EXPRESSION)
ZENOH_ENDPOINT = os.getenv("ZENOH_HOST_ENDPOINT", config.ZENOH_HOST_ENDPOINT)

# IoTDB configuration
IOTDB_HOST = os.getenv("IOTDB_HOST", "127.0.0.1")  # Connect to localhost for local execution
IOTDB_PORT = int(os.getenv("IOTDB_PORT", str(config.IOTDB_PORT)))
IOTDB_USER = os.getenv("IOTDB_USER", config.IOTDB_USER)
IOTDB_PASSWORD = os.getenv("IOTDB_PASSWORD", config.IOTDB_PASSWORD)
IOTDB_DEVICE = os.getenv("IOTDB_DEVICE", config.IOTDB_DEVICE)
IOTDB_MEASUREMENT = os.getenv("IOTDB_MEASUREMENT", config.IOTDB_MEASUREMENT)
IOTDB_TIMESERIES = f"{IOTDB_DEVICE}.{IOTDB_MEASUREMENT}"

# Buffer and Refresh configurations
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", "100"))
UI_REFRESH_INTERVAL_MS = int(os.getenv("UI_REFRESH_INTERVAL_MS", "1000"))
IOTDB_REFRESH_INTERVAL_MS = int(os.getenv("IOTDB_REFRESH_INTERVAL_MS", "2000"))

# ---------------------------------------------------------------------------
# Shared Buffers and State
# ---------------------------------------------------------------------------
zenoh_points: deque = deque(maxlen=BUFFER_SIZE)
iotdb_points: deque = deque(maxlen=BUFFER_SIZE)

state = {
    "zenoh_connected": False,
    "iotdb_connected": False,
    "last_zenoh_timestamp": "N/A",
    "last_zenoh_val": None,
    "last_iotdb_refresh": "N/A",
    "last_iotdb_error": "",
    "latest_logs": deque(maxlen=5),
}

# ---------------------------------------------------------------------------
# ECharts helper
# ---------------------------------------------------------------------------
def create_echarts_option(
    title: str,
    x_data: List[str],
    y_data: List[float],
    series_name: str,
    color: str,
) -> Dict[str, Any]:
    """Create ECharts configuration dictionary for a line chart.

    Args:
        title: Chart title text.
        x_data: X-axis categories (timestamps).
        y_data: Y-axis values.
        series_name: Name of the telemetry series.
        color: Line color in hex.

    Returns:
        ECharts option dictionary.
    """
    return {
        "title": {
            "text": title,
            "textStyle": {"color": "#ffffff", "fontSize": 16},
            "left": "center",
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
        },
        "xAxis": {
            "type": "category",
            "data": x_data,
            "axisLabel": {"color": "#aaaaaa"},
            "axisLine": {"lineStyle": {"color": "#555555"}},
        },
        "yAxis": {
            "type": "value",
            "scale": True,
            "axisLabel": {"color": "#aaaaaa"},
            "axisLine": {"lineStyle": {"color": "#555555"}},
            "splitLine": {"lineStyle": {"color": "#333333"}},
        },
        "series": [
            {
                "name": series_name,
                "type": "line",
                "data": y_data,
                "smooth": True,
                "showSymbol": True,
                "itemStyle": {"color": color},
                "lineStyle": {"width": 3},
            }
        ],
        "backgroundColor": "transparent",
    }

# ---------------------------------------------------------------------------
# UI component initialization
# ---------------------------------------------------------------------------
pn.extension("echarts", sizing_mode="stretch_width", template="fast", theme="dark")
ACCENT = "orange"
pn.state.template.param.update(
    site="Apache Con 2022",
    title="IoT Live Stream & Historical Dashboard",
    sidebar_width=250,
    accent_base_color=ACCENT,
    header_background=ACCENT,
    font="Montserrat",
)

# Define chart panes with empty initial state
zenoh_chart_pane = pn.pane.ECharts(
    create_echarts_option("Live Zenoh Stream", [], [], "Temperature", "#ff9800"),
    height=400,
    sizing_mode="stretch_width",
)

iotdb_chart_pane = pn.pane.ECharts(
    create_echarts_option("Live IoTDB Time Series", [], [], "Temperature", "#2196f3"),
    height=400,
    sizing_mode="stretch_width",
)

# Status panes
zenoh_status_pane = pn.pane.Markdown("### Zenoh Status\n🔴 Disconnected")
iotdb_status_pane = pn.pane.Markdown("### IoTDB Status\n🔴 Disconnected")
log_pane = pn.pane.Markdown("### Recent Logs\n* Waiting for events...")

# ---------------------------------------------------------------------------
# Logic and tasks
# ---------------------------------------------------------------------------
def log_message(msg: str) -> None:
    """Log to console and display in the UI debug log panel."""
    logger.info(msg)
    timestamp = datetime.now().strftime("%H:%M:%S")
    state["latest_logs"].append(f"[{timestamp}] {msg}")
    log_pane.object = "### Recent Logs\n" + "\n".join(f"* {m}" for m in reversed(state["latest_logs"]))

def parse_zenoh_payload(payload_str: str) -> Tuple[float, str]:
    """Parse payload string into value and timestamp.

    Accepts Pydantic SensorReading JSON format or raw numeric string.
    """
    try:
        data = json.loads(payload_str)
        if isinstance(data, dict):
            val = float(data.get("value", 0.0))
            ts_raw = data.get("timestamp", "")
            if ts_raw:
                try:
                    dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    ts_display = dt.strftime("%H:%M:%S")
                except Exception:
                    ts_display = ts_raw
            else:
                ts_display = datetime.now().strftime("%H:%M:%S")
            return val, ts_display
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback to parsing raw float value
    val = float(payload_str)
    ts_display = datetime.now().strftime("%H:%M:%S")
    return val, ts_display

def on_zenoh_message(sample: Any) -> None:
    """Asynchronous callback triggered when a Zenoh sample is received."""
    payload_str = decode_payload(sample)
    if payload_str is None:
        return

    try:
        val, ts_display = parse_zenoh_payload(payload_str)
        state["last_zenoh_val"] = val
        state["last_zenoh_timestamp"] = ts_display
        zenoh_points.append((ts_display, val))
    except Exception as exc:
        logger.error("Error parsing Zenoh message in dashboard: %s", exc)

def start_zenoh_subscriber(client: ZenohClient, key_expr: str, callback: Callable) -> bool:
    """Start Zenoh subscriber and register callback."""
    if client.is_connected():
        sub = client.get_subscriber(key_expr, callback)
        if sub is not None:
            log_message(f"Subscribed to Zenoh expression: '{key_expr}'")
            return True
    return False

def query_iotdb_latest_values(client: IoTDBClient, limit: int) -> List[Dict[str, Any]]:
    """Query recent values from IoTDB.

    Returns:
        List of dicts containing timestamp and temperature value.
    """
    if not client.is_connected():
        return []
    try:
        return client.query_temperature(limit=limit)
    except Exception as exc:
        state["last_iotdb_error"] = str(exc)
        logger.error("Error querying IoTDB: %s", exc)
        return []

def update_zenoh_chart(points: deque, chart_pane: pn.pane.ECharts) -> None:
    """Update Zenoh ECharts pane data."""
    if not points:
        return

    # Extract time series points from buffer
    times = [pt[0] for pt in points]
    values = [pt[1] for pt in points]

    # Mutate data dict in-place and trigger Panel ECharts refresh
    chart_pane.data["xAxis"]["data"] = times
    chart_pane.data["series"][0]["data"] = values
    chart_pane.param.trigger("data")

def update_iotdb_chart(points: List[Dict[str, Any]], chart_pane: pn.pane.ECharts) -> None:
    """Update IoTDB ECharts pane data."""
    if not points:
        return

    times = []
    values = []

    # IoTDB queries usually return newest-first (ORDER BY TIME DESC).
    # We reverse it to display chronologically (left-to-right).
    chronological_points = list(reversed(points))

    for pt in chronological_points:
        ts_raw = pt.get("timestamp", "")
        if ts_raw:
            try:
                if str(ts_raw).isdigit():
                    dt = datetime.fromtimestamp(int(ts_raw) / 1000.0)
                else:
                    dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                ts_display = dt.strftime("%H:%M:%S")
            except Exception:
                ts_display = str(ts_raw)
        else:
            ts_display = ""
        times.append(ts_display)
        values.append(pt.get("temperature", 0.0))

    # Mutate data dict in-place and trigger ECharts refresh
    chart_pane.data["xAxis"]["data"] = times
    chart_pane.data["series"][0]["data"] = values
    chart_pane.param.trigger("data")

# ---------------------------------------------------------------------------
# Clients and execution callbacks
# ---------------------------------------------------------------------------
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()

def refresh_zenoh_ui() -> None:
    """Periodic Panel callback to update Zenoh chart & connection status."""
    z_ok = zenoh_client.is_connected()
    state["zenoh_connected"] = z_ok

    if z_ok:
        zenoh_status_pane.object = f"""### Zenoh Status
🟢 Connected
* **Last Message**: {state['last_zenoh_val']} °C
* **Time Received**: {state['last_zenoh_timestamp']}
* **Key Expression**: `{ZENOH_KEY_EXPR}`"""
    else:
        zenoh_status_pane.object = f"""### Zenoh Status
🔴 Disconnected
* **Endpoint**: `{ZENOH_ENDPOINT}`
* Will attempt reconnect on next refresh cycle..."""
        # Attempt reconnect — wrapped defensively so it never blocks or crashes the UI
        try:
            if zenoh_client.connect(peer=ZENOH_ENDPOINT):
                log_message("Zenoh reconnected successfully.")
                start_zenoh_subscriber(zenoh_client, ZENOH_KEY_EXPR, on_zenoh_message)
        except Exception as e:
            logger.debug("Zenoh reconnect attempt skipped: %s", e)

    # Refresh the UI chart
    update_zenoh_chart(zenoh_points, zenoh_chart_pane)

def refresh_iotdb_ui() -> None:
    """Periodic Panel callback to query database and update IoTDB chart."""
    i_ok = iotdb_client.is_connected()
    state["iotdb_connected"] = i_ok

    if not i_ok:
        iotdb_status_pane.object = f"""### IoTDB Status
🔴 Disconnected
* **Host**: `{IOTDB_HOST}:{IOTDB_PORT}`
* Attempting reconnect in background..."""
        try:
            if iotdb_client.connect(host=IOTDB_HOST, port=IOTDB_PORT, username=IOTDB_USER, password=IOTDB_PASSWORD):
                log_message("IoTDB reconnected successfully.")
                iotdb_client.initialize_schema()
        except Exception as e:
            logger.debug("Failed to reconnect to IoTDB: %s", e)
        return

    # Query and update
    records = query_iotdb_latest_values(iotdb_client, limit=BUFFER_SIZE)
    state["last_iotdb_refresh"] = datetime.now().strftime("%H:%M:%S")

    if records:
        state["last_iotdb_error"] = ""
        iotdb_status_pane.object = f"""### IoTDB Status
🟢 Connected
* **Latest Value**: {records[0].get('temperature')} °C
* **Last Query**: {state['last_iotdb_refresh']}
* **Timeseries Path**: `{IOTDB_TIMESERIES}`"""
        update_iotdb_chart(records, iotdb_chart_pane)
    else:
        err_msg = state["last_iotdb_error"]
        status_text = "🟢 Connected (No Data)" if not err_msg else f"⚠️ Connected (Query Error: {err_msg})"
        iotdb_status_pane.object = f"""### IoTDB Status
{status_text}
* **Last Query Attempt**: {state['last_iotdb_refresh']}
* **Timeseries Path**: `{IOTDB_TIMESERIES}`"""

# ---------------------------------------------------------------------------
# Dashboard Builder
# ---------------------------------------------------------------------------
def build_dashboard() -> pn.layout.Column:
    """Assemble status headers, charts, and layout components into a single column."""
    # Description Markdown
    description = pn.pane.Markdown(
        "This interactive dashboard visualizes telemetry data streams from two independent live sources: "
        "real-time data direct from Eclipse Zenoh, and persisted historical records from Apache IoTDB."
    )

    # Status indicators row
    status_row = pn.Row(
        pn.Card(zenoh_status_pane, title="Zenoh Connection", margin=5, sizing_mode="stretch_width"),
        pn.Card(iotdb_status_pane, title="Apache IoTDB Connection", margin=5, sizing_mode="stretch_width"),
        sizing_mode="stretch_width",
    )

    # Chart display row
    chart_row = pn.Row(
        pn.Card(zenoh_chart_pane, title="Live Zenoh Stream", margin=5, sizing_mode="stretch_width"),
        pn.Card(iotdb_chart_pane, title="Live IoTDB Time Series", margin=5, sizing_mode="stretch_width"),
        sizing_mode="stretch_width",
    )

    # Assemble into main Column
    main_layout = pn.Column(
        description,
        status_row,
        chart_row,
        pn.Card(log_pane, title="Developer Log", collapsed=True, margin=5),
        sizing_mode="stretch_width",
    )
    return main_layout

# Setup sidebar logo & config details
logo_path = os.path.join(PROJECT_ROOT, "app", "asf-estd-1999-logo.jpg")
if os.path.exists(logo_path):
    pn.pane.JPG(logo_path, sizing_mode="scale_width", embed=True).servable(area="sidebar")

pn.pane.Markdown(
    f"""# System Settings
* **Zenoh Key**: `{ZENOH_KEY_EXPR}`
* **Zenoh Endpoint**: `{ZENOH_ENDPOINT}`
* **IoTDB Host**: `{IOTDB_HOST}:{IOTDB_PORT}`
* **IoTDB Timeseries**: `{IOTDB_TIMESERIES}`
* **Buffer Limit**: `{BUFFER_SIZE}`
"""
).servable(area="sidebar")

# Initialize and Connect
log_message("Initializing Dashboard connection services...")
try:
    if zenoh_client.connect(peer=ZENOH_ENDPOINT):
        log_message("Connected to Zenoh router.")
        start_zenoh_subscriber(zenoh_client, ZENOH_KEY_EXPR, on_zenoh_message)
    else:
        log_message("Failed to connect to Zenoh at startup. Will retry in background.")
except Exception as e:
    log_message(f"Zenoh connection error: {e}")

try:
    if iotdb_client.connect(host=IOTDB_HOST, port=IOTDB_PORT, username=IOTDB_USER, password=IOTDB_PASSWORD):
        log_message("Connected to IoTDB.")
        iotdb_client.initialize_schema()
    else:
        log_message("Failed to connect to IoTDB at startup. Will retry in background.")
except Exception as e:
    log_message(f"IoTDB connection error: {e}")

# Register Periodic UI updates
pn.state.add_periodic_callback(refresh_zenoh_ui, UI_REFRESH_INTERVAL_MS)
pn.state.add_periodic_callback(refresh_iotdb_ui, IOTDB_REFRESH_INTERVAL_MS)

# Serve the final layout
build_dashboard().servable()
