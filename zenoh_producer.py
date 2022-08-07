#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
from zenoh import Zenoh
import random
import time

random.seed()

def read_temp():
    return random.randint(15, 30)

def run_sensor_loop(w):
    # read and produce a temperature every second
    while True:
        t = read_temp()
        w.put('/myfactory/machine1/temp', t)
        print (t)
        time.sleep(15)

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    run_sensor_loop(w)