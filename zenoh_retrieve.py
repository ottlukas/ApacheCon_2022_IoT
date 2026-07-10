#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zenoh retrieve script for educational demonstration.

Demonstrates querying the latest value from Zenoh storage using a GET request,
persisting the value in Apache IoTDB, and querying the database to show what is stored.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import zenoh
from app import config
from app.zenoh_client import decode_payload
from app.iotdb_client import IoTDBClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("zenoh_retrieve")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Zenoh Telemetry Retrieve and Persist")
    parser.add_argument(
        "--zenoh-endpoint",
        type=str,
        default=os.getenv("ZENOH_HOST_ENDPOINT", config.ZENOH_HOST_ENDPOINT),
        help="Zenoh router TCP endpoint"
    )
    parser.add_argument(
        "--zenoh-key",
        type=str,
        default=os.getenv("ZENOH_KEY_EXPRESSION", config.ZENOH_KEY_EXPRESSION),
        help="Zenoh key expression to query"
    )
    parser.add_argument(
        "--iotdb-host",
        type=str,
        default="127.0.0.1",
        help="IoTDB database server host"
    )
    parser.add_argument(
        "--iotdb-port",
        type=int,
        default=config.IOTDB_PORT,
        help="IoTDB database server port"
    )
    return parser.parse_args()

def parse_val_and_ts(payload_str: str) -> tuple:
    """Parse payload string to extract value and timestamp."""
    try:
        data = json.loads(payload_str)
        if isinstance(data, dict):
            val = float(data.get("value", 0.0))
            ts = data.get("timestamp", datetime.now(timezone.utc).isoformat())
            return val, ts
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    
    # Fallback to raw float
    val = float(payload_str)
    ts = datetime.now(timezone.utc).isoformat()
    return val, ts

def main():
    args = parse_args()
    logger.info("Initializing retrieve demonstration...")

    # Configure and open Zenoh Session
    conf_dict = {
        "mode": "client",
        "connect": {"endpoints": [args.zenoh_endpoint]}
    }
    z_config = zenoh.Config.from_json5(json.dumps(conf_dict))
    
    logger.info("Connecting to Zenoh router at: %s", args.zenoh_endpoint)
    try:
        session = zenoh.open(z_config)
    except Exception as exc:
        logger.error("Failed to connect to Zenoh: %s", exc)
        sys.exit(1)

    # Perform GET query
    logger.info("Retrieving latest values for Zenoh key '%s'...", args.zenoh_key)
    results = session.get(args.zenoh_key)
    
    retrieved_records = []
    
    # Process Zenoh query replies
    for reply in results:
        if reply.is_ok():
            sample = reply.ok
            payload_str = decode_payload(sample)
            if payload_str:
                try:
                    val, ts = parse_val_and_ts(payload_str)
                    retrieved_records.append({
                        "key": str(sample.key_expr),
                        "value": val,
                        "timestamp": ts
                    })
                    logger.info("Retrieved sample: key=%s value=%s timestamp=%s", sample.key_expr, val, ts)
                except Exception as exc:
                    logger.warning("Failed to parse sample: %s", exc)
        else:
            logger.warning("Zenoh GET error reply: %s", reply.err)
            
    session.close()
    logger.info("Zenoh session closed.")
    
    if not retrieved_records:
        logger.warning("No data retrieved from Zenoh storage.")
        print("\nDataFrame from Zenoh is empty.\n")
    else:
        # Create a pandas DataFrame
        df_zenoh = pd.DataFrame(retrieved_records)
        print("\n--- DataFrame of retrieved Zenoh Telemetry ---")
        print(df_zenoh)
        print("-" * 46 + "\n")
        
        # Connect to IoTDB and insert the records
        iotdb_client = IoTDBClient()
        logger.info("Connecting to Apache IoTDB at %s:%d...", args.iotdb_host, args.iotdb_port)
        if iotdb_client.connect(host=args.iotdb_host, port=args.iotdb_port):
            logger.info("Connected to IoTDB. Initializing schema...")
            iotdb_client.initialize_schema()
            
            # Insert retrieved data
            for record in retrieved_records:
                success = iotdb_client.insert_temperature(record["timestamp"], record["value"])
                if success:
                    logger.info("Inserted %s (%s) into IoTDB", record["value"], record["timestamp"])
                else:
                    logger.error("Failed to insert %s into IoTDB", record["value"])
                    
            # Query recent values to demonstrate retrieval from IoTDB
            logger.info("Querying back latest records from IoTDB...")
            db_records = iotdb_client.query_temperature(limit=10)
            if db_records:
                df_iotdb = pd.DataFrame(db_records)
                print("--- DataFrame of historical IoTDB Telemetry ---")
                print(df_iotdb)
                print("-" * 47 + "\n")
            else:
                logger.info("No records found in IoTDB.")
                
            iotdb_client.close()
            logger.info("IoTDB connection closed.")
        else:
            logger.warning("Could not connect to IoTDB. Skipping database insertion and query demonstration.")

if __name__ == "__main__":
    main()
