# READ ME
This is a short Python script to show an end to end connection from Zenoh IoT Protocol to a Panel Dashboard Webapplication, which could run in a Notebook to analyse the incoming IoT Data.

## Prerequisites

Install and execute
1) [Zenoh Installation](https://zenoh.io/docs/getting-started/installation/)
    This project uses the Zenoh 1.0.x API. Install the Python library using:
    ```bash
    pip install eclipse-zenoh==1.3.4
    ```

2) [Zenoh First App](https://zenoh.io/docs/getting-started/first-app/)

    Adapt the Producer topic to the one in the panel_script py or the other way around. 
    - "'/myfactory/machine1/temp'"
    Same for the Zenoh Broker
    - "'/myfactory/**'"

    Start zenoh broker:
    ```
    zenohd --mem-storage='/myfactory/**' 
    ``` 

3) [Apache IoTDB Quickstart](https://iotdb.apache.org/UserGuide/V0.13.x/QuickStart/QuickStart.html)

    Download [Apache IoTDB](https://iotdb.apache.org/Download/)
    ```
    ./sbin/start-server.sh 
    ```
    ```
    ./sbin/start-cli.sh -h 127.0.0.1 -p 6667 -u root -pw root
    ```
    Execute in IoTDB CLI:
    ```
    SET STORAGE GROUP TO root.myfactory
    CREATE TIMESERIES root.myfactory.machine1.temperature WITH DATATYPE=INT32, ENCODING=PLAIN
    INSERT INTO root.myfactory.machine1(timestamp,temperature) values(200,21) // Test Insert
    SELECT * FROM root.myfactory.machine1
    ```

4) Install [Panel](https://panel.holoviz.org/getting_started/index.html)
    
    Used Python packages:
    ```
    import zenoh
    import json
    from iotdb.Session import Session
    from datetime import datetime
    import panel as pn
    ```
5) Execute in a Shell / Terminal (whith running Zenoh Broker and Apache IoTDB): 
    ``` 
    panel serve 'panel_script.py' --autoreload --show 
    ```

## Code Quality
The Python code in this repository has been formatted and linted using Pylint to ensure adherence to common Python coding standards and improve readability. This helps in maintaining a clean and understandable codebase.
