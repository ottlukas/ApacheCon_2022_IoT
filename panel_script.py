#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 19:10:07 2022
@author: luk
"""
from zenoh import Zenoh
import panel as pn
import pandas as pd
pn.extension('echarts',sizing_mode="stretch_width",template="fast")
ACCENT = "orange"
pn.state.template.param.update(site="Apache Con", title="Introduction to data apps with Panel", 
                               sidebar_width=200, accent_base_color=ACCENT, 
                               header_background=ACCENT, font="Montserrat")
# Zenoh Retrieve values
def retrieve():
    z = Zenoh({})
    w = z.workspace('/')
    results = w.get('/myfactory/machine1/temp')
    return results[0].value.get_content()

# Panel Model eCharts Gauge
def model():
    gauge = {
		'tooltip': {
		    'formatter': '{a} <br/>{b} : {c}%'
		},
		'series': [
		    {
		        'name': 'Gauge',
		        'type': 'gauge',
		        'detail': {'formatter': '{value} °C'},
		        'data': [{'value': [retrieve()], 'name': 'Temperature'}]
		    }
		]
 	};
    gauge_pane = pn.pane.ECharts(gauge, width=400, height=400)

    pn.Column(gauge_pane)
    return gauge_pane
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

pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")

pn.panel(model).servable()
