#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Panel dashboard script for ApacheCon 2022 IoT Demo.

This script provides a web-based dashboard for visualizing IoT data
from Zenoh and Apache IoTDB.
"""

import os
import sys
import logging
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import panel as pn
from src.zenoh_client import ZenohClient
from src.iotdb_client import IoTDBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize clients
zenoh_client = ZenohClient()
iotdb_client = IoTDBClient()

# Configuration from environment variables
ZENOH_PEER = os.getenv("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
IOTDB_HOST = os.getenv("IOTDB_HOST", "127.0.0.1")
IOTDB_PORT = os.getenv("IOTDB_PORT", "6667")
IOTDB_USERNAME = os.getenv("IOTDB_USERNAME", "root")
IOTDB_PASSWORD = os.getenv("IOTDB_PASSWORD", "root")

# Panel configuration
pn.extension('echarts', sizing_mode="stretch_width", template="fast", theme="dark")
ACCENT = "orange"
pn.state.template.param.update(
    site="Apache Con",
    title="Introduction to data apps with Panel",
    sidebar_width=200,
    accent_base_color=ACCENT,
    header_background=ACCENT,
    font="Montserrat"
)

# Initialize clients
def init_clients():
    """Initialize Zenoh and IoTDB clients."""
    try:
        # Connect to Zenoh
        if not zenoh_client.is_connected():
            zenoh_client.connect(peer=ZENOH_PEER)
            logger.info(f"Connected to Zenoh at {ZENOH_PEER}")
        
        # Connect to IoTDB
        if not iotdb_client.is_connected():
            iotdb_client.connect(
                host=IOTDB_HOST,
                port=IOTDB_PORT,
                username=IOTDB_USERNAME,
                password=IOTDB_PASSWORD
            )
            iotdb_client.initialize_schema()
            logger.info(f"Connected to IoTDB at {IOTDB_HOST}:{IOTDB_PORT}")
        
    except Exception as e:
        logger.error(f"Error initializing clients: {e}")


# Retrieve data from Zenoh and save to IoTDB
def retrieve():
    """Retrieve temperature data from Zenoh and store in IoTDB."""
    try:
        results = zenoh_client.get('/myfactory/machine1/temp')
        if results is None:
            logger.warning("No data received from Zenoh")
            return None, None, None
        
        temperature = float(results)
        timestamp = datetime.utcnow().isoformat()
        
        # Insert into IoTDB
        iotdb_client.insert_temperature(timestamp, temperature)
        
        # Query latest data
        query_results = iotdb_client.query_temperature(limit=10)
        
        if query_results:
            values = [r['temperature'] for r in query_results]
            timevalues = [r['timestamp'] for r in query_results]
            return temperature, values, timevalues
        else:
            return temperature, [], []
            
    except Exception as e:
        logger.error(f"Error in retrieve: {e}")
        return None, None, None


# Initialize clients on startup
init_clients()

# Get initial data
temperature = 0
values = []
timevalues = []

retrieved_data = retrieve()
if retrieved_data[0] is not None:
    temperature, values, timevalues = retrieved_data

# Invisible widgets for callbacks
slider = pn.widgets.FloatSlider(visible=False)
literal_input = pn.widgets.LiteralInput(
    name='Literal Input (dict)',
    value={'key': [1, 2, 3]},
    type=dict,
    visible=False
)

# Stream function
def stream():
    """Stream data from Zenoh to update dashboard."""
    try:
        retrieved_data = retrieve()
        if retrieved_data[0] is not None:
            s_temperature, s_values, s_timevalues = retrieved_data
            
            # Update literal input with new data
            if s_values and s_timevalues:
                literal_dict = {str(l): v for l, v in zip(s_timevalues, s_values)}
                literal_input.value = literal_dict
            
            # Update slider
            slider.value = s_temperature
    except Exception as e:
        logger.error(f"Error in stream: {e}")


# Gauge configuration
GAUGE_DATA = {
    'tooltip': {
        'formatter': '{a} <br/>{b} : {c}\u00b0C'
    },
    'series': [
        {
            'name': 'Gauge',
            'type': 'gauge',
            'detail': {'formatter': '{value}\u00b0C'},
            'data': [{'value': [temperature], 'name': 'Temperature'}]
        }
    ]
}

# Add periodic callback
pn.state.add_periodic_callback(stream, 250)

# Create gauge panel
gauge_pane = pn.pane.ECharts(GAUGE_DATA, width=400, height=400)
row = pn.Row(gauge_pane, slider).servable()

# JavaScript callback for slider
slider.jscallback(args={'gauge': gauge_pane}, value="""
    console.log('slider:', cb_obj.value, 'gauge value:', gauge.data.series[0].data[0].value);
    gauge.data.series[0].data[0].value = cb_obj.value;
    gauge.properties.data.change.emit()
"""
)

# Line chart configuration
ECHART_DATA = {
    'title': {
        'text': 'Temperature over Time'
    },
    'tooltip': {},
    'legend': {
        'data': ['Temperature over time']
    },
    'xAxis': {
        'data': timevalues if timevalues else []
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': values if values else []
    }],
}

ECHART_DATA['series'] = [dict(ECHART_DATA['series'][0], type='line')]
responsive_spec = dict(ECHART_DATA, responsive=True)
echart_pane = pn.pane.ECharts(responsive_spec, theme="dark", height=400)
row = pn.Row(echart_pane, literal_input).servable()

# JavaScript callback for literal input
literal_input.jscallback(args={'echart': echart_pane}, value="""
    console.log(cb_obj.value)
    let literal_dict = JSON.parse(cb_obj.value.replaceAll(\"'\",'\\\"') )
    console.log(literal_dict)

    let keys = Object.keys(literal_dict);
    let values = Object.entries(literal_dict);

    console.log(typeof(literal_dict), literal_dict, 'keys:', keys, 'values:', values,
            'echart xAxis:', echart.data.xAxis.data,
            'echart series:', echart.data.series[0].data);

    echart.data.xAxis.data = [...echart.data.xAxis.data, ...keys].slice(-1000);
    echart.data.series[0].data = [...echart.data.series[0].data, ...values].slice(-1000);

    echart.properties.data.change.emit()
"""
)

# Side panel with logo and settings
pn.pane.JPG(
    "https://apache.org/img/asf-estd-1999-logo.jpg",
    sizing_mode="scale_width",
    embed=False
).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")
