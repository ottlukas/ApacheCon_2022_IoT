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
import os

import zenoh

random.seed()

def read_temp():
    """Reads a random temperature."""
    return random.randint(15, 30)

def run_sensor_loop(sensor_session):
    """Runs a loop to read and produce temperature data."""
    # read and produce a temperature every second
    print("Inside run_sensor_loop, starting while True loop.", flush=True)
    while True:
        try:
            temp = read_temp()
            print(f"Read temperature: {temp}", flush=True)
            sensor_session.put('myfactory/machine1/temp', str(temp))
            print(temp, flush=True) # This is the actual numeric output for the test script
            time.sleep(0.5) # Reduced sleep time for more frequent sends
        except Exception as e_loop:
            print(f"Error in sensor loop: {e_loop}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(1) # Avoid busy-looping on continuous errors

if __name__ == "__main__":
    print("Producer script started. Configuring Zenoh session...", flush=True)
    config = zenoh.Config()
    # Set mode to client
    config.insert_json5("mode", json.dumps("client"))
    # Corrected configuration key for connect endpoints
    zenoh_router_endpoint = os.environ.get("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
    print(f"Using Zenoh router endpoint: {zenoh_router_endpoint}", flush=True)
    config.insert_json5("connect/endpoints", json.dumps([zenoh_router_endpoint]))

    print("Attempting to open Zenoh session...", flush=True)
    try:
        with zenoh.open(config) as open_session:
            print("Zenoh session opened. Starting sensor loop...", flush=True)
            run_sensor_loop(open_session)
    except Exception as e:
        print(f"An error occurred: {e}", flush=True)
        import traceback
        traceback.print_exc()
