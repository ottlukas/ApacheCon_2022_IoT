#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# TODO: Add module docstring
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
import json
from datetime import datetime
import os

import zenoh
from iotdb.Session import Session as IoTDBLibSession # Renamed to avoid conflict

def main():
    """Main function to retrieve data from Zenoh and store it in IoTDB."""
    conf = zenoh.Config()
    # Set mode to client
    conf.insert_json5("mode", json.dumps("client"))
    # Corrected configuration key for connect endpoints
    # pylint: disable=line-too-long
    zenoh_router_endpoint = os.environ.get("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
    conf.insert_json5("connect/endpoints", json.dumps([zenoh_router_endpoint]))
    # pylint: enable=line-too-long
    zenoh_session = zenoh.open(conf) # Zenoh session
    results = zenoh_session.get('/myfactory/machine1/temp')

    iotdb_ip = os.environ.get("IOTDB_HOST", "127.0.0.1")
    iotdb_port = os.environ.get("IOTDB_PORT", "6667")
    iotdb_username = "root"
    iotdb_password = "root"
    #Insert into IoTDB via Python IoTDB API
    # pylint: disable=line-too-long
    iotdb_conn = IoTDBLibSession(iotdb_ip, iotdb_port, iotdb_username, iotdb_password) # IoTDB session
    # pylint: enable=line-too-long
    iotdb_conn.open(False)

    dataframe = None # Initialize dataframe to None
    if results: # Check if results are not empty
        # Assuming results[0] is the desired data structure from Zenoh.
        # Zenoh 1.x Sample has `payload` (bytes) and `timestamp` (zenoh.Timestamp).
        # `zenoh.Timestamp` has `time` (datetime).
        # Producer sends an int. Assuming it's encoded as a string.
        first_result = results[0] # Assuming get returns a list
        # .timestamp() to convert datetime to float
        datetime_iso = datetime.fromtimestamp(
            first_result.timestamp.time.timestamp()
        ).isoformat()

        # Assuming UTF-8 string encoding of the number from producer
        value_content = first_result.payload.decode()

        print(datetime_iso)
        # SQL uses the string representation of the value.
        # pylint: disable=line-too-long
        sql_insert = f"INSERT INTO root.myfactory.machine1(timestamp,temperature) values('{datetime_iso}', {value_content})"
        # pylint: enable=line-too-long
        iotdb_conn.execute_non_query_statement(sql_insert)
        # pylint: disable=line-too-long
        query_result = iotdb_conn.execute_query_statement(
            "SELECT * FROM root.myfactory.machine1"
        )
        # pylint: enable=line-too-long
        # Transform to Pandas Dataset
        dataframe = query_result.todf()
        iotdb_conn.close()
    else:
        print("No data received from Zenoh.")

    zenoh_session.close() # Close Zenoh session
    print(dataframe)

if __name__ == "__main__":
    main()
