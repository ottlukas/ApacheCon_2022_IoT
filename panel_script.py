#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 19:10:07 2022
@author: luk
"""
import zenoh
from iotdb.Session import Session
from datetime import datetime
import panel as pn


#Settings
#Zenoh
z = zenoh.Zenoh({'peer': 'tcp/127.0.0.1:7447'})
w = z.workspace('/')
# IoTDB
ip = "127.0.0.1"
port_ = "6667"
username_ = "root"
password_ = "root"
# Panel
pn.extension('echarts',sizing_mode="stretch_width",template="fast")
ACCENT = "orange"
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel", 
                               sidebar_width=200, accent_base_color=ACCENT, 
                               header_background=ACCENT, font="Montserrat")

# Zenoh Retrieve values
def retrieve():
    results = w.get('/myfactory/machine1/temp')
    temperature = results[0].value.get_content()
    session = Session(ip, port_, username_, password_)
    session.open(False)
    datetime_iso = datetime.fromtimestamp(results[0].timestamp.time).isoformat()
    sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values("+str(datetime_iso)+", "+str(results[0].value.get_content())+")"
    session.execute_non_query_statement(sql)
    result = session.execute_query_statement("SELECT * FROM root.myfactory.machine1 ORDER BY TIME DESC limit 10")
    # Transform to Pandas Dataset
    df = result.todf()
    session.close()
    values = df['root.myfactory.machine1.temperature'].values.tolist()
    timevalues = df.Time.values.tolist()
    return temperature, values, timevalues

# Gauge data
temperature = 0
if not retrieve() == None:
    temperature, values, timevalues = retrieve()
    
# invisible slider to jscallback
slider = pn.widgets.FloatSlider(visible=False)
literal_input = pn.widgets.LiteralInput(name='Literal Input (dict)', 
        value={'key': [1, 2, 3]}, type=dict, visible=False)
# Stream function
def stream():
    #gauge invisible slider to update gauge
    temperature, values, timevalues = retrieve()
    literal_dict = {str(l):v for l, v in zip(timevalues, values)}
    #print('in python', literal_dict)
    literal_input.value = literal_dict
    slider.value = temperature
    # this step triggers internally the js_callback attached to the slider 
    
gauge = {
    'tooltip': {
        'formatter': '{a} <br/>{b} : {c}°C'
    },
    'series': [
        {
            'name': 'Gauge',
            'type': 'gauge',
            'detail': {'formatter': '{value}°C'},
            'data': [{'value': [temperature], 'name': 'Temperature'}]
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
        'data': timevalues
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': values
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
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")
