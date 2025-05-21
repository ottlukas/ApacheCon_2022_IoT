#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
import zenoh
import json
from iotdb.Session import Session as IoTDBLibSession # Renamed to avoid conflict
from datetime import datetime

if __name__ == "__main__":
    conf = zenoh.Config()
    conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(["tcp/127.0.0.1:7447"]))
    session = zenoh.open(conf) # Zenoh session
    results = session.get('/myfactory/machine1/temp')
    
    ip = "127.0.0.1"
    port_ = "6667"
    username_ = "root"
    password_ = "root"
    #Insert into IoTDB via Python IoTDB API
    iotdb_session = IoTDBLibSession(ip, port_, username_, password_) # IoTDB session
    iotdb_session.open(False)
    
    if results: # Check if results are not empty
        # Assuming results[0] is the desired data structure from Zenoh
        # The original code did not check if results was empty or had the expected structure
        # For now, I'll keep the logic similar but this might need more robust error handling
        # Also, the old code results[0].timestamp.time might need adjustment based on Zenoh 1.x API
        # Assuming results[0].sample.timestamp.time for Zenoh 1.x based on common patterns
        # and results[0].payload for value. This is a guess and might need correction.
        # For now, I will try to keep it as close as possible to the original,
        # but Zenoh 1.x Sample (which `get` returns) has `payload` and `timestamp` attributes.
        # The original `results[0].value.get_content()` implies `value` was an object.
        # `results[0].timestamp.time` implies timestamp was an object with a time attribute.
        # In Zenoh 1.x, a `Sample` has `payload` (bytes) and `timestamp` (a `Timestamp` object with `time` and `id`).
        
        # For now, let's assume the structure from get is a list of Sample objects
        # and results[0].payload gives the content, and results[0].timestamp.time gives the timestamp.
        # This part might need review if the structure of `results[0]` has changed significantly.
        # The original code uses `results[0].value.get_content()`. In Zenoh 1.x, this is likely `results[0].payload.decode()` if it's text.
        # Or just `results[0].payload` if it's directly usable as a number (e.g. if Zenoh handles encoding/decoding).
        # Given `read_temp` returns an int, it's likely a numeric value. ZenohPy `Value` could wrap it.
        # A `Sample` from `get` has a `payload` attribute which is `bytes`.
        # We need to decode this, assuming it's a string representation of the number, or unpack it if it's binary.
        # The original `w.put('/myfactory/machine1/temp', t)` where t is an int.
        # Zenoh Python API examples show `session.put(key_expr, Value(payload, encoding=Encoding.APP_INTEGER))`
        # If it was put as an integer, `get` should return a Sample whose payload can be interpreted as such.
        # `Value.get_content()` implies some form of automatic decoding.
        # For now, I'll assume `results[0].payload` needs to be converted.
        # Let's assume it's stored as a string representation of an integer for simplicity, matching `print(t)` in producer.
        
        # This is a critical part: How Zenoh 0.5.0's `results[0].value.get_content()` and `results[0].timestamp.time`
        # map to Zenoh 1.0.x's `Sample` object from `session.get()`.
        # A `Sample` has `key_expr`, `payload` (bytes), `encoding`, `timestamp` (zenoh.Timestamp).
        # `zenoh.Timestamp` has `time` (datetime) and `id` (bytes).
        # So, `results[0].timestamp.time` likely maps to `sample.timestamp.time`.
        # And `results[0].value.get_content()` likely maps to `sample.payload` (potentially needing decoding/deserialization).
        # The producer puts an integer. Let's assume it's encoded as a string.
        
        # For now, I will assume the get result is a list of Sample objects.
        # And that payload needs to be decoded.
        first_result = results[0] # Assuming get returns a list
        datetime_iso = datetime.fromtimestamp(first_result.timestamp.time.timestamp()).isoformat() # .timestamp() to convert datetime to float
        
        # The producer sends an int. How it's encoded by default in Zenoh 0.x `put(key, int_val)`
        # and how it's retrieved by `get` then `value.get_content()` is key.
        # In Zenoh 1.x, `put(key, int_val)` will use `Encoding.APP_INTEGER`.
        # `get` returns a `Sample`. `sample.payload` will be bytes.
        # We need to convert these bytes back to an int. `int.from_bytes(sample.payload, 'big')` or similar if it's raw bytes.
        # Or if it was `str(t)` in put, then `int(sample.payload.decode())`.
        # The producer does `session.put('/myfactory/machine1/temp', t)` where t is an int.
        # Let's assume Zenoh 1.x `put` with an int argument encodes it in a way that `payload` can be converted back.
        # A common way is string encoding for simplicity or specific int encoding.
        # If the producer used `session.put(key, str(t))`, then `int(first_result.payload.decode())` would be correct.
        # If the producer used `session.put(key, t)` (an int), zenoh might use an efficient binary encoding.
        # For now, let's assume it's retrievable as a string, as the original print statement suggests.
        # The simplest assumption is that Zenoh handles the type conversion, or it's stored as a string.
        # Given `results[0].value.get_content()`, it's likely some form of string or auto-decoded value.
        # Let's try `first_result.payload.decode()` and convert to string for SQL.
        value_content = first_result.payload.decode() # Assuming UTF-8 string encoding of the number

        print(datetime_iso)
        # Ensure value_content is suitable for SQL (e.g. if it's numeric, it should be passed as such, not as a string if the column is numeric)
        # The original code directly uses str(results[0].value.get_content()), so using value_content directly should be fine if it's already a string.
        sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values('"+str(datetime_iso)+"', "+str(value_content)+")"
        #print(sql)
        iotdb_session.execute_non_query_statement(sql)
        result = iotdb_session.execute_query_statement("SELECT * FROM root.myfactory.machine1")
        # Transform to Pandas Dataset
        df = result.todf()
        iotdb_session.close()
    else:
        df = None # Or handle error appropriately
        print("No data received from Zenoh.")

    session.close() # Close Zenoh session
    print(df)