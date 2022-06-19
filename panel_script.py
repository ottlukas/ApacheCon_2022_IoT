#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 19:10:07 2022
@author: luk
"""
import re
from sqlite3 import Timestamp
import zenoh
import time
import panel as pn
import numpy as np
import pandas as pd

#Settings
z = zenoh.Zenoh({'peer': 'tcp/127.0.0.1:7447'})
w = z.workspace('/')
pn.extension('echarts',sizing_mode="stretch_width",template="fast")
ACCENT = "orange"
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel", 
                               sidebar_width=200, accent_base_color=ACCENT, 
                               header_background=ACCENT, font="Montserrat")

# Zenoh Retrieve values
def retrieve():
    results = w.get('/myfactory/machine1/temp')
    return results[0].value.get_content()

# Gauge data
global temperature, time_value, gauge
temperature = 0
if not retrieve() == None:
    temperature = retrieve()
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

# Stream function
def stream():
    #time_value += 1
    temperature = retrieve()
    #print (temperature)
    # how to update the gauge values ? 
    # -> the dictionary update below does not update the values in the panel
    #print(gauge['series'][0]['data'][0]['value'])
    gauge.update({['series'][0]['data'][0]['value'] : temperature})
    print(gauge['series'][0]['data'][0]['value'])
    
print(gauge['series'][0]['data'][0]['value'])  
gauge_pane = pn.pane.ECharts(gauge,width=400, height=400).servable()
pn.state.add_periodic_callback(stream, 150)
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

# side panel with logo and "Settings"
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")
