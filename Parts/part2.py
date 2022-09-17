#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
"""

import panel as pn

pn.extension(template="fast", theme="dark")

pn.state.template.param.update(site="ApacheCon 2022", title="Introduction to dashboarding with Panel")

pn.panel('# Hello ApacheCon 2022').servable()