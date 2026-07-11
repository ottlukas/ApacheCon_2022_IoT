# -*- coding: utf-8 -*-
"""Dashboard layout and plotting components using Panel + Apache ECharts."""

import collections
import functools
import html
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import panel as pn

from app import config
from app import simulator_controller
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
    """Create an ECharts configuration dictionary for a line chart.

    Args:
        title: Chart title shown at the top.
        x_data: Category (x-axis) labels.
        y_data: Numeric (y-axis) values.
        series_name: Name of the data series.
        color: Series line colour (hex string).

    Returns:
        ECharts option dictionary consumable by ``pn.pane.ECharts``.
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
# Payload parsing helpers
# ---------------------------------------------------------------------------
def parse_zenoh_payload(payload_str: str) -> Tuple[float, str]:
    """Parse a Zenoh payload string into a (value, display_timestamp) tuple.

    Args:
        payload_str: Raw payload received from Zenoh (JSON or plain float).

    Returns:
        Tuple of the numeric value and a HH:MM:SS formatted timestamp.

    Raises:
        ValueError: If the payload cannot be interpreted as a number.
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
                except (ValueError, TypeError):
                    ts_display = ts_raw
            else:
                ts_display = datetime.now().strftime("%H:%M:%S")
            return val, ts_display
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback to parsing a raw float value
    val = float(payload_str)
    ts_display = datetime.now().strftime("%H:%M:%S")
    return val, ts_display


def _format_iotdb_timestamp(ts_raw: str) -> str:
    """Convert an IoTDB timestamp into a HH:MM:SS display string.

    Args:
        ts_raw: Numeric (epoch milliseconds) or ISO-8601 timestamp string.

    Returns:
        Formatted time, or the raw value if it cannot be parsed.
    """
    if not ts_raw:
        return ""
    try:
        if str(ts_raw).isdigit():
            dt = datetime.fromtimestamp(int(ts_raw) / 1000.0)
        else:
            dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError, OSError):
        return str(ts_raw)


# ---------------------------------------------------------------------------
# Live chart update helpers
# ---------------------------------------------------------------------------
def _update_zenoh_chart(points: "collections.deque", chart_pane: Any) -> None:
    """Push the most recent Zenoh samples onto the live ECharts pane."""
    if not points:
        return
    times = [pt[0] for pt in points]
    values = [pt[1] for pt in points]
    # ECharts panes expose the option dict via `object` (not `data`).
    chart_pane.object["xAxis"]["data"] = times
    chart_pane.object["series"][0]["data"] = values
    chart_pane.param.trigger("object")


def _update_iotdb_chart(records: List[Dict[str, Any]], chart_pane: Any) -> None:
    """Push historical IoTDB records onto the live ECharts pane."""
    if not records:
        return
    times = [_format_iotdb_timestamp(pt.get("timestamp", "")) for pt in records]
    values = [float(pt.get("temperature", 0.0)) for pt in records]
    chart_pane.object["xAxis"]["data"] = times
    chart_pane.object["series"][0]["data"] = values
    chart_pane.param.trigger("object")


# ---------------------------------------------------------------------------
# Zenoh / IoTDB subscription + refresh callbacks (module level so they do
# not count against create_dashboard's local-variable/statement budget)
# ---------------------------------------------------------------------------
def _handle_zenoh_message(
    sample: Any,
    state: Dict[str, Any],
    zenoh_points: "collections.deque",
) -> None:
    """Callback invoked for each incoming Zenoh sample."""
    payload_str = decode_payload(sample)
    if payload_str is None:
        return
    try:
        val, ts_display = parse_zenoh_payload(payload_str)
        state["last_zenoh_val"] = val
        state["last_zenoh_timestamp"] = ts_display
        zenoh_points.append((ts_display, val))
    except (ValueError, TypeError) as exc:
        logger.error("Error parsing Zenoh message: %s", exc)


def _establish_subscription(
    zenoh_client: ZenohClient,
    state: Dict[str, Any],
    callback: Any,
) -> None:
    """Subscribe to the Zenoh key expression if not already subscribed."""
    if zenoh_client.is_connected() and not state["subscribed"]:
        sub = zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, callback)
        if sub is not None:
            state["subscribed"] = True
            logger.info("Subscribed to Zenoh: %s", config.ZENOH_KEY_EXPRESSION)


def _refresh_zenoh_ui(
    state: Dict[str, Any],
    zenoh_client: ZenohClient,
    zenoh_points: "collections.deque",
    zenoh_chart_pane: Any,
    zenoh_status_pane: Any,
) -> None:
    """Update the Zenoh connection status text and live chart."""
    z_ok = zenoh_client.is_connected()
    if not z_ok:
        state["subscribed"] = False
        zenoh_status_pane.object = (
            "### Zenoh Status\n🔴 Disconnected\n"
            f"* **Endpoint**: `{config.ZENOH_ENDPOINT}`\n"
            "Waiting for reconnect from lifespan..."
        )
        return

    if not state["subscribed"]:
        _establish_subscription(zenoh_client, state, state["on_zenoh_message"])

    val_str = f"{state['last_zenoh_val']} °C" if state["last_zenoh_val"] is not None else "N/A"
    zenoh_status_pane.object = (
        "### Zenoh Status\n🟢 Connected\n"
        f"* **Last Message**: {val_str}\n"
        f"* **Time Received**: {state['last_zenoh_timestamp']}\n"
        f"* **Key Expression**: `{config.ZENOH_KEY_EXPRESSION}`"
    )
    _update_zenoh_chart(zenoh_points, zenoh_chart_pane)


def _refresh_iotdb_ui(
    state: Dict[str, Any],
    iotdb_client: "IoTDBClient",
    iotdb_chart_pane: Any,
    iotdb_status_pane: Any,
    buffer_size: int,
) -> None:
    """Update the IoTDB connection status text and historical chart."""
    i_ok = iotdb_client.is_connected()
    if not i_ok:
        iotdb_status_pane.object = (
            "### IoTDB Status\n🔴 Disconnected\n"
            f"* **Host**: `{config.IOTDB_HOST}:{config.IOTDB_PORT}`\n"
            "Waiting for reconnect from lifespan..."
        )
        return

    try:
        records = iotdb_client.query_temperature(limit=buffer_size)
        state["last_iotdb_refresh"] = datetime.now().strftime("%H:%M:%S")
        state["last_iotdb_error"] = ""

        if not records:
            iotdb_status_pane.object = (
                "### IoTDB Status\n🟢 Connected (No Data)\n"
                f"* **Last Query Attempt**: {state['last_iotdb_refresh']}\n"
                f"* **Timeseries Path**: "
                f"`{config.IOTDB_DEVICE}.{config.IOTDB_MEASUREMENT}`"
            )
            return

        iotdb_status_pane.object = (
            "### IoTDB Status\n🟢 Connected\n"
            f"* **Latest Value**: {records[0].get('temperature')} °C\n"
            f"* **Last Query**: {state['last_iotdb_refresh']}\n"
            f"* **Timeseries Path**: "
            f"`{config.IOTDB_DEVICE}.{config.IOTDB_MEASUREMENT}`"
        )
        _update_iotdb_chart(records, iotdb_chart_pane)
    except (ValueError, TypeError, OSError) as exc:
        # query_temperature() swallows its own IoTDB errors and returns [],
        # so only data-shaping / timestamp errors can escape here.
        state["last_iotdb_error"] = str(exc)
        iotdb_status_pane.object = (
            "### IoTDB Status\n⚠️ Connected (Query Error: "
            f"{exc})\n* **Last Query Attempt**: {state['last_iotdb_refresh']}"
        )


def _refresh_simulator_ui(
    simulator_status_pane: Any,
    simulator_log_pane: Any,
) -> None:
    """Refresh the simulator status + log panel from the controller.

    Reads the rolling log buffer and current running state via
    ``app.simulator_controller`` (the same in-process controller the FastAPI
    routes use) and re-renders the Markdown panes. Called on a periodic
    callback so the dashboard mirrors the subprocess's live output.
    """
    info = simulator_controller.get_log(tail=200)
    running = bool(info.get("running"))

    badge = "🟢 Running" if running else "🔴 Stopped"
    detail = html.escape(str(info.get("detail", "")))
    status_md = (
        "### Sensor Simulator\n"
        f"{badge}\n"
        f"* **State**: `{html.escape(str(info.get('status', 'stopped')))}`\n"
        f"* **Detail**: {detail}\n"
    )
    simulator_status_pane.object = status_md

    lines = info.get("lines", [])
    if lines:
        log_md = "```text\n" + "\n".join(lines[-200:]) + "\n```"
    else:
        log_md = (
            "```text\n"
            "(no output yet – press ▶ Start Simulator to begin publishing)\n"
            "```"
        )
    simulator_log_pane.object = log_md


# ---------------------------------------------------------------------------
# Dashboard factory
# ---------------------------------------------------------------------------
def create_dashboard(zenoh_client: ZenohClient, iotdb_client: IoTDBClient) -> pn.layout.Column:
    """Create the Panel dashboard layout.

    Called once per browser session by the Panel/FastAPI integration.

    Args:
        zenoh_client: Connected (or reconnecting) Zenoh client.
        iotdb_client: Connected (or reconnecting) IoTDB client.

    Returns:
        The assembled Panel layout column.
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

    # Subscriber callback (bound to this dashboard's buffers); stored on the
    # shared state dict so _refresh_zenoh_ui needs one fewer argument.
    def on_zenoh_message(sample: Any) -> None:
        _handle_zenoh_message(sample, state, zenoh_points)

    state["on_zenoh_message"] = on_zenoh_message

    def try_subscribe() -> None:
        _establish_subscription(zenoh_client, state, on_zenoh_message)

    # Initial subscription attempt
    try_subscribe()

    # Periodic UI update registration
    pn.state.add_periodic_callback(
        functools.partial(
            _refresh_zenoh_ui,
            state,
            zenoh_client,
            zenoh_points,
            zenoh_chart_pane,
            zenoh_status_pane,
        ),
        1000,
    )
    pn.state.add_periodic_callback(
        functools.partial(
            _refresh_iotdb_ui,
            state,
            iotdb_client,
            iotdb_chart_pane,
            iotdb_status_pane,
            buffer_size,
        ),
        2000,
    )

    # Sidebar elements
    # NOTE: The logo path must be resolved relative to the package, never a
    # hard-coded absolute path (e.g. "/app/app/asf-estd-1999-logo.jpg").
    # pn.pane.JPG(..., embed=True) fetches the source through `requests.get`,
    # so a bare/non-existent absolute path raises requests.exceptions.MissingSchema.
    # That exception propagates up through template.server_doc and aborts the
    # *entire* dashboard render -- the ECharts panes never appear.
    # We therefore resolve the file robustly and only embed it when it exists.
    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "app", "asf-estd-1999-logo.jpg"
    )
    if os.path.exists(logo_path):
        pn.pane.JPG(logo_path, sizing_mode="scale_width", embed=True).servable(area="sidebar")
    pn.pane.Markdown(f"""# System Settings
* **Zenoh Key**: `{config.ZENOH_KEY_EXPRESSION}`
* **Zenoh Endpoint**: `{config.ZENOH_ENDPOINT}`
* **IoTDB Host**: `{config.IOTDB_HOST}:{config.IOTDB_PORT}`
* **IoTDB Device**: `{config.IOTDB_DEVICE}`
""").servable(area="sidebar")

    # ---------------------------------------------------------------------------
    # Sensor Simulator control section
    #
    # The dashboard container runs the simulator as an in-process-controlled
    # subprocess (see app.simulator_controller). These buttons + the log panel
    # give the operator start/stop control and a live, scrollable view of the
    # simulator's stdout (status, published readings, any errors).
    # ---------------------------------------------------------------------------
    simulator_status_pane = pn.pane.Markdown("### Sensor Simulator\n🔴 Stopped")
    simulator_log_pane = pn.pane.Markdown(
        "```text\n(no output yet – press ▶ Start Simulator to begin publishing)\n```"
    )

    def _start_cb(event: Any) -> None:
        """Panel button callback: start the simulator via the controller."""
        simulator_controller.start_simulator()
        _refresh_simulator_ui(simulator_status_pane, simulator_log_pane)

    def _stop_cb(event: Any) -> None:
        """Panel button callback: stop the simulator via the controller."""
        simulator_controller.stop_simulator()
        _refresh_simulator_ui(simulator_status_pane, simulator_log_pane)

    start_btn = pn.widgets.Button(
        name="▶ Start Simulator", button_type="success", width=160
    )
    stop_btn = pn.widgets.Button(
        name="■ Stop Simulator", button_type="danger", width=160
    )
    start_btn.on_click(_start_cb)
    stop_btn.on_click(_stop_cb)

    simulator_card = pn.Card(
        pn.Column(
            pn.Row(start_btn, stop_btn, sizing_mode="stretch_width"),
            simulator_status_pane,
            pn.layout.Divider(),
            pn.pane.Markdown("**Live Simulator Log**"),
            simulator_log_pane,
            sizing_mode="stretch_width",
        ),
        title="Sensor Simulator Control",
        margin=5,
        sizing_mode="stretch_width",
        collapsible=True,
    )

    # Keep the simulator panel in sync even when the user hasn't clicked.
    pn.state.add_periodic_callback(
        functools.partial(
            _refresh_simulator_ui,
            simulator_status_pane,
            simulator_log_pane,
        ),
        2000,
    )

    # Main dashboard assembly
    description = pn.pane.Markdown(
        "This interactive dashboard visualizes telemetry data streams from two "
        "independent live sources: real-time data direct from Eclipse Zenoh, and "
        "persisted historical records from Apache IoTDB."
    )

    status_row = pn.Row(
        pn.Card(
            zenoh_status_pane,
            title="Zenoh Connection",
            margin=5,
            sizing_mode="stretch_width",
        ),
        pn.Card(
            iotdb_status_pane,
            title="Apache IoTDB Connection",
            margin=5,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )

    chart_row = pn.Row(
        pn.Card(
            zenoh_chart_pane,
            title="Live Zenoh Stream",
            margin=5,
            sizing_mode="stretch_width",
        ),
        pn.Card(
            iotdb_chart_pane,
            title="Live IoTDB Time Series",
            margin=5,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )

    return pn.Column(
        description,
        status_row,
        chart_row,
        simulator_card,
        sizing_mode="stretch_width",
    )
