#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: luk
source: https://zenoh.io/docs/getting-started/first-app/
"""
from zenoh import Zenoh
from iotdb.Session import Session
from datetime import datetime

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    results = w.get('/myfactory/machine1/temp')
    ip = "127.0.0.1"
    port_ = "6667"
    username_ = "root"
    password_ = "root"
    #Insert into IoTDB via Python IoTDB API
    session = Session(ip, port_, username_, password_)
    session.open(False)
    datetime_iso = datetime.fromtimestamp(results[0].timestamp.time).isoformat()
    #print(datetime_iso)
    sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values("+str(datetime_iso)+", "+str(results[0].value.get_content())+")"
    #print(sql)
    session.execute_non_query_statement(sql)
    result = session.execute_query_statement("SELECT * FROM root.myfactory.machine1")
    # Transform to Pandas Dataset
    df = result.todf()
    session.close()
    print(df)