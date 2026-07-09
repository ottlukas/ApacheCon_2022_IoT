# -*- coding: utf-8 -*-
"""Dashboard layout and plotting components using Panel."""

import collections
import json
import logging
from datetime import datetime
import panel as pn

from app import config

logger = logging.getLogger("dashboard")

# Set up Panel configuration
pn.extension('echarts', sizing_mode="stretch_width", template="fast", theme="dark")
ACCENT = "orange"
pn.state.template.param.update(
    site="Apache Con 2022",
    title="IoT Stream Analysis Dashboard",
    sidebar_width=250,
    accent_base_color=ACCENT,
    header_background=ACCENT,
    font="Montserrat"
)


def create_dashboard(zenoh_client, iotdb_client) -> pn.layout.Column:
    """Create the Panel dashboard layout.

    Args:
        zenoh_client: Connected ZenohClient instance
        iotdb_client: Connected IoTDBClient instance

    Returns:
        The main Panel layout component
    """
    # Deque to hold live Zenoh temperature data points
    zenoh_history = collections.deque(maxlen=30)
    current_temp = 0.0
    last_update_zenoh = "Never"

    # 1. Gauge configurations
    gauge_config = {
        'tooltip': {
            'formatter': '{a} <br/>{b} : {c}°C'
        },
        'series': [
            {
                'name': 'Current Temperature',
                'type': 'gauge',
                'min': 0,
                'max': 50,
                'detail': {'formatter': '{value}°C'},
                'data': [{'value': 0.0, 'name': 'Temp'}]
            }
        ]
    }

    # 2. Zenoh Chart config (Real-time Line Chart)
    zenoh_chart_config = {
        'title': {
            'text': 'Zenoh Live Stream (Real-Time)'
        },
        'tooltip': {'trigger': 'axis'},
        'xAxis': {
            'type': 'category',
            'data': []
        },
        'yAxis': {
            'type': 'value',
            'scale': True
        },
        'series': [{
            'name': 'Temperature',
            'type': 'line',
            'data': [],
            'smooth': True,
            'itemStyle': {'color': '#ff9800'}
        }]
    }

    # 3. IoTDB Chart config (Periodic Bar/Line Chart)
    iotdb_chart_config = {
        'title': {
            'text': 'Apache IoTDB Historical (Periodic Query)'
        },
        'tooltip': {'trigger': 'axis'},
        'xAxis': {
            'type': 'category',
            'data': []
        },
        'yAxis': {
            'type': 'value',
            'scale': True
        },
        'series': [{
            'name': 'Temperature',
            'type': 'bar',
            'data': [],
            'itemStyle': {'color': '#2196f3'}
        }]
    }

    # Wrap configs in Panel ECharts panes
    gauge_pane = pn.pane.ECharts(gauge_config, width=300, height=300)
    zenoh_chart_pane = pn.pane.ECharts(zenoh_chart_config, height=350)
    iotdb_chart_pane = pn.pane.ECharts(iotdb_chart_config, height=350)

    # Status & Metadata panel
    status_pane = pn.pane.Markdown("### Initializing...")

    # Zenoh callback (background thread)
    def on_zenoh_message(sample):
        nonlocal current_temp, last_update_zenoh
        if sample.payload is None:
            return
        try:
            payload_str = bytes(sample.payload).decode("utf-8")
            data = json.loads(payload_str)
            val = float(data.get("value", 0.0))
            ts_str = data.get("timestamp", "")
            
            if ts_str:
                # e.g., 2026-07-09T12:00:00.000Z -> 12:00:00
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    ts_display = dt.strftime("%H:%M:%S")
                except Exception:
                    ts_display = ts_str
            else:
                ts_display = datetime.now().strftime("%H:%M:%S")

            current_temp = val
            last_update_zenoh = ts_display
            zenoh_history.append((ts_display, val))
        except Exception as e:
            logger.error("Error parsing Zenoh message in dashboard: %s", e)

    # Register Zenoh subscription if connected
    if zenoh_client.is_connected():
        logger.info("Registering dashboard Zenoh subscription on %s", config.ZENOH_KEY_EXPRESSION)
        zenoh_client.get_subscriber(config.ZENOH_KEY_EXPRESSION, on_zenoh_message)

    # Periodic callback to refresh Zenoh UI elements (runs thread-safely via Panel event loop)
    def refresh_zenoh_ui():
        # Update Gauge
        gauge_pane.data['series'][0]['data'][0]['value'] = round(current_temp, 2)
        gauge_pane.param.trigger('data')

        # Update Zenoh History Line Chart
        times = [item[0] for item in zenoh_history]
        temps = [item[1] for item in zenoh_history]
        zenoh_chart_pane.data['xAxis']['data'] = times
        zenoh_chart_pane.data['series'][0]['data'] = temps
        zenoh_chart_pane.param.trigger('data')

    # Periodic callback to refresh IoTDB UI elements (runs thread-safely)
    def refresh_iotdb_ui():
        if not iotdb_client.is_connected():
            return
        try:
            records = iotdb_client.query_temperature(limit=20)
            # Reverse so it displays chronologically (left-to-right)
            records.reverse()

            times = []
            temps = []
            for r in records:
                ts_str = r.get("timestamp", "")
                if ts_str:
                    try:
                        if ts_str.isdigit():
                            dt = datetime.fromtimestamp(int(ts_str) / 1000.0)
                        else:
                            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        ts_display = dt.strftime("%H:%M:%S")
                    except Exception:
                        ts_display = ts_str
                else:
                    ts_display = ""
                times.append(ts_display)
                temps.append(r.get("temperature", 0.0))

            iotdb_chart_pane.data['xAxis']['data'] = times
            iotdb_chart_pane.data['series'][0]['data'] = temps
            iotdb_chart_pane.param.trigger('data')
        except Exception as e:
            logger.error("Error refreshing IoTDB chart: %s", e)

    def refresh_status():
        z_ok = zenoh_client.is_connected()
        i_ok = iotdb_client.is_connected()
        
        status_pane.object = f"""
        ### Connection Status
        * **Zenoh Broker**: {"🟢 Connected" if z_ok else "🔴 Disconnected"}
        * **Apache IoTDB**: {"🟢 Connected" if i_ok else "🔴 Disconnected"}
        
        ### Telemetry Metadata
        * **Last Value**: {current_temp}°C
        * **Last Update**: {last_update_zenoh}
        * **Subscription Path**: `{config.ZENOH_KEY_EXPRESSION}`
        """

    # Register periodic callbacks
    pn.state.add_periodic_callback(refresh_zenoh_ui, 500)
    pn.state.add_periodic_callback(refresh_iotdb_ui, 2000)
    pn.state.add_periodic_callback(refresh_status, 1000)

    # Sidebar layout
    logo_path = "/app/app/asf-estd-1999-logo.jpg"
    pn.pane.JPG(
        logo_path,
        sizing_mode="scale_width",
        embed=True
    ).servable(area="sidebar")
    
    status_pane.servable(area="sidebar")

    # Main dashboard grid layout
    main_layout = pn.Column(
        pn.Row(
            pn.Card(gauge_pane, title="Current Reading", margin=10, width=320),
            pn.Card(zenoh_chart_pane, title="Real-Time Data (Zenoh)", margin=10, sizing_mode="stretch_width"),
        ),
        pn.Row(
            pn.Card(iotdb_chart_pane, title="Historical Data (IoTDB)", margin=10, sizing_mode="stretch_width")
        )
    )

    return main_layout
