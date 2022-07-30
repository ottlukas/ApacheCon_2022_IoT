#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 19:10:07 2022
@author: luk
"""
import re
from sqlite3 import Timestamp
import zenoh
from iotdb.Session import Session
from datetime import datetime
import time
import panel as pn
import numpy as np
import pandas as pd

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
    session = Session(ip, port_, username_, password_)
    session.open(False)
    date_time = datetime.fromtimestamp(results[0].timestamp.time)
    sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values("+str(date_time)+", "+str(results[0].value.get_content())+")"
    #print(sql)
    session.execute_non_query_statement(sql)
    session.close()
    return results[0].value.get_content()

# Gauge data
temperature = 0
if not retrieve() == None:
    temperature = retrieve()
    
# invisible slider to jscallback
slider = pn.widgets.FloatSlider(visible=False)
# Stream function
def stream():
    #gauge invisible slider to update gauge
    temperature = retrieve()
    #print('in python', temperature)
    slider.value = temperature # this step triggers internally the js_callback attached to the slider 
    
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
};

#callback
pn.state.add_periodic_callback(stream, 250)
# gauge panel + slider
gauge_pane = pn.pane.ECharts(gauge,width=400, height=400)
row = pn.Row(gauge_pane,slider).servable()
# Linechart
# TODO Query IoTDB and update Linechart with current Temperature values
echart = {
    'title': {
        'text': 'Temperature over Time'
    },
    'tooltip': {},
    'legend': {
        'data':['Temperature over time']
    },
    'xAxis': {
        'data': [0,1,2,3,4,5,6,7,8,9,10]
    },
    'yAxis': {},
    'series': [{
        'name': 'Temperature',
        'type': 'bar',
        'data': [10,15,23,16,24,5,33,45,17,8,22]
    }],
};


echart['series'] = [dict(echart['series'][0], type= 'line')]
responsive_spec = dict(echart, responsive=True)
echart_pane = pn.pane.ECharts(responsive_spec, height=400).servable()

# js callback functions
slider.jscallback(args={'gauge': gauge_pane}, value="""
    console.log( 'dummy slider:', cb_obj.value, 
            'gauge value',gauge.data.series[0].data[0].value);
    gauge.data.series[0].data[0].value = cb_obj.value;
    gauge.properties.data.change.emit()"""
    )
# side panel with logo and "Settings"
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")
