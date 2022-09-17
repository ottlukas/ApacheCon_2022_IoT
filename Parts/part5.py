#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
"""

import panel as pn
import pandas as pd

pn.extension(template="fast", theme="dark")

pn.state.template.param.update(site="ApacheCon 2022", title="Introduction to dashboarding with Panel")

def model(count=1):
    return pd.DataFrame({"x": range(0,count), "y": range(0,count)})

count_widget = pn.widgets.IntSlider(value=5, start=0, end=5).servable(area="sidebar")
imodel = pn.bind(model, count=count_widget)

pn.panel(imodel).servable()
# side panel with logo and "Settings"
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")