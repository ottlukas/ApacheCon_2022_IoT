#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
"""
import zenoh
import json # Added import
from iotdb.Session import Session as IoTDBLibSession # Renamed to avoid conflict
from datetime import datetime
import panel as pn

#Settings
#Zenoh
conf = zenoh.Config()
conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(["tcp/127.0.0.1:7447"]))
# It's better to manage the session lifecycle, e.g. with `with zenoh.open(conf) as session: ...`
# or by explicitly closing it on app shutdown. For now, opening globally.
# A Panel 'on_unload' callback would be a good place for session.close().
zenoh_session = zenoh.open(conf)

# IoTDB
ip = "127.0.0.1"
port_ = "6667"
username_ = "root"
password_ = "root"
# Panel
pn.extension('echarts',sizing_mode="stretch_width",template="fast", theme="dark")
ACCENT = "orange"
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel", 
                               sidebar_width=200, accent_base_color=ACCENT, 
                               header_background=ACCENT, font="Montserrat")

# Zenoh retrieve values and save values to IoTDB
def retrieve():
    # Assuming zenoh_session is the globally opened Zenoh session
    results = zenoh_session.get('/myfactory/machine1/temp') 
    
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
        temperature = float(temperature_str) # Or int() if it's always an integer
    except (UnicodeDecodeError, ValueError) as e:
        print(f"Error decoding Zenoh payload: {e}")
        return None, None, None # Indicate failure

    datetime_iso = datetime.fromtimestamp(first_result.timestamp.time.timestamp()).isoformat()

    iotdb_s = IoTDBLibSession(ip, port_, username_, password_) # IoTDB session
    iotdb_s.open(False)
    # Using temperature_str for SQL to match original str(results[0].value.get_content())
    sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values('"+str(datetime_iso)+"', "+str(temperature_str)+")"
    iotdb_s.execute_non_query_statement(sql)
    result = iotdb_s.execute_query_statement("SELECT * FROM root.myfactory.machine1 ORDER BY TIME DESC limit 10")
    # Transform to Pandas Dataset
    df = result.todf()
    iotdb_s.close()
    
    values = df['root.myfactory.machine1.temperature'].values.tolist()
    #TODO convert timevalues to datetime values
    timevalues = df.Time.values.tolist()
    return temperature, values, timevalues

# Gauge data
initial_temperature = 0
initial_values = []
initial_timevalues = []

retrieved_data = retrieve()
if retrieved_data and retrieved_data[0] is not None:
    initial_temperature, initial_values, initial_timevalues = retrieved_data
else:
    print("Failed to retrieve initial data for panel.")
    # Set some defaults if retrieve() fails, to prevent errors later
    # initial_temperature remains 0
    # initial_values and initial_timevalues remain empty lists

# invisible slider and literal to jscallback
slider = pn.widgets.FloatSlider(visible=False)
literal_input = pn.widgets.LiteralInput(name='Literal Input (dict)', 
        value={'key': [1, 2, 3]}, type=dict, visible=False)
# Stream function
def stream():
    retrieved_data = retrieve()
    if retrieved_data and retrieved_data[0] is not None:
        temperature, values, timevalues = retrieved_data
        literal_dict = {str(l):v for l, v in zip(timevalues, values)}
        #print('in python', literal_dict)
        literal_input.value = literal_dict
        slider.value = temperature
        # this step triggers internally the js_callback attached to the slider / literal input
    else:
        print("Stream: Failed to retrieve data, skipping update.")
    
gauge = {
    'tooltip': {
        'formatter': '{a} <br/>{b} : {c}°C'
    },
    'series': [
        {
            'name': 'Gauge',
            'type': 'gauge',
            'detail': {'formatter': '{value}°C'},
            'data': [{'value': [initial_temperature], 'name': 'Temperature'}] # Use initial_temperature
        }
    ]
}

#callback
pn.state.add_periodic_callback(stream, 250)
# gauge panel + slider
gauge_pane = pn.pane.ECharts(gauge,width=400, height=400)
row = pn.Row(gauge_pane,slider).servable()
# js callback functions
slider.jscallback(args={'gauge': gauge_pane}, value="""
    console.log( 'dummy slider:', cb_obj.value, 
            'gauge value',gauge.data.series[0].data[0].value);
    gauge.data.series[0].data[0].value = cb_obj.value;
    gauge.properties.data.change.emit()"""
    )
# Linechart
echart = {
    'title': {
        'text': 'Temperature over Time'
    },
    'tooltip': {},
    'legend': {
        'data':['Temperature over time']
    },
    'xAxis': {
        'data': initial_timevalues # Use initial_timevalues
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': initial_values # Use initial_values
    }],
}

echart['series'] = [dict(echart['series'][0], type= 'line')]
responsive_spec = dict(echart, responsive=True)
echart_pane = pn.pane.ECharts(responsive_spec,theme="dark", height=400)
row = pn.Row(echart_pane,literal_input).servable()
literal_input.jscallback(args={'echart': echart_pane,}, value="""
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

# side panel with logo and "Settings"
pn.pane.JPG("asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")
