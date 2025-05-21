#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
import zenoh
import json
import random
import time

random.seed()

def read_temp():
    return random.randint(15, 30)

def run_sensor_loop(session):
    # read and produce a temperature every second
    while True:
        t = read_temp()
        session.put('/myfactory/machine1/temp', t)
        print (t)
        time.sleep(15)

if __name__ == "__main__":
    conf = zenoh.Config()
    conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(["tcp/127.0.0.1:7447"]))
    with zenoh.open(conf) as session:
        run_sensor_loop(session)