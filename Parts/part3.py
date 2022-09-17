#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
"""

import panel as pn

pn.extension(template="fast", theme="dark")

pn.state.template.param.update(site="ApacheCon 2022", title="Introduction to dashboarding with Panel")

pn.panel('# Hello ApacheCon 2022\n').servable()
# side panel with logo and "Settings"
pn.pane.JPG("https://apache.org/img/asf-estd-1999-logo.jpg", sizing_mode="scale_width", embed=False).servable(area="sidebar")
pn.panel("# Settings").servable(area="sidebar")