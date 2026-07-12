# -*- coding: utf-8 -*-
"""Configuration module for the IoT application."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Zenoh configuration
# NOTE: Zenoh 1.x key expressions must NOT have a leading slash.
ZENOH_ENDPOINT = os.getenv("ZENOH_ENDPOINT", "tcp/zenoh:7447")
ZENOH_HOST_ENDPOINT = os.getenv("ZENOH_HOST_ENDPOINT", "tcp/zenoh:7447")
ZENOH_KEY_EXPRESSION = os.getenv("ZENOH_KEY_EXPRESSION", "myfactory/machine1/temperature")

# IoTDB configuration
IOTDB_HOST = os.getenv("IOTDB_HOST", "iotdb")
IOTDB_PORT = int(os.getenv("IOTDB_PORT", "6667"))
IOTDB_USER = os.getenv("IOTDB_USER", "root")
IOTDB_PASSWORD = os.getenv("IOTDB_PASSWORD", "root")
IOTDB_DATABASE = os.getenv("IOTDB_DATABASE", "root.myfactory")
IOTDB_DEVICE = os.getenv("IOTDB_DEVICE", "root.myfactory.machine1")
IOTDB_MEASUREMENT = os.getenv("IOTDB_MEASUREMENT", "temperature")

# Dashboard configuration
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

# Simulator configuration
SIMULATOR_INTERVAL_SECONDS = float(os.getenv("SIMULATOR_INTERVAL_SECONDS", "1"))
SIMULATOR_MIN_VALUE = float(os.getenv("SIMULATOR_MIN_VALUE", "15"))
SIMULATOR_MAX_VALUE = float(os.getenv("SIMULATOR_MAX_VALUE", "35"))
