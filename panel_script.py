#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 19:10:07 2022
@author: luk
"""
from zenoh import Zenoh
import panel as pn
import pandas as pd
pn.extension(sizing_mode="stretch_width",template="fast")
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

pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")

pn.panel(model).servable()
