# -*- coding: utf-8 -*-
"""Dashboard layout and plotting components using Panel + Apache ECharts."""

import collections
import json
import logging
from datetime import datetime

import panel as pn

from app import config
from app.zenoh_client import decode_payload

logger = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# Panel global configuration (called once per process)
# ---------------------------------------------------------------------------
pn.extension("echarts", sizing_mode="stretch_width", template="fast", theme="dark")
ACCENT = "orange"
pn.state.template.param.update(
    site="Apache Con 2022",
    title="IoT Stream Analysis Dashboard",
    sidebar_width=250,
    accent_base_color=ACCENT,
    header_background=ACCENT,
    font="Montserrat",
)


# ---------------------------------------------------------------------------
# Dashboard factory
# ---------------------------------------------------------------------------


def create_dashboard(zenoh_client, iotdb_client) -> pn.layout.Column:
    """Create the Panel dashboard layout.

    Called once per browser session by the Panel/FastAPI integration.

    Args:
        zenoh_client: Connected :class:`~app.zenoh_client.ZenohClient` instance.
        iotdb_client: Connected :class:`~app.iotdb_client.IoTDBClient` instance.

    Returns:
        The main Panel layout component.
    """
    # -----------------------------------------------------------------------
    # State shared between the Zenoh callback thread and Panel callbacks
    # -----------------------------------------------------------------------
    zenoh_history: collections.deque = collections.deque(maxlen=30)
    # Use a mutable container so the nested functions can mutate the value
    state = {"current_temp": 0.0, "last_update": "Never"}

    # -----------------------------------------------------------------------
    # ECharts – Gauge
    # -----------------------------------------------------------------------
    gauge_config = {
        "tooltip": {"formatter": "{a} <br/>{b} : {c}°C"},
        "series": [
            {
                "name": "Current Temperature",
                "type": "gauge",
                "min": 0,
                "max": 50,
                "detail": {"formatter": "{value}°C"},
                "data": [{"value": 0.0, "name": "Temp"}],
            }
        ],
    }

    # -----------------------------------------------------------------------
    # ECharts – Zenoh real-time line chart
    # -----------------------------------------------------------------------
    zenoh_chart_config = {
        "title": {"text": "Zenoh Live Stream (Real-Time)"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value", "scale": True},
        "series": [
            {
                "name": "Temperature",
                "type": "line",
                "data": [],
                "smooth": True,
                "itemStyle": {"color": "#ff9800"},
            }
        ],
    }

    # -----------------------------------------------------------------------
    # ECharts – IoTDB historical bar chart
    # -----------------------------------------------------------------------
    iotdb_chart_config = {
        "title": {"text": "Apache IoTDB Historical (Periodic Query)"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value", "scale": True},
        "series": [
            {
                "name": "Temperature",
                "type": "bar",
                "data": [],
                "itemStyle": {"color": "#2196f3"},
            }
        ],
    }

    # -----------------------------------------------------------------------
    # Panel panes
    # -----------------------------------------------------------------------
    gauge_pane = pn.pane.ECharts(gauge_config, width=300, height=300)
    zenoh_chart_pane = pn.pane.ECharts(zenoh_chart_config, height=350)
    iotdb_chart_pane = pn.pane.ECharts(iotdb_chart_config, height=350)
    status_pane = pn.pane.Markdown("### Initialising …")

    # -----------------------------------------------------------------------
    # Zenoh subscriber callback  (runs in a Zenoh background thread)
    # -----------------------------------------------------------------------
    def on_zenoh_message(sample) -> None:
        """Parse incoming Zenoh JSON payload and buffer it for the UI."""
        payload_str = decode_payload(sample)
        if payload_str is None:
            return
        try:
            data = json.loads(payload_str)
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

            state["current_temp"] = val
            state["last_update"] = ts_display
            zenoh_history.append((ts_display, val))
        except Exception as exc:
            logger.error("Error parsing Zenoh message in dashboard: %s", exc)

    # Register the persistent subscriber if the client is up
    if zenoh_client.is_connected():
        logger.info(
            "Registering dashboard Zenoh subscriber on %s", config.ZENOH_KEY_EXPRESSION
        )
        zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, on_zenoh_message)
    else:
        logger.warning("Zenoh not connected – live chart will be empty until reconnected")

    # -----------------------------------------------------------------------
    # Periodic UI refresh callbacks  (run in Panel's ioloop)
    # -----------------------------------------------------------------------

    def _refresh_zenoh_ui() -> None:
        gauge_pane.data["series"][0]["data"][0]["value"] = round(state["current_temp"], 2)
        gauge_pane.param.trigger("data")

        times = [item[0] for item in zenoh_history]
        temps = [item[1] for item in zenoh_history]
        zenoh_chart_pane.data["xAxis"]["data"] = times
        zenoh_chart_pane.data["series"][0]["data"] = temps
        zenoh_chart_pane.param.trigger("data")

    def _refresh_iotdb_ui() -> None:
        if not iotdb_client.is_connected():
            return
        try:
            records = iotdb_client.query_temperature(limit=20)
            records.reverse()  # chronological left-to-right

            times = []
            temps = []
            for rec in records:
                ts_raw = rec.get("timestamp", "")
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
                temps.append(rec.get("temperature", 0.0))

            iotdb_chart_pane.data["xAxis"]["data"] = times
            iotdb_chart_pane.data["series"][0]["data"] = temps
            iotdb_chart_pane.param.trigger("data")
        except Exception as exc:
            logger.error("Error refreshing IoTDB chart: %s", exc)

    def _refresh_status() -> None:
        z_ok = zenoh_client.is_connected()
        i_ok = iotdb_client.is_connected()
        status_pane.object = f"""
### Connection Status
* **Zenoh Broker**: {"🟢 Connected" if z_ok else "🔴 Disconnected"}
* **Apache IoTDB**: {"🟢 Connected" if i_ok else "🔴 Disconnected"}

### Telemetry Metadata
* **Last Value**: {state["current_temp"]}°C
* **Last Update**: {state["last_update"]}
* **Key Expression**: `{config.ZENOH_KEY_EXPRESSION}`
"""

    pn.state.add_periodic_callback(_refresh_zenoh_ui, 500)
    pn.state.add_periodic_callback(_refresh_iotdb_ui, 2000)
    pn.state.add_periodic_callback(_refresh_status, 1000)

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------
    logo_path = "/app/app/asf-estd-1999-logo.jpg"
    pn.pane.JPG(logo_path, sizing_mode="scale_width", embed=True).servable(area="sidebar")
    status_pane.servable(area="sidebar")

    # -----------------------------------------------------------------------
    # Main layout
    # -----------------------------------------------------------------------
    return pn.Column(
        pn.Row(
            pn.Card(gauge_pane, title="Current Reading", margin=10, width=320),
            pn.Card(
                zenoh_chart_pane,
                title="Real-Time Data (Zenoh)",
                margin=10,
                sizing_mode="stretch_width",
            ),
        ),
        pn.Row(
            pn.Card(
                iotdb_chart_pane,
                title="Historical Data (IoTDB)",
                margin=10,
                sizing_mode="stretch_width",
            )
        ),
    )
