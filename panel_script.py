#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# TODO: Add module docstring
@author: luk
"""
import json
from datetime import datetime

import panel as pn
import zenoh
from iotdb.Session import Session as IoTDBLibSession # Renamed to avoid conflict


#Settings
#Zenoh
CONF = zenoh.Config()
# Set mode to client
CONF.insert_json5("mode", json.dumps("client"))
# Corrected configuration key for connect endpoints
CONF.insert_json5("connect/endpoints", json.dumps(["tcp/127.0.0.1:7447"]))
# It's better to manage the session lifecycle, e.g. with `with zenoh.open(conf) as session: ...`
# or by explicitly closing it on app shutdown. For now, opening globally.
# A Panel 'on_unload' callback would be a good place for session.close().
ZENOH_SESSION = zenoh.open(CONF)

# IoTDB
IP = "127.0.0.1"
PORT = "6667"
USERNAME = "root"
PASSWORD = "root"
# Panel
pn.extension('echarts',sizing_mode="stretch_width",template="fast", theme="dark")
ACCENT_COLOR = "orange"
# pylint: disable=line-too-long
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel",
                               sidebar_width=200, accent_base_color=ACCENT_COLOR,
                               header_background=ACCENT_COLOR, font="Montserrat")
# pylint: enable=line-too-long

# Zenoh retrieve values and save values to IoTDB
def retrieve_data():
    """Retrieves temperature data from Zenoh and stores it in IoTDB."""
    # Assuming ZENOH_SESSION is the globally opened Zenoh session
    results = ZENOH_SESSION.get('/myfactory/machine1/temp')

    if not results:
        print("No data received from Zenoh in retrieve()")
        # Return some default or cached values if appropriate, or raise an error
        # For now, returning None to indicate failure, caller must handle this.
        return None, None, None

    first_result = results[0] # Assuming get returns a list of Sample objects

    # Adapting from Zenoh 0.x to 1.x Sample API
    # Original: temperature = results[0].value.get_content()
    # Original: datetime_iso = datetime.fromtimestamp(results[0].timestamp.time).isoformat()
    # Assuming payload is string representation of the temperature value
    try:
        temperature_str = first_result.payload.decode()
        temperature_val = float(temperature_str) # Or int() if it's always an integer
    except (UnicodeDecodeError, ValueError) as e:
        print(f"Error decoding Zenoh payload: {e}")
        return None, None, None # Indicate failure

    datetime_iso = datetime.fromtimestamp(first_result.timestamp.time.timestamp()).isoformat()

    iotdb_s = IoTDBLibSession(IP, PORT, USERNAME, PASSWORD) # IoTDB session
    iotdb_s.open(False)
    # Using temperature_str for SQL to match original str(results[0].value.get_content())
    # pylint: disable=line-too-long
    sql_query = f"INSERT INTO root.myfactory.machine1(timestamp,temperature) values('{datetime_iso}', {temperature_str})"
    # pylint: enable=line-too-long
    iotdb_s.execute_non_query_statement(sql_query)
    # pylint: disable=line-too-long
    result_set = iotdb_s.execute_query_statement("SELECT * FROM root.myfactory.machine1 ORDER BY TIME DESC limit 10")
    # pylint: enable=line-too-long
    # Transform to Pandas Dataset
    df_result = result_set.todf()
    iotdb_s.close()

    values_list = df_result['root.myfactory.machine1.temperature'].values.tolist()
    #TODO convert timevalues to datetime values
    timevalues_list = df_result.Time.values.tolist()
    return temperature_val, values_list, timevalues_list

# Gauge data
# Renaming to avoid W0621 in stream_live_data
INITIAL_TEMP = 0
INITIAL_VALUES_LIST = []
INITIAL_TIMEVALUES_LIST = []

# Renaming to avoid W0621 in stream_live_data
live_retrieved_data = retrieve_data()
if live_retrieved_data and live_retrieved_data[0] is not None:
    INITIAL_TEMP, INITIAL_VALUES_LIST, INITIAL_TIMEVALUES_LIST = live_retrieved_data
else:
    print("Failed to retrieve initial data for panel.")
    # Set some defaults if retrieve_data() fails, to prevent errors later
    # INITIAL_TEMP remains 0
    # INITIAL_VALUES_LIST and INITIAL_TIMEVALUES_LIST remain empty lists

# invisible slider and literal to jscallback
slider_widget = pn.widgets.FloatSlider(visible=False)
# pylint: disable=line-too-long
literal_input_widget = pn.widgets.LiteralInput(name='Literal Input (dict)',
        value={'key': [1, 2, 3]}, type=dict, visible=False)
# pylint: enable=line-too-long
# Stream function
def stream_live_data():
    """Streams live data to update dashboard components."""
    # Using different variable names from the global scope ones
    s_retrieved_data = retrieve_data()
    if s_retrieved_data and s_retrieved_data[0] is not None:
        s_temperature, s_values, s_timevalues = s_retrieved_data
        literal_dict = {str(l):v for l, v in zip(s_timevalues, s_values)}
        #print('in python', literal_dict)
        literal_input_widget.value = literal_dict
        slider_widget.value = s_temperature
        # this step triggers internally the js_callback attached to the slider / literal input
    else:
        print("Stream: Failed to retrieve data, skipping update.")

GAUGE_CONFIG = {
    'tooltip': {
        'formatter': '{a} <br/>{b} : {c}°C'
    },
    'series': [
        {
            'name': 'Gauge',
            'type': 'gauge',
            'detail': {'formatter': '{value}°C'},
            'data': [{'value': [INITIAL_TEMP], 'name': 'Temperature'}] # Use INITIAL_TEMP
        }
    ]
}

#callback
pn.state.add_periodic_callback(stream_live_data, 250)
# gauge panel + slider
gauge_pane_widget = pn.pane.ECharts(GAUGE_CONFIG,width=400, height=400)
row_widget = pn.Row(gauge_pane_widget,slider_widget).servable()
# js callback functions
# pylint: disable=line-too-long
slider_widget.jscallback(args={'gauge': gauge_pane_widget}, value="""
    console.log( 'dummy slider:', cb_obj.value,
            'gauge value',gauge.data.series[0].data[0].value);
    gauge.data.series[0].data[0].value = cb_obj.value;
    gauge.properties.data.change.emit()"""
    )
# pylint: enable=line-too-long
# Linechart
ECHART_CONFIG = {
    'title': {
        'text': 'Temperature over Time'
    },
    'tooltip': {},
    'legend': {
        'data':['Temperature over time']
    },
    'xAxis': {
        'data': INITIAL_TIMEVALUES_LIST # Use INITIAL_TIMEVALUES_LIST
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': INITIAL_VALUES_LIST # Use INITIAL_VALUES_LIST
    }],
}

ECHART_CONFIG['series'] = [dict(ECHART_CONFIG['series'][0], type= 'line')]
RESPONSIVE_ECHART_CONFIG = dict(ECHART_CONFIG, responsive=True)
echart_pane_widget = pn.pane.ECharts(RESPONSIVE_ECHART_CONFIG,theme="dark", height=400)
row_echart_widget = pn.Row(echart_pane_widget,literal_input_widget).servable()
# pylint: disable=line-too-long
literal_input_widget.jscallback(args={'echart': echart_pane_widget,}, value="""
    console.log(cb_obj.value)
    let literal_dict = JSON.parse( cb_obj.value.replaceAll("'",'"') )
    console.log(literal_dict)

    let keys = Object.keys(literal_dict);
    let values = Object.entries(literal_dict);

    console.log(typeof(literal_dict),literal_dict, 'dummy slider:', keys, values ,
            'echart value',echart.data.xAxis.data,
           echart.data.series[0].data );

    echart.data.xAxis.data = [...echart.data.xAxis.data, ...keys].slice(-1000);
    echart.data.series[0].data = [...echart.data.series[0].data, ...values].slice(-1000);

    echart.properties.data.change.emit()
"""
    )
# pylint: enable=line-too-long

# side panel with logo and "Settings"
# pylint: disable=line-too-long
pn.pane.JPG("asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
# pylint: enable=line-too-long
pn.panel("# Settings").servable(area="sidebar")
