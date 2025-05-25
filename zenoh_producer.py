#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# TODO: Add module docstring
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
import json
import random
import time

import zenoh

random.seed()

def read_temp():
    """Reads a random temperature."""
    return random.randint(15, 30)

def run_sensor_loop(sensor_session):
    """Runs a loop to read and produce temperature data."""
    # read and produce a temperature every second
    while True:
        temp = read_temp()
        sensor_session.put('/myfactory/machine1/temp', temp)
        print(temp)
        time.sleep(15)

if __name__ == "__main__":
    config = zenoh.Config()
    # Set mode to client
    config.insert_json5("mode", json.dumps("client"))
    # Corrected configuration key for connect endpoints
    config.insert_json5("connect/endpoints", json.dumps(["tcp/127.0.0.1:7447"]))
    with zenoh.open(config) as open_session:
        run_sensor_loop(open_session)
