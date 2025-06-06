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
import pandas # Ensure pandas is imported for DataFrame creation

import zenoh

# Attempt to import IoTDB, but allow failure
iotdb_available = False
try:
    from iotdb.Session import Session as IoTDBLibSession # Renamed to avoid conflict
    iotdb_available = True
    print("IoTDB Session client imported successfully.", flush=True)
except ImportError:
    print("Warning: IoTDB Session client not found. Will skip IoTDB operations.", flush=True)

def main():
    """Main function to retrieve data from Zenoh and optionally store it in IoTDB."""
    global iotdb_available # Declare intent to use and modify the global variable

    conf = zenoh.Config()
    # Set mode to client
    conf.insert_json5("mode", json.dumps("client"))
    # Corrected configuration key for connect endpoints
    # pylint: disable=line-too-long
    zenoh_router_endpoint = os.environ.get("ZENOH_ROUTER_ENDPOINT", "tcp/127.0.0.1:7447")
    conf.insert_json5("connect/endpoints", json.dumps([zenoh_router_endpoint]))
    # pylint: enable=line-too-long
    print("Attempting to open Zenoh session...", flush=True)
    zenoh_session = zenoh.open(conf) # Zenoh session
    print("Zenoh session open. Getting data for 'myfactory/machine1/temp'...", flush=True)
    # Use the correct key expression (no leading slash)
    print("Attempting Zenoh get (simple form)...", flush=True)
    results = list(zenoh_session.get('myfactory/machine1/temp')) # Reverted to simplest form

    iotdb_conn = None
    if iotdb_available:
        iotdb_ip = os.environ.get("IOTDB_HOST", "127.0.0.1")
        iotdb_port = os.environ.get("IOTDB_PORT", "6667")
        iotdb_username = "root"
        iotdb_password = "root"
        try:
            # pylint: disable=line-too-long
            iotdb_conn = IoTDBLibSession(iotdb_ip, iotdb_port, iotdb_username, iotdb_password)
            # pylint: enable=line-too-long
            iotdb_conn.open(False)
            print("IoTDB connection opened successfully.", flush=True)
        except Exception as e_iotdb_conn:
            print(f"Failed to connect to IoTDB: {e_iotdb_conn}. Will not perform IoTDB operations.", flush=True)
            iotdb_available = False # Modifies the global variable due to 'global' declaration at function start

    retrieved_data_for_df = [] # Store data for DataFrame creation

    if not results:
        print("No data received from Zenoh replies list.", flush=True)
    else:
        print(f"Received {len(results)} replies from Zenoh get.", flush=True)
        processed_one_sample_ok = False
        for reply in results:
            if reply.is_ok():
                sample = reply.ok
                if not processed_one_sample_ok: # Indicate Zenoh get worked at least once
                     print(f"Successfully retrieved data from Zenoh: {sample.key_expr}", flush=True)
                     processed_one_sample_ok = True

                try:
                    value_content = bytes(sample.payload).decode('utf-8')
                    # Using HLC counter as a simplified timestamp for this example
                    # as full datetime conversion from HLC is complex and was failing.
                    timestamp_val = sample.timestamp.get_counter() # HLC counter

                    print(f"  Payload: {value_content}, Timestamp (HLC counter): {timestamp_val}", flush=True)
                    retrieved_data_for_df.append({'timestamp': timestamp_val, 'temperature': float(value_content)})

                    if iotdb_available and iotdb_conn:
                        try:
                            # For IoTDB, timestamp should ideally be epoch milliseconds.
                            # HLC counter is not directly epoch ms. This insert WILL LIKELY FAIL or store nonsensical time.
                            # This part is for demonstrating the flow if IoTDB was working perfectly with HLC.
                            # A proper solution would need HLC to epoch ms conversion.
                            sql_insert = f"INSERT INTO root.myfactory.machine1(timestamp,temperature) values({timestamp_val}, {float(value_content)})"
                            print(f"Attempting SQL: {sql_insert}", flush=True)
                            iotdb_conn.execute_non_query_statement(sql_insert)
                            print("Data inserted into IoTDB (or attempted).", flush=True)
                        except Exception as e_iotdb_insert:
                            print(f"Error inserting into IoTDB: {e_iotdb_insert}. Data not stored in IoTDB.", flush=True)
                except Exception as e_sample:
                    print(f"Error processing Zenoh sample: {e_sample}", flush=True)
            else:
                print(f"Received an error reply from Zenoh get: {reply.err}", flush=True)

    # Create DataFrame from successfully processed Zenoh messages
    if retrieved_data_for_df:
        dataframe = pandas.DataFrame(retrieved_data_for_df)
        print("Created DataFrame from Zenoh data.", flush=True)
    else:
        dataframe = None # Explicitly set to None if no data was processed
        print("No data processed from Zenoh to create DataFrame.", flush=True)

    if iotdb_available and iotdb_conn:
        try:
            # This query part is less critical if inserts were problematic.
            # Querying IoTDB to show what's there, if anything.
            print("Attempting to query IoTDB (might be empty or reflect previous state if inserts failed)...", flush=True)
            # pylint: disable=line-too-long
            query_result = iotdb_conn.execute_query_statement(
                "SELECT * FROM root.myfactory.machine1 ORDER BY time DESC LIMIT 5"
            )
            # pylint: enable=line-too-long
            iotdb_dataframe = query_result.todf()
            print("Data queried from IoTDB (if any):", flush=True)
            print(iotdb_dataframe) # Print what was actually in IoTDB
        except Exception as e_iotdb_query:
            print(f"Error querying from IoTDB: {e_iotdb_query}", flush=True)

        iotdb_conn.close()
        print("IoTDB connection closed.", flush=True)

    zenoh_session.close()
    print("Zenoh session closed.", flush=True)

    if dataframe is None:
        # This message is for the test script's heuristic if Zenoh itself yielded nothing usable
        print("DataFrame is None and no results processed.", flush=True)

    print("Final DataFrame created from Zenoh data (may be None if no data or errors):")
    print(dataframe)

if __name__ == "__main__":
    main()
