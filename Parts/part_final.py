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
from iotdb.Session import Session


#Settings
#Zenoh
config = zenoh.Config()
# Set mode to client
config.insert_json5("mode", json.dumps("client"))
# Set connect endpoints
config.insert_json5("connect/endpoints", json.dumps(["tcp/127.0.0.1:7447"]))
# Open session
session = zenoh.open(config)
workspace = session.workspace('/')

# IoTDB
IP = "127.0.0.1"
PORT = "6667"
USERNAME = "root"
PASSWORD = "root"
# Panel
pn.extension('echarts',sizing_mode="stretch_width",template="fast", theme="dark")
ACCENT = "orange"
# pylint: disable=line-too-long
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel",
                               sidebar_width=200, accent_base_color=ACCENT,
                               header_background=ACCENT, font="Montserrat")
# pylint: enable=line-too-long

# Zenoh retrieve values and save values to IoTDB
def retrieve():
    """Retrieves temperature data from Zenoh and stores it in IoTDB."""
    results = workspace.get('/myfactory/machine1/temp')
    
    # Handle new API where get returns Reply objects
    temperature_val = None
    timestamp_val = None
    
    if results:
        for reply in results:
            if reply.is_ok():
                sample = reply.ok
                if sample.payload is not None:
                    try:
                        temperature_val = bytes(sample.payload).decode('utf-8')
                        if hasattr(sample.timestamp, 'time'):
                            timestamp_val = datetime.fromtimestamp(sample.timestamp.time.timestamp()).isoformat()
                        else:
                            timestamp_val = datetime.utcnow().isoformat()
                    except Exception as e:
                        print(f"Error processing sample: {e}")
                        temperature_val = str(sample.payload)
                        timestamp_val = datetime.utcnow().isoformat()
                break
    
    if temperature_val is None:
        temperature_val = "0"
        timestamp_val = datetime.utcnow().isoformat()
    
    iotdb_session = Session(IP, PORT, USERNAME, PASSWORD)
    iotdb_session.open(False)
    # pylint: disable=line-too-long
    sql_query = f"INSERT INTO root.myfactory.machine1(timestamp,temperature) values('{timestamp_val}', {temperature_val})"
    # pylint: enable=line-too-long
    iotdb_session.execute_non_query_statement(sql_query)
    # pylint: disable=line-too-long
    result = iotdb_session.execute_query_statement("SELECT * FROM root.myfactory.machine1 ORDER BY TIME DESC limit 10")
    # pylint: enable=line-too-long
    # Transform to Pandas Dataset
    df_result = result.todf()
    iotdb_session.close()
    values_list = df_result['root.myfactory.machine1.temperature'].values.tolist()
    #TODO convert timevalues to datetime values
    timevalues_list = df_result.Time.values.tolist()
    return float(temperature_val), values_list, timevalues_list

# Gauge data
CURRENT_TEMPERATURE = 0
# Initialize values and timevalues to avoid potential errors if retrieve() returns None
RETRIEVED_VALUES = None
RETRIEVED_TIMEVALUES = None

retrieved_data = retrieve()
if retrieved_data is not None:
    CURRENT_TEMPERATURE, RETRIEVED_VALUES, RETRIEVED_TIMEVALUES = retrieved_data

# invisible slider and literal to jscallback
slider_widget = pn.widgets.FloatSlider(visible=False)
# pylint: disable=line-too-long
literal_input_widget = pn.widgets.LiteralInput(name='Literal Input (dict)',
        value={'key': [1, 2, 3]}, type=dict, visible=False)
# pylint: enable=line-too-long

# Stream function
def stream_data():
    """Streams data from retrieve() to update dashboard components."""
    # Renaming variables to avoid W0621
    s_temperature, s_values, s_timevalues = retrieve()
    literal_dict = {str(l):v for l, v in zip(s_timevalues, s_values)}
    #print('in python', literal_dict)
    literal_input_widget.value = literal_dict
    slider_widget.value = s_temperature
    # this step triggers internally the js_callback attached to the slider / literal input

GAUGE_DATA = {
    'tooltip': {
        'formatter': '{a} <br/>{b} : {c}\u00b0C'
    },
    'series': [
        {
            'name': 'Gauge',
            'type': 'gauge',
            'detail': {'formatter': '{value}\u00b0C'},
            'data': [{'value': [CURRENT_TEMPERATURE], 'name': 'Temperature'}]
        }
    ]
}

#callback
pn.state.add_periodic_callback(stream_data, 250)
# gauge panel + slider
gauge_pane_widget = pn.pane.ECharts(GAUGE_DATA,width=400, height=400)
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
# Initialize with empty data if retrieved_timevalues or retrieved_values are None
ECHART_DATA = {
    'title': {
        'text': 'Temperature over Time'
    },
    'tooltip': {},
    'legend': {
        'data':['Temperature over time']
    },
    'xAxis': {
        'data': RETRIEVED_TIMEVALUES if RETRIEVED_TIMEVALUES is not None else []
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': RETRIEVED_VALUES if RETRIEVED_VALUES is not None else []
    }],
}

ECHART_DATA['series'] = [dict(ECHART_DATA['series'][0], type= 'line')]
responsive_spec_data = dict(ECHART_DATA, responsive=True)
echart_pane_widget = pn.pane.ECharts(responsive_spec_data,theme="dark", height=400)
row_echart_widget = pn.Row(echart_pane_widget,literal_input_widget).servable()
# pylint: disable=line-too-long
literal_input_widget.jscallback(args={'echart': echart_pane_widget,}, value="""
    console.log(cb_obj.value)
    let literal_dict = JSON.parse( cb_obj.value.replaceAll("'",'\"') )
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
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
# pylint: enable=line-too-long
pn.panel("# Settings").servable(area="sidebar")
