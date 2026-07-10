# -*- coding: utf-8 -*-
"""Dashboard layout and plotting components using Panel + Apache ECharts."""

import collections
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import panel as pn

from app import config
from app.zenoh_client import ZenohClient, decode_payload
from app.iotdb_client import IoTDBClient

logger = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# Panel global configuration (called once per process)
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
    """Create ECharts configuration dictionary for a line chart."""
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
# Payload Parsing
# ---------------------------------------------------------------------------
def parse_zenoh_payload(payload_str: str) -> Tuple[float, str]:
    """Parse payload string into value and timestamp."""
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

# ---------------------------------------------------------------------------
# Dashboard factory
# ---------------------------------------------------------------------------
def create_dashboard(zenoh_client: ZenohClient, iotdb_client: IoTDBClient) -> pn.layout.Column:
    """Create the Panel dashboard layout.

    Called once per browser session by the Panel/FastAPI integration.
    """
    buffer_size = 100
    zenoh_points: collections.deque = collections.deque(maxlen=buffer_size)
    
    state = {
        "last_zenoh_val": None,
        "last_zenoh_timestamp": "N/A",
        "last_iotdb_refresh": "N/A",
        "last_iotdb_error": "",
        "subscribed": False,
    }

    # ECharts Panes
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

    # Status indicators
    zenoh_status_pane = pn.pane.Markdown("### Zenoh Status\n🔴 Disconnected")
    iotdb_status_pane = pn.pane.Markdown("### IoTDB Status\n🔴 Disconnected")

    # Subscriber callback
    def on_zenoh_message(sample: Any) -> None:
        payload_str = decode_payload(sample)
        if payload_str is None:
            return
        try:
            val, ts_display = parse_zenoh_payload(payload_str)
            state["last_zenoh_val"] = val
            state["last_zenoh_timestamp"] = ts_display
            zenoh_points.append((ts_display, val))
        except Exception as exc:
            logger.error("Error parsing Zenoh message in dashboard callback: %s", exc)

    # Start Zenoh Subscription helper
    def try_subscribe():
        if zenoh_client.is_connected() and not state["subscribed"]:
            sub = zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, on_zenoh_message)
            if sub is not None:
                state["subscribed"] = True
                logger.info("Successfully subscribed to Zenoh: %s", config.ZENOH_KEY_EXPRESSION)

    # UI updates callbacks
    def refresh_zenoh_ui() -> None:
        z_ok = zenoh_client.is_connected()
        
        if z_ok:
            if not state["subscribed"]:
                try_subscribe()
            
            val_str = f"{state['last_zenoh_val']} °C" if state['last_zenoh_val'] is not None else "N/A"
            zenoh_status_pane.object = f"""### Zenoh Status
🟢 Connected
* **Last Message**: {val_str}
* **Time Received**: {state['last_zenoh_timestamp']}
* **Key Expression**: `{config.ZENOH_KEY_EXPRESSION}`"""
        else:
            state["subscribed"] = False
            zenoh_status_pane.object = f"""### Zenoh Status
🔴 Disconnected
* **Endpoint**: `{config.ZENOH_ENDPOINT}`
* Waiting for reconnect from lifespan..."""

        # Update chart
        if zenoh_points:
            times = [pt[0] for pt in zenoh_points]
            values = [pt[1] for pt in zenoh_points]
            zenoh_chart_pane.data["xAxis"]["data"] = times
            zenoh_chart_pane.data["series"][0]["data"] = values
            zenoh_chart_pane.param.trigger("data")

    def refresh_iotdb_ui() -> None:
        i_ok = iotdb_client.is_connected()
        
        if not i_ok:
            iotdb_status_pane.object = f"""### IoTDB Status
🔴 Disconnected
* **Host**: `{config.IOTDB_HOST}:{config.IOTDB_PORT}`
* Waiting for reconnect from lifespan..."""
            return

        # Query recent values
        try:
            records = iotdb_client.query_temperature(limit=buffer_size)
            state["last_iotdb_refresh"] = datetime.now().strftime("%H:%M:%S")
            state["last_iotdb_error"] = ""
            
            if records:
                iotdb_status_pane.object = f"""### IoTDB Status
🟢 Connected
* **Latest Value**: {records[0].get('temperature')} °C
* **Last Query**: {state['last_iotdb_refresh']}
* **Timeseries Path**: `{config.IOTDB_DEVICE}.{config.IOTDB_MEASUREMENT}`"""
                
                # Update ECharts UI
                times = []
                values = []
                for pt in reversed(records):
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
                
                iotdb_chart_pane.data["xAxis"]["data"] = times
                iotdb_chart_pane.data["series"][0]["data"] = values
                iotdb_chart_pane.param.trigger("data")
            else:
                iotdb_status_pane.object = f"""### IoTDB Status
🟢 Connected (No Data)
* **Last Query Attempt**: {state['last_iotdb_refresh']}
* **Timeseries Path**: `{config.IOTDB_DEVICE}.{config.IOTDB_MEASUREMENT}`"""
        except Exception as exc:
            state["last_iotdb_error"] = str(exc)
            iotdb_status_pane.object = f"""### IoTDB Status
⚠️ Connected (Query Error: {exc})
* **Last Query Attempt**: {state['last_iotdb_refresh']}"""

    # Initial subscription attempt
    try_subscribe()

    # Periodic UI update registration
    pn.state.add_periodic_callback(refresh_zenoh_ui, 1000)
    pn.state.add_periodic_callback(refresh_iotdb_ui, 2000)

    # Sidebar elements
    logo_path = "/app/app/asf-estd-1999-logo.jpg"
    pn.pane.JPG(logo_path, sizing_mode="scale_width", embed=True).servable(area="sidebar")
    pn.pane.Markdown(
        f"""# System Settings
* **Zenoh Key**: `{config.ZENOH_KEY_EXPRESSION}`
* **Zenoh Endpoint**: `{config.ZENOH_ENDPOINT}`
* **IoTDB Host**: `{config.IOTDB_HOST}:{config.IOTDB_PORT}`
* **IoTDB Device**: `{config.IOTDB_DEVICE}`
"""
    ).servable(area="sidebar")

    # Main dashboard assembly
    description = pn.pane.Markdown(
        "This interactive dashboard visualizes telemetry data streams from two independent live sources: "
        "real-time data direct from Eclipse Zenoh, and persisted historical records from Apache IoTDB."
    )

    status_row = pn.Row(
        pn.Card(zenoh_status_pane, title="Zenoh Connection", margin=5, sizing_mode="stretch_width"),
        pn.Card(iotdb_status_pane, title="Apache IoTDB Connection", margin=5, sizing_mode="stretch_width"),
        sizing_mode="stretch_width",
    )

    chart_row = pn.Row(
        pn.Card(zenoh_chart_pane, title="Live Zenoh Stream", margin=5, sizing_mode="stretch_width"),
        pn.Card(iotdb_chart_pane, title="Live IoTDB Time Series", margin=5, sizing_mode="stretch_width"),
        sizing_mode="stretch_width",
    )

    return pn.Column(
        description,
        status_row,
        chart_row,
        sizing_mode="stretch_width",
    )
